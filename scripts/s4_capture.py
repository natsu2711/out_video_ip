#!/usr/bin/env python3
"""S4 扩展：Playwright 网页实拍 —— 截图 / 录屏（资讯/教程类证据镜头）。

能力吸收：screen_capture（talkcraft broll-sources 实测范式：新闻类话题
Playwright 实时截图比泛用 B-roll 更有信息量；mock 假 UI 被真图规则禁止）。

用法:
  s4_capture.py screenshot <job_dir> <shot_id> <url> [--full-page] [--wait 2.0] [--scroll 0]
  s4_capture.py record    <job_dir> <shot_id> <url> [--seconds 8] [--scroll-steps 3] [--wait 1.5]

产物:
  screenshot → job/assets/screenshots/<shot_id>.png + manifest.screenshots[shot_id]
  record     → job/assets/broll/<shot_id>.mp4     + manifest.broll_videos[shot_id]
登录态页面暂不支持（fresh context）；接入 ego-browser 属后续 adapter（接口已留）。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_manifest(job: Path) -> dict:
    p = job / "assets" / "manifest.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"version": "1.0", "ip_images": {}, "broll_videos": {}, "screenshots": {}, "bgm": None}


def _save_manifest(job: Path, m: dict) -> None:
    (job / "assets" / "manifest.json").parent.mkdir(parents=True, exist_ok=True)
    (job / "assets" / "manifest.json").write_text(
        json.dumps(m, ensure_ascii=False, indent=2), "utf-8"
    )


def do_screenshot(job: Path, shot_id: str, url: str, full: bool, wait: float, scroll: int) -> Path:
    from playwright.sync_api import sync_playwright

    out_dir = job / "assets" / "screenshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{shot_id}.png"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": 1920, "height": 1080}, device_scale_factor=2
        )
        page = ctx.new_page()
        page.goto(url, wait_until="networkidle", timeout=30_000)
        page.wait_for_timeout(int(wait * 1000))
        if scroll:
            page.mouse.wheel(0, scroll)
            page.wait_for_timeout(800)
        page.screenshot(path=str(out), full_page=full)
        browser.close()
    m = _load_manifest(job)
    m.setdefault("screenshots", {})[shot_id] = str(out.relative_to(job))
    _save_manifest(job, m)
    print(f"[s4-capture] 截图 → {out}")
    return out


def do_record(job: Path, shot_id: str, url: str, seconds: float, steps: int, wait: float) -> Path:
    from playwright.sync_api import sync_playwright

    out_dir = job / "assets" / "broll"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / f"_raw_{shot_id}"
    raw_dir.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(raw_dir),
            record_video_size={"width": 1920, "height": 1080},
        )
        page = ctx.new_page()
        page.goto(url, wait_until="networkidle", timeout=30_000)
        page.wait_for_timeout(int(wait * 1000))
        # 慢速滚动制造"浏览网页"的运镜感：steps 次滚轮，均匀铺满时长
        interval = max(0.3, (seconds - wait) / max(1, steps))
        for _ in range(steps):
            page.mouse.wheel(0, 420)
            page.wait_for_timeout(int(interval * 1000))
        ctx.close()  # close 后视频才落盘
        browser.close()
    webm = next(raw_dir.glob("*.webm"))
    out = out_dir / f"{shot_id}.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(webm), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(out)],
        check=True,
    )
    webm.unlink()
    raw_dir.rmdir()
    m = _load_manifest(job)
    m.setdefault("broll_videos", {})[shot_id] = {"path": str(out.relative_to(job)), "kind": "screen_recording"}
    _save_manifest(job, m)
    print(f"[s4-capture] 录屏 → {out}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("screenshot")
    ps.add_argument("job_dir")
    ps.add_argument("shot_id")
    ps.add_argument("url")
    ps.add_argument("--full-page", action="store_true")
    ps.add_argument("--wait", type=float, default=2.0)
    ps.add_argument("--scroll", type=int, default=0)

    pr = sub.add_parser("record")
    pr.add_argument("job_dir")
    pr.add_argument("shot_id")
    pr.add_argument("url")
    pr.add_argument("--seconds", type=float, default=8.0)
    pr.add_argument("--scroll-steps", type=int, default=3)
    pr.add_argument("--wait", type=float, default=1.5)

    a = ap.parse_args()
    job = Path(a.job_dir).resolve()
    if a.cmd == "screenshot":
        do_screenshot(job, a.shot_id, a.url, a.full_page, a.wait, a.scroll)
    else:
        do_record(job, a.shot_id, a.url, a.seconds, a.scroll_steps, a.wait)


if __name__ == "__main__":
    main()
