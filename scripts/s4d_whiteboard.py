#!/usr/bin/env python3
"""S4D：白板动画镜头生产（whiteboard-animator 吸收链的执行端）。

对 B-roll 镜头：assets/broll/{shot_id}.png 有源图 → whiteboard-animate 生成手绘动画
→ manifest.broll_videos 登记 → S5 渲染时自动升级 RealFootage 消费。
无源图的镜头 → 提示先完成生图（s4b 任务单 → 生图 → 存 target_path）再重跑本脚本。

用法: s4d_whiteboard.py <job_dir>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.adapters import registry  # noqa: E402


def main() -> None:
    job = Path(sys.argv[1]).resolve()
    sb = json.loads((job / "storyboard.json").read_text(encoding="utf-8"))

    adapters = registry.by_capability("video_render")
    if not adapters:
        print("[s4d] ⚠ whiteboard-animator 不可用（.venv/bin/pip install whiteboard-animator），跳过")
        return
    ad = adapters[0]
    print(f"[s4d] 渲染器: {ad.name}（{ad.available()[1]}）")

    manifest_path = job / "assets" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest.setdefault("broll_videos", {})

    made = tasks = 0
    for s in sb["shots"]:
        if s["roll"] != "B" or s["recipe_ref"] in ("TitleCard", "EndingCard"):
            continue
        if s["id"] in manifest["broll_videos"]:
            continue  # 已有素材（含 stock footage）不覆盖
        src = job / "assets" / "broll" / f"{s['id']}.png"
        if not src.exists():
            tasks += 1
            continue
        dur = (s["time"]["end_ms"] - s["time"]["start_ms"]) / 1000
        out = job / "assets" / "broll_videos" / f"{s['id']}.mp4"
        try:
            ad.produce({"image": src, "duration_s": dur}, out)
            manifest["broll_videos"][s["id"]] = {
                "path": f"assets/broll_videos/{s['id']}.mp4",
                "provider": ad.name, "duration": round(dur, 2),
                "keywords": ["whiteboard"],
            }
            made += 1
            print(f"[s4d] ✓ {s['id']}: 白板动画 {dur:.1f}s")
        except Exception as e:  # noqa: BLE001 单镜失败不拖垮全片
            print(f"[s4d] ✗ {s['id']}: {e}")

    if made:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), "utf-8")
    print(f"[s4d] 完成 {made} 镜白板动画；{tasks} 镜缺源图（先按 s4b 任务单生图到 assets/broll/ 再重跑）")


if __name__ == "__main__":
    main()
