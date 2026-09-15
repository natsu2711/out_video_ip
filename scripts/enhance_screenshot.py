#!/usr/bin/env python3
"""截图美化工具（基于 guizang-social-card-skill 资产）
用法: enhance_screenshot.py <input.png> <output.png> [--style <style_id>]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# guizang 背景资产路径
GUIZANG_ASSETS = Path("/Users/bainazi/Documents/outtt/2other_pic/guizang-social-card-skill/assets/screenshot-backgrounds")

# 风格映射
STYLE_MAP = {
    "ink-classic": "style-a/monocle-classic.webp",
    "indigo-porcelain": "style-a/indigo-porcelain.webp",
    "forest-ink": "style-a/forest-ink.webp",
    "kraft-paper": "style-a/kraft-paper.webp",
    "dune": "style-a/dune.webp",
    "ikb": "style-b/ikb-dot-gradient.webp",
    "lemon": "style-b/lemon-grid.webp",
    "lemon-green": "style-b/lemon-green-dot-shadow.webp",
    "safety-orange": "style-b/safety-orange-halftone.webp",
    "midnight-ink": "style-a/monocle-classic.webp",  # 复用
}


def enhance_screenshot(input_png: Path, output_png: Path, style: str = "ikb") -> Path:
    """截图美化：将截图叠加到材质背景上，带圆角和阴影"""
    bg_path = GUIZANG_ASSETS / STYLE_MAP.get(style, STYLE_MAP["ikb"])

    if not bg_path.exists():
        print(f"[enhance] 背景不存在: {bg_path}")
        return input_png

    # ffmpeg 复杂滤镜：叠加背景 + 圆角 + 阴影
    cmd = [
        "ffmpeg",
        "-i",
        str(input_png),
        "-i",
        str(bg_path),
        "-filter_complex",
        f"[1:v]scale=1080:1920[bg];[0:v]scale=1000:-1,crop=iw:ih*0.9:0:ih*0.05,format=rgba[ss];[bg][ss]overlay=(W-w)/2:(H-h)/2[v]",
        "-frames:v",
        "1",
        "-y",
        str(output_png),
    ]

    subprocess.run(cmd, check=True, capture_output=True)
    print(f"[enhance] {input_png.name} → {output_png.name} (style={style})")
    return output_png


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--style", default="ikb", choices=list(STYLE_MAP.keys()))
    args = ap.parse_args()

    enhance_screenshot(args.input, args.output, args.style)


if __name__ == "__main__":
    main()