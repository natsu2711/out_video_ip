#!/usr/bin/env python3
"""主题色应用工具：根据 project.style.theme 自动更新 b_roll.palette。
用法: apply_theme.py <job_dir>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.theme_tokens import get_theme  # noqa: E402


def main() -> None:
    job = Path(sys.argv[1])
    proj = json.loads((job / "project.json").read_text(encoding="utf-8"))
    theme_id = proj.get("style", {}).get("theme", "ikb")
    theme = get_theme(theme_id)

    # 自动更新 b_roll.palette
    if "b_roll" not in proj["style"]:
        proj["style"]["b_roll"] = {}
    proj["style"]["b_roll"]["palette"] = {
        "bg": theme["bg"],
        "anchor": theme["anchor"],
        "text": theme["text"],
    }

    (job / "project.json").write_text(json.dumps(proj, ensure_ascii=False, indent=2), "utf-8")
    print(f"[apply-theme] 已应用主题: {theme['name']} (bg={theme['bg']}, anchor={theme['anchor']})")


if __name__ == "__main__":
    main()