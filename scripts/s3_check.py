#!/usr/bin/env python3
"""S3 节奏自检：校验 storyboard 是否满足节奏铁律与边界约束。
用法: s3_check.py <job_dir>  （exit 1 = 不过）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.validate import validate_file  # noqa: E402

RULES = {
    "max_consecutive_same_roll": 3,
    "max_consecutive_text_broll": 2,
    "min_shot_sec": 2.0,
    "max_shot_sec": 18.0,
    "hook_shock_within_ms": 6000,
}



def check_anchors(sb: dict, timing: dict) -> list[str]:
    """motion 节拍的（锚：'xx'）词必须在 timing words 中存在（子串匹配）。
    talkcraft 纪律：动效拍必须锁得住字——锚不存在的节拍是写意描述，机器不可验。"""
    errs = []
    words = "".join(w["text"] for seg in timing.get("segments", []) for w in seg.get("words", []))
    texts = "".join(seg["text"] for seg in timing.get("segments", []))
    for shot in sb.get("shots", []):
        for m in shot.get("motion", []):
            if "（锚：" in m or "(锚:" in m:
                seg = m.split("锚：")[-1].split("(锚:")[-1].split("）")[0].split(")")[0].strip("'「」")
                key = seg.replace("'", "")
                if key and key not in words and key not in texts:
                    errs.append(f"{shot['id']}: 锚词「{key}」在 timing 中不存在")
    return errs


def main() -> None:
    job = Path(sys.argv[1])
    errs = validate_file("storyboard", job / "storyboard.json")
    if errs:
        print("[s3-check] schema FAIL:")
        [print("  -", e) for e in errs]
        sys.exit(1)

    sb = json.loads((job / "storyboard.json").read_text(encoding="utf-8"))
    timing = json.loads((job / "timing.json").read_text(encoding="utf-8"))
    tmap = {s["id"]: s for s in timing["segments"]}
    shots = sb["shots"]
    # 0.5) 动效锚词机器校验（锚不在 timing 里的节拍 = 不可验描述）
    errs.extend(check_anchors(sb, timing))

    # 0) ★时间从真相源派生：seg_ids 是唯一声明，start/end 一律从 timing.json 重算
    for sh in shots:
        segs = [tmap[sid] for sid in sh["time"]["seg_ids"] if sid in tmap]
        if segs:
            sh["time"]["start_ms"] = min(s["start_ms"] for s in segs)
            sh["time"]["end_ms"] = max(s["end_ms"] for s in segs)
    errs, warns = [], []

    # 1) 镜头时间必须覆盖 timing 段并落在段边界上
    covered = set()
    for sh in shots:
        t = sh["time"]
        if t["start_ms"] >= t["end_ms"]:
            errs.append(f"{sh['id']}: start>=end")
        for sid in t["seg_ids"]:
            if sid not in tmap:
                errs.append(f"{sh['id']}: 引用不存在的 timing 段 {sid}")
            else:
                covered.add(sid)
    missing = set(tmap) - covered
    if missing:
        errs.append(f"时间轴段未被任何镜头覆盖: {sorted(missing)}")

    # 2) 镜头时序连续不重叠（按 id 顺序）
    prev_end = 0
    for sh in shots:
        if sh["time"]["start_ms"] < prev_end - 1:
            errs.append(f"{sh['id']}: 与上一镜头重叠")
        prev_end = max(prev_end, sh["time"]["end_ms"])

    # 3) 连续同类 roll / text 限制
    run = 1
    for i in range(1, len(shots)):
        same = shots[i]["roll"] == shots[i - 1]["roll"]
        run = run + 1 if same else 1
        if run > RULES["max_consecutive_same_roll"]:
            warns.append(f"{shots[i]['id']}: 连续 {run} 个 {shots[i]['roll']}-roll")
    trun = 1
    for i in range(1, len(shots)):
        both_text = shots[i].get("b_type") == "text" and shots[i - 1].get("b_type") == "text"
        trun = trun + 1 if both_text else 1
        if trun > RULES["max_consecutive_text_broll"]:
            warns.append(f"{shots[i]['id']}: 连续 {trun} 个 text 型 B-roll")

    # 4) A-roll 视角相邻不重复
    for i in range(1, len(shots)):
        a, b = shots[i - 1], shots[i]
        if a["roll"] == b["roll"] == "A":
            if a.get("view_angle") and a.get("view_angle") == b.get("view_angle"):
                warns.append(f"{b['id']}: 与上一镜头同为 {a['view_angle']} 视角")

    # 5) 时长与动效拍数
    for sh in shots:
        dur_s = (sh["time"]["end_ms"] - sh["time"]["start_ms"]) / 1000
        if not (RULES["min_shot_sec"] <= dur_s <= RULES["max_shot_sec"]):
            warns.append(f"{sh['id']}: 时长 {dur_s:.1f}s 超出 [{RULES['min_shot_sec']},{RULES['max_shot_sec']}]")
        if dur_s > 8 and len(sh.get("motion", [])) < 2:
            errs.append(f"{sh['id']}: {dur_s:.0f}s 长镜头 motion 拍数 <2")

    # 6) recipe_ref 必填（第一锁）
    for sh in shots:
        if not sh.get("recipe_ref"):
            errs.append(f"{sh['id']}: recipe_ref 缺失（配方强制铁律）")

    # 7) hook 5s 内视觉冲击
    if shots and shots[0]["time"]["start_ms"] > RULES["hook_shock_within_ms"]:
        warns.append("开头 5s 内没有镜头（hook 冲击不足）")

    # 节奏统计
    a = sum(1 for s in shots if s["roll"] == "A")
    b = len(shots) - a
    sb.setdefault("rhythm_check", {})
    sb["rhythm_check"]["a_b_ratio"] = [round(a / len(shots), 2), round(b / len(shots), 2)]

    # pace_gate（a2e 节奏 + FireRed 字数预算）：建议级，不挡闸
    try:
        from pipeline import pace_gate
        _script = json.loads((job / "script.json").read_text(encoding="utf-8"))
        _timing = json.loads((job / "timing.json").read_text(encoding="utf-8"))
        _rep = pace_gate.check(_script, _timing, sb)
        sb["rhythm_check"]["pace_gate"] = {
            "violations": _rep["pace_violations"],
            "sentences": _rep["sentences"],
            "duration": _rep["duration"],
            "over_budget": _rep.get("budgets", {}).get("超预算镜", 0),
        }
        if _rep["pace_violations"]:
            print(f"[s3-check] ⚠ pace_gate: {_rep['pace_violations']} 处节奏越界（建议级，见 rhythm_check.pace_gate）")
    except Exception as e:  # noqa: BLE001 建议级不挡闸
        print(f"[s3-check] pace_gate 跳过: {e}")

    (job / "storyboard.json").write_text(json.dumps(sb, ensure_ascii=False, indent=2), "utf-8")

    print(f"[s3-check] 镜头 {len(shots)} | A:{a} B:{b} | A/B={sb['rhythm_check']['a_b_ratio']}")
    for w in warns:
        print("  [warn]", w)
    if errs:
        print("[s3-check] FAIL:")
        [print("  -", e) for e in errs]
        sys.exit(1)
    print("[s3-check] OK")


if __name__ == "__main__":
    main()
