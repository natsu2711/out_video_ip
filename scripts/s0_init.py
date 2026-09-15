#!/usr/bin/env python3
"""S0: 初始化 job 目录 + project.json。
用法: s0_init.py <job_root> <slug> <title> [--story <文案文件>]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.validate import require  # noqa: E402

TEMPLATE = {
    "pipeline_version": "1.0",
    "canvas": {"width": 1920, "height": 1080, "fps": 30, "ratio": "16:9"},
    "language": "zh",
    "voice": {
        "provider": "index-tts",
        "ref_audio": "/Users/bainazi/Documents/outtt/other/1other_video/index-tts/examples/voice_02.wav",
        "speed": 1.0,
    },
    "style": {
        "theme": "ink-classic",
        "a_roll": {
            "engine": "ip-image",
            "style_lock": "白底简笔小剧场，圆润白色小人，头顶绿色豆芽，黑点眼，粗净线稿，扁平色彩",
            "reference_images": {
                "three_view": "assets/ip-placeholder/ip-three-view_00001_.png",
                "brush_detail": "assets/ip-placeholder/ip-brush-detail_00001_.png",
                "scene": "assets/ip-placeholder/ip-scene_00001_.png",
            },
            "view_angles": ["host", "protagonist", "supporting", "pov"],
        },
        "b_roll": {
            "palette": {"bg": "#0A0A0A", "anchor": "#7C5CFF", "text": "#FFFFFF"},
            "font_stack": ["Source Han Sans CN Bold", "PingFang SC"],
        },
    },
    "bgm": {"mood": "轻快快节奏", "duck_to_db": -14, "file": None},
    "i2v": {"enabled": False},
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("job_root")
    ap.add_argument("slug")
    ap.add_argument("title")
    ap.add_argument("--story")
    args = ap.parse_args()

    job_id = time.strftime("%Y-%m%d-") + args.slug
    job_dir = Path(args.job_root) / job_id
    if job_dir.exists():
        print(f"[s0] job 已存在: {job_dir}")
        sys.exit(1)
    for sub in ["audio", "assets", "render/segments", "out", "qa", "docs"]:
        (job_dir / sub).mkdir(parents=True, exist_ok=True)

    proj = {"id": job_id, "title": args.title, **TEMPLATE}
    (job_dir / "project.json").write_text(json.dumps(proj, ensure_ascii=False, indent=2), "utf-8")

    # 占位 IP 参考图复制进 job（正式 IP 到位后替换 job 内三张图即可）
    ip_src = ROOT / "assets/ip-placeholder"
    ip_dst = job_dir / "assets/ip-placeholder"
    if ip_src.exists():
        shutil.copytree(ip_src, ip_dst, dirs_exist_ok=True)

    if args.story:
        shutil.copy(args.story, job_dir / "story.md")
        print(f"[s0] 文案已放入: {job_dir/'story.md'}")

    require("project", job_dir / "project.json")
    from pipeline.state import set_stage
    set_stage(job_dir, "s0", "done", "initialized")
    print(f"[s0] OK → {job_dir}")


if __name__ == "__main__":
    main()
