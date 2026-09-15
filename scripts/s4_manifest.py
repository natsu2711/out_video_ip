#!/usr/bin/env python3
"""S4：生成 assets/manifest.json（A-roll IP 图映射 + 逐镜场景图）。
用法: s4_manifest.py <job_dir>

素材约定（assets/ip-placeholder/）：
  ip三视图.jpg / ip.jpg   主图（角色三视图，A-roll 回退用）
  ip<数字>.jpg            逐镜场景图（ip00.jpg、ip01.jpg…），按序号分配给
                          storyboard 中 A-roll 镜头的出场顺序；不足时回退主图
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    job = Path(sys.argv[1])
    sb = json.loads((job / "storyboard.json").read_text(encoding="utf-8"))

    manifest_path = job / "assets" / "manifest.json"
    old = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

    # 本人 IP 姿态池（assets/ip/ 下任意图片，文件名=姿态名；规范名 idle/point/… 优先）
    poses: dict[str, str] = {}
    my_ip = ROOT / "assets" / "ip"
    if my_ip.exists():
        for f in sorted(my_ip.iterdir()):
            if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                poses[f.stem] = str(f)

    ip_dir = ROOT / "assets" / "ip-placeholder"
    main_img = None
    scenes = []
    if poses:
        # 本人 IP 优先：姿态池即主图池
        pool = sorted(poses.values())
        main_img = pool[0]
        scenes = [Path(p) for p in pool]
    else:
        for cand in ("ip三视图.jpg", "ip.jpg"):
            if (ip_dir / cand).exists():
                main_img = str(ip_dir / cand)
                break
        scenes = sorted(
            [f for f in ip_dir.glob("ip*.jpg") if re.search(r"ip\d+", f.name)],
            key=lambda f: int(re.search(r"ip(\d+)", f.name).group(1)),
        )

    # 逐镜场景图：按序分配给 A-roll 镜头出场序
    a_roll_ids = [s["id"] for s in sb["shots"] if s["roll"] == "A"]
    ip_scenes = {sid: str(scenes[i]) for i, sid in enumerate(a_roll_ids) if i < len(scenes)}

    manifest = {
        "version": "1.0",
        "ip_images": ({"three_view": main_img} if main_img else {}),
        "ip_scenes": ip_scenes,
        "ip_poses": poses,
        "bgm": old.get("bgm"),
        "sfx": old.get("sfx", []),
        # 合并保留既有登记（broll_videos/screenshots…）——重跑不清库
        **{k: v for k, v in old.items()
           if k not in ("version", "ip_images", "ip_scenes", "ip_poses", "bgm", "sfx")},
    }
    out = job / "assets" / "manifest.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), "utf-8")
    print(f"[s4-manifest] → {out} (主图={'有' if main_img else '无'} + {len(ip_scenes)}张逐镜场景图 + {len(poses)}张姿态切图)")


if __name__ == "__main__":
    main()
