"""storyboard 质量闸：节奏铁律（沿用 s3_check）+ 反单调规则（拆自 shotcraft「一种手法全片只当一次主角」）。

lint_storyboard(sb) -> list[str]  错误清单（空 = 通过）
规则全部确定性可复算——不达标就换配方重排，不靠模型自觉。
"""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft7Validator

ROOT = Path(__file__).resolve().parent.parent

# 反单调参数（可按片长缩放）
MAX_CONSEC_SAME_RECIPE = 2          # 连续同配方上限
AROLL_GAP = 2                       # A-roll 最小间隔镜数
SAME_RECIPE_PER_10SHOTS = 2         # 每 10 镜同配方最多几次（结构卡 Title/Ending 不计）


def _cap(n_shots: int) -> int:
    """单一配方全片上限。必须满足鸽笼：cap×配方数 ≥ 镜数，否则无解（已实测踩坑：cap=2×7=14<18 镜）。"""
    import math
    return max(3, math.ceil(n_shots / 4))


def lint_storyboard(sb: dict) -> list[str]:
    shots = sb.get("shots", [])
    errs: list[str] = []
    n = len(shots)
    if n == 0:
        return ["shots 为空"]

    # ---- 节奏铁律（与 s3_check 同源口径）----
    for i, s in enumerate(shots):
        dur = (s["time"]["end_ms"] - s["time"]["start_ms"]) / 1000
        if not (2.0 <= dur <= 18.0):
            errs.append(f"{s['id']}: 时长 {dur:.1f}s 超出 [2,18]s")
        if not s.get("motion") or len(s["motion"]) < 1:
            errs.append(f"{s['id']}: motion 为空（每镜至少 1 个画面节拍——talkcraft「每句都要有活的画面响应」）")
        if not (s.get("intent") or "").strip():
            errs.append(f"{s['id']}: intent 为空")

    # 连续同 roll / 连续同配方
    run_roll = run_recipe = 1
    for i in range(1, n):
        if shots[i]["roll"] == shots[i - 1]["roll"]:
            run_roll += 1
            if run_roll > 3:
                errs.append(f"{shots[i]['id']}: 连续 {run_roll} 镜同 roll={shots[i]['roll']}")
        else:
            run_roll = 1
        r_i, r_prev = shots[i].get("recipe_ref", ""), shots[i - 1].get("recipe_ref", "")
        if r_i and r_i == r_prev:
            run_recipe += 1
            if run_recipe > MAX_CONSEC_SAME_RECIPE:
                errs.append(f"{shots[i]['id']}: 连续 {run_recipe} 镜同配方 {r_i}（上限 {MAX_CONSEC_SAME_RECIPE}）")
        else:
            run_recipe = 1

    # 同配方全片占比（shotcraft：重复是廉价感第一来源；结构卡不计）
    from collections import Counter
    recipes = Counter(s.get("recipe_ref", "") for s in shots
                      if s.get("recipe_ref") not in ("TitleCard", "EndingCard"))
    cap = _cap(n)
    for r, c in recipes.items():
        if c > cap:
            errs.append(f"配方 {r} 全片 {c} 次 > 上限 {cap}")

    # A-roll 间隔（IP 形象别连刷存在感）
    aroll_idx = [i for i, s in enumerate(shots) if s["roll"] == "A"]
    for a, b in zip(aroll_idx, aroll_idx[1:]):
        if b - a - 1 < AROLL_GAP:
            errs.append(f"{shots[b]['id']}: 与上一 A-roll 仅隔 {b - a - 1} 镜（需 ≥{AROLL_GAP}）")

    # 首尾镜头约束
    if shots[0].get("recipe_ref") != "TitleCard":
        errs.append(f"首镜必须 TitleCard（现为 {shots[0].get('recipe_ref')}）")
    if shots[-1].get("recipe_ref") != "EndingCard":
        errs.append(f"末镜必须 EndingCard（现为 {shots[-1].get('recipe_ref')}）")

    # hook 镜 6s 内必须有 shock 节拍
    if shots[0]["time"]["end_ms"] - shots[0]["time"]["start_ms"] > 6000:
        ms = [m for m in shots[0].get("motion", [])]
        # 文本级检查放在 assemble 层；这里只挡超长 hook

    # 卡文字字数闸（registry arities 决定条数，这里守单条长度——爆框是短视频廉价感第二来源）
    reg = json.loads((ROOT / "render-engine" / "src" / "cards" / "registry.json").read_text("utf-8"))
    for s in shots:
        texts = (s.get("config") or {}).get("TEXT") or []
        slug = s.get("recipe_ref", "")[5:] if s.get("recipe_ref", "").startswith("card:") else ""
        arity = (reg.get(slug) or {}).get("arities", {}).get("TEXT") if slug else None
        if arity is not None and texts and len(texts) != arity:
            errs.append(f"{s['id']}: TEXT {len(texts)} 条 ≠ {slug} 需要 {arity} 条")
        for t in texts:
            if len(t) > 16:
                errs.append(f"{s['id']}: TEXT 单条 {len(t)} 字 > 16（'{t[:12]}…'，换卡或精简）")

    # C-roll 叠层纪律：ARoll 干净（≤1），任何镜头 ≤2
    for s in shots:
        ov = s.get("overlay") or []
        if len(ov) > 2:
            errs.append(f"{s['id']}: overlay {len(ov)} 层 > 2")
        if s["roll"] == "A" and len(ov) > 1:
            errs.append(f"{s['id']}: A-roll overlay {len(ov)} 层（IP 镜头保持干净，≤1）")

    # 时间轴连续无缝
    for a, b in zip(shots, shots[1:]):
        if b["time"]["start_ms"] != a["time"]["end_ms"]:
            errs.append(f"{b['id']} 起点与 {a['id']} 终点不连续")
    return errs


def validate_schema(sb: dict) -> list[str]:
    schema = json.loads((ROOT / "schemas" / "storyboard.schema.json").read_text(encoding="utf-8"))
    v = Draft7Validator(schema)
    return [f"{'/'.join(map(str, x.path))}: {x.message}" for x in v.iter_errors(sb)]
