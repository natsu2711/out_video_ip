#!/usr/bin/env python3
"""S6 密度/死空白闸（消融特征：abl_easel_density_gate）。建议级，不挡闸。

来源：Easel `skills/openclaw/card-design/references/layout-laws.md`（内容填充 ≥75% 画高、
死空白带 >15% 高度判 fail、纵向 4 带自检）+ `card-design/scripts/card_audit.py`
（行边缘密度算法：横向梯度 > 阈值判"该行有内容"，比背景色差鲁棒）。

输入：qa/metric-frames/*.jpg（s6_frame_metrics 的抽帧产物；缺失时从成片 ffmpeg 抽帧）。
输出：qa/density-report.json + stdout 摘要。纯 numpy/PIL，确定性。

用法: s6_density_gate.py <job_dir> [--grad-thresh 12] [--fill-min 0.60] [--dead-max 0.22]
（阈值默认放宽到 advisory 档：layout-laws 原值是"卡片"标准，成片含字幕带/留白构图，先观测再收紧）
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent


def ensure_frames(job: Path, want: int = 24) -> list[Path]:
    """metric-frames 缺失时从成片均匀抽帧。"""
    frames_dir = job / "qa" / "metric-frames"
    frames = sorted(frames_dir.glob("*.jpg"))
    if frames or not (job / "out" / "video-final.mp4").exists():
        return frames
    frames_dir.mkdir(parents=True, exist_ok=True)
    out = job / "out" / "video-final.mp4"
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.strip() or 0)
    if dur <= 0:
        return []
    step = max(1.0, dur / want)
    t = 0.5
    while t < dur:
        f = frames_dir / f"auto-{int(t * 10):05d}.jpg"
        subprocess.run(["ffmpeg", "-y", "-ss", str(t), "-i", str(out), "-frames:v", "1", "-q:v", "3", str(f)],
                       capture_output=True)
        t += step
    return sorted(frames_dir.glob("*.jpg"))


def analyze(path: Path, grad_thresh: int = 12, row_frac: float = 0.003) -> dict:
    """单帧行密度：横向梯度 > 阈值的行 = 有内容行（card_audit 算法）。
    row_frac：行内边缘像素占比阈值。白卡深底构图中，卡左右描边也占行 —— 阈值需低于
    卡边 2~4 列 / 帧宽（≈0.004），否则卡内部行被误判空白（首版 0.02 导致 44/44 全 fail 的教训）。"""
    img = np.asarray(Image.open(path).convert("L"), dtype=np.float32)
    h, w = img.shape
    gx = np.abs(np.diff(img, axis=1))  # 横向梯度
    row_activity = (gx > grad_thresh).mean(axis=1)  # 每行"有边缘的像素占比"
    content_rows = row_activity > row_frac  # 行内边缘占比达标 = 有内容
    fill = float(content_rows.mean())
    # 最长连续空白带
    max_dead = cur = 0
    for r in content_rows:
        cur = 0 if r else cur + 1
        max_dead = max(max_dead, cur)
    max_dead_ratio = max_dead / h
    bottom_dead_ratio = float((~content_rows[int(h * 0.8):]).mean())
    return {
        "frame": path.name,
        "fill_ratio": round(fill, 3),
        "max_dead_band": round(max_dead_ratio, 3),
        "bottom_dead": round(bottom_dead_ratio, 3),
        "fail": fill < 0.60 or max_dead_ratio > 0.22,
    }


def run(job: Path, grad_thresh: int = 12, row_frac: float = 0.003) -> dict:
    frames = ensure_frames(job)
    if not frames:
        return {"available": False, "note": "无抽帧也无成片，密度闸跳过"}
    rows = [analyze(f, grad_thresh, row_frac) for f in frames]
    fails = [r for r in rows if r["fail"]]
    rep = {
        "feature": "abl_easel_density_gate",
        "blocking": False,
        "frames": len(rows),
        "fill_median": round(float(np.median([r["fill_ratio"] for r in rows])), 3),
        "max_dead_median": round(float(np.median([r["max_dead_band"] for r in rows])), 3),
        "fail_frames": len(fails),
        "fail_detail": fails[:8],
        "note": "layout-laws 卡片口径（fill≥0.75/dead≤0.15）对成片偏严，默认 advisory 阈值 fill≥0.60/dead≤0.22，观测后校准",
    }
    out = job / "qa" / "density-report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=1), "utf-8")
    print(f"[density-gate] 帧 {rep['frames']} | fill 中位 {rep['fill_median']} | 死带中位 {rep['max_dead_median']} | fail {rep['fail_frames']} → {out.name}")
    return rep


def main() -> None:
    job = Path(sys.argv[1]).resolve()
    grad = int(sys.argv[sys.argv.index("--grad-thresh") + 1]) if "--grad-thresh" in sys.argv else 12
    run(job, grad)


if __name__ == "__main__":
    main()
