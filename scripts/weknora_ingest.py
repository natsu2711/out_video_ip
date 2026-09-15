#!/usr/bin/env python3
"""把 registry 全部卡片文档 ingest 进 WeKnora KB asset-cards（spec §12）。

用法: python scripts/weknora_ingest.py
WeKnora 不可用时打印降级提示并退出 0（S3 检索层会自动回退纯本地链路）。
幂等：按 slug 覆盖式更新。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import weknora  # noqa: E402

REG = ROOT / "render-engine" / "src" / "cards" / "registry.json"


def main() -> None:
    cards = json.loads(REG.read_text(encoding="utf-8"))
    if isinstance(cards, dict):
        cards = list(cards.values())
    if not weknora.available():
        print("[weknora] 服务不可用（CLI 未构建 / HTTP 未启动）→ 跳过 ingest。")
        print("[weknora] 启动方式：cd WeKnora && docker compose up -d（或 make cli 构建 knora CLI）。")
        print("[weknora] S3 检索层当前走纯本地链路（元数据检索→关键词→保底王），功能不受影响。")
        return
    ok = weknora.ingest(cards)
    print(f"[weknora] ingest {ok}/{len(cards)} 张卡 → KB {weknora.KB_NAME}")


if __name__ == "__main__":
    main()
