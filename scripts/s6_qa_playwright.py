#!/usr/bin/env python3
"""S6 QA 扩展：Playwright 真实渲染测量（guizang-social-card-skill 9 条规则）
用法: s6_qa_playwright.py <job_dir>
"""
from __future__ import annotations

import json
import sys
import asyncio
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("[qa-playwright] Playwright 未安装，跳过此模块")
    sys.exit(0)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# 9 条规则（从 guizang-social-card-skill 适配到视频）
RULES = {
    "R1_Overflow": "任何元素超出画布边界",
    "R2_Footer_Collision": "内容压到底部 footer 或页码",
    "R3_Bold_Display_Exceed": "大标题违反'越大越细'原则",
    "R4_Min_Readable_Font": "正文/说明/标签字号低于手机可读下限",
    "R5_4Band_Density": "1920 高画布切 4 横带，每带应有内容或主动留白理由",
    "R6_H_XL_Line_Cap": "超大标题行数超出画板预算",
    "R7_Figure_Margin_Drift": "浏览器默认 <figure> margin 造成版式漂移",
    "R8_Visual_Bounds": "真实可见内容的上/下边界报告",
    "R9_Title_Gap": "标题与下一块内容距离过小",
}


async def check_shot(shot_id: str, segment_video: Path) -> dict:
    """对单个镜头片段运行 9 条规则（简化版：只检测可见内容边界）"""
    result = {rule: False for rule in RULES}
    notes = []

    # R8_Visual_Bounds：用 ffprobe 检测视频有效内容边界（简化版）
    import subprocess

    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "frame=width,height",
            "-of",
            "json",
            str(segment_video),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        meta = json.loads(proc.stdout)
        width = int(meta["streams"][0]["width"])
        height = int(meta["streams"][0]["height"])
        notes.append(f"R8_Visual_Bounds: {width}x{height} 视频尺寸")
        result["R8_Visual_Bounds"] = True

    # 其他规则需要 HTML 渲染测量（暂留桩，M2+ 实现）
    notes.append("R1-R7 需要对应镜头的 HTML 版本进行 Playwright 测量（M2+ 实现）")

    return {shot_id: {"passed": all(result.values()), "details": result, "notes": notes}}


async def main() -> None:
    job = Path(sys.argv[1])

    # 查找所有镜头片段
    segments_dir = job / "render" / "segments"
    segments = list(segments_dir.glob("S*.mp4"))

    if not segments:
        print("[qa-playwright] 无镜头片段，跳过")
        return

    print(f"[qa-playwright] 检测到 {len(segments)} 个镜头片段")

    async with async_playwright() as p:
        results = {}
        for seg in segments:
            shot_id = seg.stem
            result = await check_shot(shot_id, seg)
            results.update(result)
            passed = result[shot_id]["passed"]
            print(f"  {shot_id}: {'✓ 通过' if passed else '✗ 未过'} ({len(result[shot_id]['notes'])} 条)")

    # 生成报告
    report_path = job / "qa" / "playwright-report.json"
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), "utf-8")
    print(f"[qa-playwright] → {report_path}")


if __name__ == "__main__":
    asyncio.run(main())