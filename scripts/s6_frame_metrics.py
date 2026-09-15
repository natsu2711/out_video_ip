#!/usr/bin/env python3
"""S6 aesthetic metrics: non-blocking per-shot visual review.

Adapted from anything2explainer's frame_metrics.py.  This version consumes the
IP pipeline's storyboard/timing contracts, samples shot-local frames, and is
canvas-agnostic (16:9 or 9:16).  Failures are advisories; s6_qa.py remains the
only hard visual/audio gate.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from statistics import median
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent


def ffprobe_size(video: Path) -> tuple[int, int]:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", str(video)],
        capture_output=True, text=True, check=True,
    )
    stream = json.loads(result.stdout)["streams"][0]
    return int(stream["width"]), int(stream["height"])


def extract_frame(video: Path, at_s: float, out: Path) -> bool:
    result = subprocess.run(
        ["ffmpeg", "-y", "-ss", f"{max(0.0, at_s):.3f}", "-i", str(video),
         "-frames:v", "1", "-update", "1", str(out)],
        capture_output=True, text=True,
    )
    return result.returncode == 0 and out.exists()


def safe_region(width: int, height: int) -> tuple[slice, slice]:
    """Exclude outer margins and the subtitle band, but keep the working zone."""
    vertical_inset = int(height * 0.075)
    bottom = height - int(height * (0.12 if width >= height else 0.09))
    return slice(vertical_inset, bottom), slice(int(width * 0.07), int(width * 0.93))


def image_features(path: Path) -> dict[str, float]:
    import numpy as np
    from PIL import Image
    from scipy import ndimage as ndi

    rgb = np.asarray(Image.open(path).convert("RGB")).astype(np.int32)
    height, width = rgb.shape[:2]
    ys, xs = safe_region(width, height)
    rgb = rgb[ys, xs]
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    luminance = (r * 299 + g * 587 + b * 114) // 1000
    bright = luminance > 120

    # Merge nearby glyphs so a headline is one object; isolated dots stay out.
    glyphs = ndi.binary_dilation(bright, structure=np.ones((9, 31), bool))
    labels, count = ndi.label(glyphs)
    object_sizes: list[float] = []
    small_objects = 0
    if count:
        ink = ndi.sum(bright, labels, index=np.arange(1, count + 1))
        for index, box in enumerate(ndi.find_objects(labels)):
            if box is None or ink[index] < 40:
                continue
            box_h = box[0].stop - box[0].start
            box_w = box[1].stop - box[1].start
            if box_h < 45 and box_w < 45:
                small_objects += 1
            # Wide cards/headlines count by compacted width; thin rules do not.
            object_sizes.append(max(box_h, min(box_w, 4 * box_h) / 2.5))

    chroma = rgb.max(axis=2) - rgb.min(axis=2)
    soft = (chroma > 25) & (luminance > 18) & (luminance < 120)
    empty = len(object_sizes) == 0 or max(object_sizes, default=0) < 80
    return {
        "hero_px": max(object_sizes, default=0.0),
        "object_count": len(object_sizes),
        "small_objects": small_objects,
        "clutter_score": min(100.0, len(object_sizes) * 4 + small_objects * 1.5),
        "glow_px": float(soft.sum()),
        "ink_ratio": float(bright.mean()),
        "empty": empty,
    }


def mean_abs_diff(previous: Path, current: Path) -> float:
    import numpy as np
    from PIL import Image

    def grey(path: Path) -> np.ndarray:
        return np.asarray(Image.open(path).convert("L").resize((320, 180))).astype(np.int32)

    return float(np.abs(grey(previous) - grey(current)).mean())


def sample_times(start_ms: int, end_ms: int) -> list[float]:
    duration = max(0.0, (end_ms - start_ms) / 1000.0)
    fractions = (0.30, 0.60, 0.90) if duration >= 3.0 else (0.50,)
    return [start_ms / 1000.0 + duration * fraction for fraction in fractions]


def flags_for(metrics: dict[str, Any], duration_s: float) -> list[str]:
    flags: list[str] = []
    if metrics["static_seconds"] > 1.5:
        flags.append("static-motion-low")
    if metrics["empty_ratio"] > 0.34:
        flags.append("empty-field")
    if metrics["hero_px_median"] < 140:
        flags.append("hero-small")
    if metrics["glow_px_median"] < 800:
        flags.append("focus-low")
    if metrics["clutter_score_median"] >= 65:
        flags.append("clutter-high")
    if duration_s > 18.0:
        flags.append("duration-long")
    return flags


def run_metrics(job: Path, samples_per_shot: int = 3) -> dict[str, Any]:
    """Generate reports; return a compact status suitable for qa/report.json."""
    video = job / "out" / "video-final.mp4"
    storyboard = json.loads((job / "storyboard.json").read_text(encoding="utf-8"))
    frames_dir = job / "qa" / "metric-frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    width, height = ffprobe_size(video)
    shots_out: list[dict[str, Any]] = []
    for shot in storyboard["shots"]:
        shot_id = shot["id"]
        times = sample_times(
            int(shot["time"]["start_ms"]), int(shot["time"]["end_ms"])
        )[:max(1, samples_per_shot)]
        paths: list[Path] = []
        for number, at_s in enumerate(times):
            path = frames_dir / f"{shot_id}-{number:02d}.jpg"
            if extract_frame(video, at_s, path):
                paths.append(path)

        features = [image_features(path) for path in paths]
        static_seconds = 0.0
        current_static = 0.0
        for index, (previous, current) in enumerate(zip(paths, paths[1:])):
            delta = mean_abs_diff(previous, current)
            current_static = (
                current_static + times[index + 1] - times[index]
                if delta < 0.15 else 0.0
            )
            static_seconds = max(static_seconds, current_static)

        def stat(key: str, caster=float) -> float:
            values = [caster(item[key]) for item in features]
            return round(median(values), 1) if values else 0.0

        duration_s = (int(shot["time"]["end_ms"]) - int(shot["time"]["start_ms"])) / 1000.0
        item: dict[str, Any] = {
            "shot_id": shot_id,
            "roll": shot.get("roll", "B"),
            "duration_s": round(duration_s, 2),
            "samples": len(features),
            "hero_px_median": stat("hero_px"),
            "object_count_median": stat("object_count", int),
            "small_objects_median": stat("small_objects", int),
            "clutter_score_median": stat("clutter_score"),
            "glow_px_median": stat("glow_px"),
            "ink_ratio_median": round(median([x["ink_ratio"] for x in features]), 4) if features else 0.0,
            "empty_ratio": round(sum(bool(x["empty"]) for x in features) / len(features), 2) if features else 1.0,
            "static_seconds": round(static_seconds, 2),
        }
        item["flags"] = flags_for(item, duration_s)
        item["status"] = "warn" if item["flags"] else "pass"
        shots_out.append(item)

    counts = {status: sum(x["status"] == status for x in shots_out) for status in ("pass", "warn")}
    report = {
        "version": "1.0",
        "source": str(video),
        "canvas": {"width": width, "height": height},
        "samples_per_shot": max(1, samples_per_shot),
        "blocking": False,
        "summary": {"shots": len(shots_out), **counts},
        "shots": shots_out,
    }
    (job / "qa" / "frame-metrics-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (job / "qa" / "frame-metrics-report.md").write_text(markdown_report(report), encoding="utf-8")
    return {
        "status": "ok",
        "blocking": False,
        "report": "qa/frame-metrics-report.json",
        "summary": report["summary"],
    }


def markdown_report(report: dict[str, Any]) -> str:
    canvas = report["canvas"]
    summary = report["summary"]
    lines = [
        "# S6 逐镜视觉量化（建议级）",
        "",
        f"来源：`{Path(report['source']).name}`；画布 `{canvas['width']}×{canvas['height']}`；"
        f"每镜采样 `{report['samples_per_shot']}` 次；不阻断 S6。",
        "",
        f"合计：pass {summary['pass']} / warn {summary['warn']} / shots {summary['shots']}。",
        "",
        "| 镜号 | 类型 | 时长s | 主体px | 空场比 | 柔光px² | 杂讯 | 最长静止s | 标记 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for shot in report["shots"]:
        lines.append(
            f"| {shot['shot_id']} | {shot['roll']} | {shot['duration_s']:.2f} | "
            f"{shot['hero_px_median']:.0f} | {shot['empty_ratio']:.2f} | "
            f"{shot['glow_px_median']:.0f} | {shot['clutter_score_median']:.0f} | "
            f"{shot['static_seconds']:.2f} | {', '.join(shot['flags']) or 'OK'} |"
        )
    lines.extend([
        "",
        "判据：主体中位数 <140px；空场样本 >34%；柔光 <800px²；杂讯 ≥65；静止 >1.5s。",
        "这些阈值用于暴露返工风险，最终仍需人工对照 contact sheet。",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("job", type=Path)
    parser.add_argument("--samples", type=int, default=3)
    args = parser.parse_args()
    result = run_metrics(args.job.resolve(), args.samples)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
