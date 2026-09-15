#!/usr/bin/env python3
"""S6 QA：机器验收（每条规则都可复算，减少环节方差）。

规则（任一失败 → exit 1，pipeline 卡在 s6 failed）：
  R1 冻结段检测（freezedetect，总冻结时长≤5s，d=2.5 只抓真死帧段）
  R2 音频响度：成片 mean_volume > -35dB 且 max_volume > -15dB（VO 必须可闻）
  R3 时长对齐：成片时长 vs timing.json duration_ms 偏差 < 800ms
  R4 A-roll 图像存在性：每个 A-roll 镜头中点帧，IP 白底图亮像素（>200）占比 ≥ 3%
  R5 字幕存在性：每个镜头中点帧，字幕带（y 78%~92%）亮像素（>150）≥ 150 个
输出 qa/report.json（逐条 pass/fail + 证据数值）。

另生成：
  - qa/contact-sheet.html：帧 + 镜号 + 时间 + VO/画面描述（人工目检入口）
  - qa/frame-metrics-report.{json,md}：逐镜主体/空场/柔光/杂讯/静止建议
"""
from __future__ import annotations

import html
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from s6_frame_metrics import run_metrics  # noqa: E402


def probe_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(r.stdout)["format"]["duration"])


def volume_stats(video: Path) -> tuple[float, float]:
    r = subprocess.run(
        ["ffmpeg", "-i", str(video), "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    mean = mx = -99.0
    for line in r.stderr.splitlines():
        if "mean_volume" in line:
            mean = float(line.split("mean_volume:")[1].replace("dB", "").strip())
        if "max_volume" in line:
            mx = float(line.split("max_volume:")[1].replace("dB", "").strip())
    return mean, mx


def volume_stats_window(video: Path, start: float, end: float) -> tuple[float, float]:
    r = subprocess.run(
        ["ffmpeg", "-ss", str(start), "-t", str(end - start), "-i", str(video),
         "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    mean = -99.0
    for line in r.stderr.splitlines():
        if "mean_volume" in line:
            mean = float(line.split("mean_volume:")[1].replace("dB", "").strip())
    return mean, -99.0


def detect_freeze(video: Path) -> float:
    """freezedetect（d=2.5s 起，n=0.3% 人眼可感知阈）：返回总冻结时长（秒）。
    口径校准说明：n=0.003 是逐帧均值差阈（0.77/255），慢速推拉/悬浮的逐帧差
    必然低于它（实测正常漂移片也被判冻），故用 d=2.5 只抓真死帧段（渲染卡死、
    组件不动画）；正常片实测 ≈3s，历史无全局运动片 ≈30s+，阈值 5s 有区分度。"""
    r = subprocess.run(
        ["ffmpeg", "-i", str(video), "-vf", "freezedetect=n=0.003:d=2.5", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    total = 0.0
    for line in r.stderr.splitlines():
        if "freeze_duration" in line:
            try:
                total += float(line.split("freeze_duration:")[1].strip())
            except ValueError:
                pass
    return total


def shot_mid_frame(video: Path, mid_s: float, out: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-ss", str(max(0.0, mid_s)), "-i", str(video),
         "-frames:v", "1", "-update", "1", str(out)],
        capture_output=True, check=True,
    )


def bright_ratio(img: Path, y0: int, y1: int, thresh: int) -> float:
    import numpy as np
    from PIL import Image
    a = np.array(Image.open(img).convert("L"))
    region = a[int(a.shape[0] * y0):int(a.shape[0] * y1)]
    return float((region > thresh).sum()) / region.size


def shot_at(shots: list[dict], time_s: float) -> dict:
    time_ms = time_s * 1000.0
    def distance(shot: dict) -> float:
        start = float(shot["time"]["start_ms"])
        end = float(shot["time"]["end_ms"])
        return max(start - time_ms, 0.0, time_ms - end)

    # Prefer the storyboard interval; use the nearest shot only for timeline gaps.
    for shot in shots:
        if int(shot["time"]["start_ms"]) <= time_ms < int(shot["time"]["end_ms"]):
            return shot
    return min(shots, key=distance) if shots else {}


def contact_html(video: Path, frames: list[tuple[float, Path]], shots: list[dict]) -> str:
    cards = []
    for time_s, path in frames:
        shot = shot_at(shots, time_s)
        shot_id = shot.get("id", "UNKNOWN")
        vo = shot.get("vo", "")
        visual = shot.get("visual", "")
        recipe = shot.get("recipe_ref", "")
        cards.append(f"""
          <figure>
            <img src="{path.name}" alt="{html.escape(shot_id)} at {time_s:g}s" loading="lazy">
            <figcaption>
              <strong>{html.escape(shot_id)}</strong>
              <span>{time_s:.1f}s · {html.escape(str(recipe))}</span>
              <p>{html.escape(vo)}</p>
              <small>{html.escape(visual)}</small>
            </figcaption>
          </figure>""")
    return f"""<!doctype html>
<html lang="zh-CN">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Contact sheet — {html.escape(video.parent.parent.name)}</title>
<style>
  :root {{ color-scheme: dark; font: 14px/1.45 system-ui, sans-serif; }}
  body {{ margin: 0; background: #101014; color: #f3f3f2; }}
  header {{ padding: 18px 20px 8px; }}
  h1 {{ margin: 0; font-size: 18px; }}
  header p {{ margin: 5px 0 0; color: #b8b8b4; }}
  main {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 14px; padding: 16px 20px 28px; }}
  figure {{ margin: 0; overflow: hidden; border: 1px solid #34343a; border-radius: 6px; background: #191920; }}
  img {{ display: block; width: 100%; aspect-ratio: 16 / 9; object-fit: cover; }}
  figcaption {{ padding: 10px 12px; display: grid; gap: 4px; }}
  span {{ color: #a9a9a4; font-size: 12px; }}
  p {{ margin: 0; }}
  small {{ color: #91918d; }}
</style>
<header>
  <h1>S6 contact sheet</h1>
  <p>{len(frames)} frames · {html.escape(str(video))}</p>
</header>
<main>{''.join(cards)}</main>
</html>
"""


def render_sheet_image(frames: list[tuple[float, Path]], out: Path) -> None:
    """Small offline-readable fallback; HTML is the primary review surface."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        if frames:
            subprocess.run(["cp", frames[-1][1], out], check=True)
        return
    if not frames:
        return
    columns = 3
    thumb_w, thumb_h, caption_h = 320, 180, 26
    rows = (len(frames) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * thumb_w, rows * (thumb_h + caption_h)), "#101014")
    draw = ImageDraw.Draw(sheet)
    for index, (time_s, path) in enumerate(frames):
        x = (index % columns) * thumb_w
        y = (index // columns) * (thumb_h + caption_h)
        try:
            with Image.open(path) as image:
                image.thumbnail((thumb_w, thumb_h))
                sheet.paste(image, (x + (thumb_w - image.width) // 2, y))
        except OSError:
            continue
        draw.text((x + 8, y + thumb_h + 6), f"{time_s:.0f}s", fill="#e6e6e2")
    sheet.save(out, quality=90)


def main() -> None:
    import numpy as np  # noqa: F401  确认依赖存在

    job = Path(sys.argv[1]).resolve()
    video = job / "out" / "video-final.mp4"
    if not video.exists():
        print("[s6-qa] ✗ 找不到成片", file=sys.stderr)
        sys.exit(1)

    timing = json.loads((job / "timing.json").read_text(encoding="utf-8"))
    sb = json.loads((job / "storyboard.json").read_text(encoding="utf-8"))
    dur = probe_duration(video)

    rules: list[dict] = []
    qa_dir = job / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)

    # R1 冻结段（全局 Ken Burns + 微光漂移 + 组件悬浮保证运动；抓真死帧段）
    # 校准基线：无全局运动的历史片 ≈30s+ 冻结；正常片 ≈3s；阈值 5s
    freeze = detect_freeze(video)
    rules.append({"rule": "R1-freeze", "pass": freeze <= 5.0, "value": round(freeze, 2),
                  "expect": "总冻结时长 ≤ 5s（freezedetect n=0.003 d=2.5，只抓真死帧段）"})

    # R2 响度（VO 必须可闻——静音音轨事故防线）+ 分窗检查（防半段静音漏网）
    mean_v, max_v = volume_stats(video)
    rules.append({"rule": "R2-audio-mean", "pass": mean_v > -35, "value": mean_v, "expect": "> -35dB"})
    rules.append({"rule": "R2-audio-max", "pass": max_v > -15, "value": max_v, "expect": "> -15dB"})
    win_fail = []
    for ws in range(0, int(dur), 30):
        we = min(ws + 30, dur)
        if we - ws < 5:
            break
        wm, _ = volume_stats_window(video, ws, we)
        (wm > -35) or win_fail.append(f"{ws}-{we}s:{wm:.1f}dB")
    rules.append({"rule": "R2-audio-windows", "pass": not win_fail,
                  "value": f"fail={win_fail}", "expect": "每 30s 窗口 mean > -35dB"})

    # R3 时长对齐
    drift = abs(dur * 1000 - timing["duration_ms"])
    rules.append({"rule": "R3-duration", "pass": drift < 800, "value": drift,
                  "expect": "< 800ms vs timing.json"})

    # R4 A-roll 图像存在性 + R5 字幕存在性（逐镜头中点采样）
    aroll_fail, sub_fail = [], []
    with tempfile.TemporaryDirectory() as td:
        for shot in sb["shots"]:
            mid_s = (shot["time"]["start_ms"] + shot["time"]["end_ms"]) / 2000.0
            f = Path(td) / f"{shot['id']}.png"
            shot_mid_frame(video, mid_s, f)
            if shot["roll"] == "A":
                ratio = bright_ratio(f, 0.15, 0.75, 200)
                (ratio >= 0.03) or aroll_fail.append(shot["id"])
                if shot is sb["shots"][0]:
                    pass
            # 字幕带检查（字幕框位于 bottom:60、高≈110px → y 90%~97%）
            sub_ratio = bright_ratio(f, 0.90, 0.97, 150)
            (sub_ratio >= 0.0015) or sub_fail.append(shot["id"])

    rules.append({"rule": "R4-aroll-image", "pass": not aroll_fail,
                  "value": f"fail={aroll_fail}", "expect": "每个 A-roll 中点帧亮像素占比≥3%"})
    rules.append({"rule": "R5-subtitle", "pass": not sub_fail,
                  "value": f"fail={sub_fail}", "expect": "字幕带亮像素占比≥0.15%"})

    passed = all(r["pass"] for r in rules)
    freeze_total = freeze
    report = {
        "video": str(video),
        "duration_s": round(dur, 2),
        "rules": rules,
        "freeze_seconds": round(freeze_total, 2),
        "passed": passed,
    }
    (qa_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")

    # contact sheet（每 5 秒一帧；HTML 提供镜头/VO 上下文，JPG 是离线备选）
    frames: list[tuple[float, Path]] = []
    for t in [i * 5 for i in range(0, int(dur // 5) + 1)]:
        fp = qa_dir / f"frame_{t}s.jpg"
        subprocess.run(
            ["ffmpeg", "-y", "-ss", str(t), "-i", str(video), "-frames:v", "1",
             "-update", "1", str(fp)],
            capture_output=True, check=True,
        )
        frames.append((t, fp))
    sheet_path = qa_dir / "contact-sheet.jpg"
    render_sheet_image(frames, sheet_path)
    html_path = qa_dir / "contact-sheet.html"
    html_path.write_text(contact_html(video, frames, sb["shots"]), encoding="utf-8")

    try:
        report["aesthetic_qa"] = run_metrics(job)
    except Exception as exc:
        report["aesthetic_qa"] = {"status": "error", "blocking": False, "error": str(exc)}

    # density_gate（Easel layout-laws 行密度/死空白）：建议级，不挡闸
    try:
        sys.path.insert(0, str(ROOT))
        from scripts.s6_density_gate import run as density_run
        report["density_gate"] = density_run(job)
    except Exception as exc:
        report["density_gate"] = {"available": False, "blocking": False, "error": str(exc)}

    report["contact_sheet"] = str(sheet_path)
    report["contact_sheet_html"] = str(html_path)
    (qa_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")

    for r in rules:
        mark = "✓" if r["pass"] else "✗"
        print(f"[s6-qa] {mark} {r['rule']}: {r['value']}（期望 {r['expect']}）")
    aesthetic = report["aesthetic_qa"]
    print(f"[s6-qa] aesthetic: {aesthetic['status']}（non-blocking） → {qa_dir/'frame-metrics-report.md'}")
    dg = report.get("density_gate") or {}
    if dg.get("frames"):
        print(f"[s6-qa] density_gate: fill 中位 {dg.get('fill_median')} / fail 帧 {dg.get('fail_frames')}（non-blocking）")
    print(f"[s6-qa] {'ALL PASS' if passed else 'FAILED'} → {qa_dir/'report.json'}")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
