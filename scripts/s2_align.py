#!/usr/bin/env python3
"""S2b: 声学对齐 —— vo.wav + script.json → timing.json（时间轴真相源）。

复用 video-talkcraft 的 timestamps_cpu.py（路径引用，不改动）：
- 默认 FireRedASR2-CTC int8（尾部最稳零误报，模型 767MB）
- --backend whisper 兜底（faster-whisper small/int8，自动下载）
输出转换为本地 timing.json schema + 三项一致性校验（fail-fast，末段偏差>200ms 自动重对齐一次）。

用法: s2_align.py <job_dir> [--backend whisper|firered]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# 避免 scripts/pipeline.py 与 pipeline 包同名冲突：从 sys.path 移除脚本自身目录
sys.path = [p for p in sys.path if Path(p or ".").resolve() != Path(__file__).parent.resolve()]
sys.path.insert(0, str(ROOT))
def _find_talkcraft() -> Path:
    """定位 video-talkcraft（路径可被环境变量覆盖，避免硬编码失效）。"""
    candidates = [
        Path(os.environ.get("TALKCRAFT_HOME", "")) if os.environ.get("TALKCRAFT_HOME") else None,
        ROOT.parent.parent / "other" / "1other_video" / "video-talkcraft",
        Path("/Users/bainazi/Documents/outtt/other/1other_video/video-talkcraft"),
    ]
    for c in candidates:
        if c and (c / "scripts" / "timestamps_cpu.py").exists():
            return c
    raise FileNotFoundError(
        "找不到 video-talkcraft（scripts/timestamps_cpu.py）。"
        "请设置环境变量 TALKCRAFT_HOME 指向其根目录。"
    )


TALKCRAFT = _find_talkcraft()
TALKCRAFT_ALIGN = TALKCRAFT / "scripts" / "timestamps_cpu.py"
VENV_PY = ROOT / ".venv" / "bin" / "python"

MAX_END_DEVIATION_MS = 200


def run_align(wav: Path, sentences: list[str], backend: str) -> dict:
    """调 talkcraft 对齐脚本，返回其原生输出。"""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({"sentences": sentences}, f, ensure_ascii=False)
        script_tmp = f.name
    out_tmp = script_tmp.replace(".json", ".ts.json")
    cmd = [str(VENV_PY), str(TALKCRAFT_ALIGN), str(wav), script_tmp, out_tmp]
    if backend == "whisper":
        cmd += ["--backend", "whisper"]
    print("[s2-align]", " ".join(cmd[1:3]), f"backend={backend}")
    subprocess.run(cmd, check=True)
    return json.loads(Path(out_tmp).read_text(encoding="utf-8"))


def merge_protected(seg: dict, prot: list[dict]) -> None:
    """数字豁免合并：把落在受保护 token 字符区间内的对齐碎片 word 合并为完整 token 条目。
    下游（字幕/动效锚点）永远看到完整 token。"""
    words = seg.get("words") or []
    if not words or not prot:
        return
    intervals = [(p["char_start"], p["char_end"], p["token"]) for p in prot]
    out: list[dict] = []
    run: list[dict] = []      # 当前受保护 token 的碎片缓冲
    cur_token: str | None = None
    char_pos = 0

    def flush() -> None:
        nonlocal run, cur_token
        if run:
            out.append({"text": cur_token or "".join(w["text"] for w in run),
                        "start_ms": run[0]["start_ms"], "end_ms": run[-1]["end_ms"],
                        "protected": True})
            run, cur_token = [], None

    for w in words:
        w_start, w_end = char_pos, char_pos + len(w["text"])
        char_pos = w_end
        hit = next((iv for iv in intervals if w_start < iv[1] and w_end > iv[0]), None)
        if hit is None:
            flush()
            out.append(w)
        else:
            if cur_token != hit[2]:
                flush()
                cur_token = hit[2]
            run.append(w)
    flush()
    seg["words"] = out


def align_confidence(seg: dict) -> tuple[str, float]:
    """对齐置信度分级：ASR match × 朗读速率偏差 × 大间隙占比 → high|medium|low。
    正常中文口播 4~6 字/秒，偏差>30% 记可疑；受保护 token 合并后跨度>2s 视为对齐失败强降 low。"""
    n = len(re.sub(r"[，。！？；、\s]", "", seg["text"]))
    dur_s = max(0.1, (seg["end_ms"] - seg["start_ms"]) / 1000)
    rate = n / dur_s
    rate_dev = 0.0 if 4.0 <= rate <= 6.0 else min(1.0, min(abs(rate - 4.0), abs(rate - 6.0)) / 3.0)
    ws = [w["start_ms"] for w in seg.get("words", [])]
    gaps = [b - a for a, b in zip(ws, ws[1:])]
    big_gap_ratio = (sum(1 for g in gaps if g > 500) / len(gaps)) if gaps else 0.0
    match = float(seg.get("match", 1.0))
    score = match * (1 - 0.5 * rate_dev) * (1 - 0.4 * big_gap_ratio)
    if any(w.get("protected") and w["end_ms"] - w["start_ms"] > 2000 for w in seg.get("words", [])):
        score = min(score, 0.5)
    level = "high" if score >= 0.85 else ("medium" if score >= 0.6 else "low")
    return level, round(score, 3)


def convert(job_dir: Path, raw: dict, backend: str, script_doc: dict) -> dict:
    """talkcraft 原生输出 → 本地 timing.json schema（毫秒）。"""
    segs = []
    for s in raw["sentences"]:
        segs.append({
            "id": f"t{s['i']:03d}",
            "start_ms": int(round(s["start"] * 1000)),
            "end_ms": int(round(s["end"] * 1000)),
            "text": s["text"],
            "match": round(s.get("match", 1.0), 3),
            "ok": s.get("ok", True),
            "words": [
                {"text": w["text"], "start_ms": int(round(w["start"] * 1000)), "end_ms": int(round(w["end"] * 1000))}
                for w in s.get("words", [])
            ],
        })
    # 与 script.json 的 segment 建立引用（一一对应；对齐脚本保证句序一致）
    for i, seg in enumerate(segs):
        seg["seg_ref"] = f"seg{i:03d}"
        src_prot = (script_doc.get("segments") or [{}]*len(segs))[i].get("protected_tokens")
        if src_prot:
            merge_protected(seg, src_prot)   # 数字豁免：碎片 → 完整 token
        level, score = align_confidence(seg)
        seg["align_confidence"] = level
        seg["align_score"] = score

    # ---- 不变量计算 ----
    overlaps = [i for i in range(1, len(segs)) if segs[i]["start_ms"] < segs[i - 1]["end_ms"]]
    gaps = [segs[i]["start_ms"] - segs[i - 1]["end_ms"] for i in range(1, len(segs))]
    duration_ms = int(round(raw["total"] * 1000))
    end_dev = duration_ms - segs[-1]["end_ms"]

    timing = {
        "version": "1.0",
        "audio": "audio/vo.wav",
        "duration_ms": duration_ms,
        "backend": backend,
        "segments": segs,
        "invariants": {
            "no_overlap": not overlaps,
            "max_gap_ms": max(gaps) if gaps else 0,
            "ends_within_ms": end_dev,
        },
    }
    return timing


def check(timing: dict) -> tuple[list[str], list[str]]:
    """返回 (结构错误, 低匹配警告)。结构错误硬失败；低匹配标记 ok:false 走人工复核（align-review.csv）。"""
    errs: list[str] = []
    warns: list[str] = []
    inv = timing["invariants"]
    if not inv["no_overlap"]:
        errs.append("时间轴存在重叠")
    if inv["max_gap_ms"] > 1500:
        errs.append(f"相邻段间隙过大: {inv['max_gap_ms']}ms（>1500ms，疑似漏句）")
    if abs(inv["ends_within_ms"]) > MAX_END_DEVIATION_MS:
        errs.append(f"末段结束与音频总时长偏差 {inv['ends_within_ms']}ms（>{MAX_END_DEVIATION_MS}ms）")
    bad = [s["id"] for s in timing["segments"] if not s.get("ok", True)]
    if bad:
        warns.append(f"锚点覆盖率低（match<0.90）的句子: {bad}（已标记 ok:false → audio/align-review.csv 人工复核）")
    return errs, warns


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("job_dir")
    ap.add_argument("--backend", default="whisper", choices=["whisper", "firered"])
    args = ap.parse_args()
    job_dir = Path(args.job_dir)

    script = json.loads((job_dir / "script.json").read_text(encoding="utf-8"))
    sentences = [seg["text"] for seg in script["segments"]]
    wav = job_dir / "audio" / "vo.wav"
    if not wav.exists():
        print(f"[s2-align] 缺少 {wav}", file=sys.stderr)
        sys.exit(1)

    for attempt in (1, 2):
        raw = run_align(wav, sentences, args.backend)
        timing = convert(job_dir, raw, args.backend, script)
        errs, warns = check(timing)
        if (not errs and not warns) or attempt == 2:
            break
        print(f"[s2-align] 校验未过（第{attempt}次）: {errs or warns} → 自动重对齐一次")

    if errs:
        print("[s2-align] FAIL（重对齐后仍不过）:", file=sys.stderr)
        for e in errs:
            print("  -", e, file=sys.stderr)
        sys.exit(1)
    for w in warns:
        print(f"[s2-align] ⚠ {w}", file=sys.stderr)

    out = job_dir / "timing.json"
    out.write_text(json.dumps(timing, ensure_ascii=False, indent=2), "utf-8")

    # 人工复核入口：低/中置信段先出列（人工可改 csv 后回灌 timing.json）
    review = job_dir / "audio" / "align-review.csv"
    with review.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["seg_id", "confidence", "score", "text", "前3词时间戳"])
        for s in timing["segments"]:
            if s["align_confidence"] != "high":
                head = " | ".join(f"{x['text']}@{x['start_ms']}" for x in s["words"][:3])
                w.writerow([s["id"], s["align_confidence"], s["align_score"], s["text"], head])

    from pipeline.validate import require
    require("timing", out)

    # 三项确认（方法论要求单独列出）
    print("[s2-align] === 最终确认 ===")
    print(f"  音频总时长: {timing['duration_ms']}ms")
    print(f"  时间轴总段数: {len(timing['segments'])}")
    print(f"  最后一段结束: {timing['segments'][-1]['end_ms']}ms (偏差 {timing['invariants']['ends_within_ms']}ms)")
    print(f"  最大间隙: {timing['invariants']['max_gap_ms']}ms | 重叠: 无" if timing["invariants"]["no_overlap"] else "  重叠: 有!")
    print(f"[s2-align] OK → {out}")


if __name__ == "__main__":
    main()
