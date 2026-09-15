#!/usr/bin/env python3
"""S3 编排表渲染：storyboard.json → docs/storyboard-table.md（闸门审阅用，一屏可决策）。
用法: s3_table.py <job_dir>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROLL_BADGE = {"A": "🅰️ 人物", "B": "🅱️ 图形"}


def main() -> None:
    job = Path(sys.argv[1])
    sb = json.loads((job / "storyboard.json").read_text(encoding="utf-8"))
    rc = sb.get("rhythm_check", {})
    lines = [
        f"# 视觉编排表 · {sb['job_id']}",
        "",
        f"镜头 {len(sb['shots'])} 个 | A/B 配比 {rc.get('a_b_ratio', [])} | **审阅方式：改口径直接回复镜头号+意见**",
        "",
        "| 镜头 | 时间 | 配音文案 | 类型 | 画面设计 | 动态变化 | 衔接 | 配方 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for sh in sb["shots"]:
        t = sh["time"]
        ts = f"{t['start_ms']/1000:.1f}-{t['end_ms']/1000:.1f}s"
        typ = ROLL_BADGE[sh["roll"]]
        if sh["roll"] == "B":
            typ += f"/{sh.get('b_type', '?')}"
        elif sh.get("view_angle"):
            typ += f"/{sh['view_angle']}"
        motion = "<br>".join(f"{i+1}. {m}" for i, m in enumerate(sh.get("motion", [])))
        needs = sh.get("assets_needed") or []
        need_mark = f"<br>⚠️需素材: {'; '.join(needs)}" if needs else ""
        recipe = sh["recipe_ref"].split(":", 1)[-1]
        if sh.get("degraded"):
            recipe += " ⚠️保底王"
        lines.append(
            f"| {sh['id']} | {ts} | {sh['vo'][:38]}{'…' if len(sh['vo'])>38 else ''} "
            f"| {typ} | {sh['visual']}{need_mark} | {motion} | {sh.get('transition_in','—')} | {recipe} |"
        )
    out = job / "docs" / "storyboard-table.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines), "utf-8")
    print(f"[s3-table] → {out} ({len(sb['shots'])} shots)")


if __name__ == "__main__":
    main()
