#!/usr/bin/env python3
"""sc- 卡路径修复（幂等）：把移植卡的相对引用统一改到 cards 内的 _sc_assets/_sc。
在 import_shotcraft.py 之后跑（或重新移植后重跑）。"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "render-engine" / "src" / "cards"
LIB = Path("/Users/bainazi/Documents/outtt/other/1other_video/video-shotcraft/assets/lib")
DEMOS = Path("/Users/bainazi/Documents/outtt/other/1other_video/video-shotcraft/demos")

def main() -> None:
    # 1) 资源文件齐备
    assets = CARDS / "_sc_assets"
    assets.mkdir(exist_ok=True)
    n = 0
    for p in list(DEMOS.rglob("*")) + list(LIB.glob("*")):
        if p.suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp', '.mp4', '.json'):
            d = assets / p.name
            if not d.exists():
                shutil.copy(p, d)
                n += 1
    for name in ('VerticalTicker', 'ClipCard', 'Caption', 'FlashCut', 'DigitRoll', 'FlatPanel', 'PageCam'):
        s = LIB / f'{name}.tsx'
        d = assets / f'{name}.tsx'
        if s.exists() and not d.exists():
            d.write_text(s.read_text(encoding='utf-8').replace("from './helpers/", "from '../_sc/helpers/"), encoding='utf-8')
            n += 1
    print(f'资源补齐 {n}')

    # 2) 路径改写（幂等）
    fixed = 0
    for card in CARDS.glob('card-sc-*.tsx'):
        src = card.read_text(encoding='utf-8')
        orig = src
        src = re.sub(r"from '(\./|\.\./)+_?(?:textures/)?([^'/]+\.(?:jpg|jpeg|png|webp|mp4|json))'",
                     r"from './_sc_assets/\2'", src)
        src = re.sub(r"from '(\.\./)+assets/lib/(\w+)'", r"from './_sc_assets/\2'", src)
        src = src.replace("from './VerticalTicker'", "from './_sc_assets/VerticalTicker'")
        src = src.replace("from './ClipCard'", "from './_sc_assets/ClipCard'")
        src = re.sub(r"from '(\./_sc_assets/)+", "from './_sc_assets/", src)  # 去重复前缀
        if src != orig:
            card.write_text(src, encoding='utf-8')
            fixed += 1
    print(f'路径修复 {fixed} 张')

if __name__ == '__main__':
    main()
