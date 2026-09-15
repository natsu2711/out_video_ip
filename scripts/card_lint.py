#!/usr/bin/env python3
"""card_lint：移植卡保真闸（拆自 talkcraft card_lint 思想——"凭卡名手写神似版"是最大翻车源）。

规则（对 storyboard.json 中每个 card:<slug>）：
  L1 卡文件存在：render-engine/src/cards/card-<slug>.tsx
  L2 注册表在册：registry.json 有 slug
  L3 已接线：tier == injectable（raw 卡文案是 demo 原文，禁止进自动分镜）
  L4 时长合理：卡时长 ≤ 镜头帧数（超出部分 Freeze 定格，仅提示）
用法: card_lint.py <job_dir>  （exit 1 = 不过）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CARDS_DIR = ROOT / "render-engine" / "src" / "cards"


def main() -> None:
    job = Path(sys.argv[1]).resolve()
    sb_path = job / "storyboard.json"
    if not sb_path.exists():
        print("[card-lint] ✗ storyboard.json 不存在", file=sys.stderr)
        sys.exit(1)
    sb = json.loads(sb_path.read_text(encoding="utf-8"))

    reg = {}
    reg_path = CARDS_DIR / "registry.json"
    if reg_path.exists():
        reg = json.loads(reg_path.read_text(encoding="utf-8"))

    errs: list[str] = []
    warns: list[str] = []
    used_cards = [s["recipe_ref"][5:] for s in sb["shots"] if s["recipe_ref"].startswith("card:")]

    for i, shot in enumerate(sb["shots"]):
        ref = shot["recipe_ref"]
        if not ref.startswith("card:"):
            continue
        slug = ref[5:]
        # L1 卡文件存在
        if not (CARDS_DIR / f"card-{slug}.tsx").exists():
            errs.append(f"{shot['id']}: 卡文件缺失 card-{slug}.tsx")
            continue
        # L2 注册表在册
        e = reg.get(slug)
        if e is None:
            errs.append(f"{shot['id']}: {slug} 不在 registry.json")
            continue
        # L3 已接线
        if e.get("tier") != "injectable":
            errs.append(f"{shot['id']}: {slug} tier={e.get('tier')}（raw 卡不得进自动分镜）")
        # L4 时长
        if i not in (0, len(sb["shots"]) - 1):
            dur_ms = shot["time"]["end_ms"] - shot["time"]["start_ms"]
            card_ms = (e.get("durationInFrames") or 0) / 30 * 1000
            if card_ms and card_ms > dur_ms + 500:
                warns.append(f"{shot['id']}: 卡时长 {card_ms/1000:.1f}s > 镜头 {dur_ms/1000:.1f}s（Freeze 定格兜底）")

    for w in warns:
        print(f"[card-lint] ⚠ {w}")
    if errs:
        print("[card-lint] FAIL:")
        for e in errs:
            print("  -", e)
        sys.exit(1)
    print(f"[card-lint] OK（{len(used_cards)} 张移植卡在用: {sorted(set(used_cards))[:8]}{'...' if len(set(used_cards)) > 8 else ''}）")


if __name__ == "__main__":
    main()
