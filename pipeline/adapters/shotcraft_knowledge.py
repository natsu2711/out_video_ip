"""video-shotcraft 吸收：镜头方法论卡库（camera/data/effects/interaction/opening/outro/rhythm）
→ recipe_knowledge adapter。
来源：/Users/bainazi/Documents/outtt/other/1other_video/video-shotcraft（prompt_pack / 知识索引吸收）
shotcraft 的卡是 md 方法论文档（非自包含 tsx），吸收为结构化知识索引：
  ① 供 S3 prompt 引用动效词汇（镜头怎么动的描述语言）
  ② 作为逐卡移植队列（talkcraft 式 tsx 移植的 backlog）"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .base import RecipeKnowledgeAdapter

SRC = Path("/Users/bainazi/Documents/outtt/other/1other_video/video-shotcraft/references/shots")


class ShotcraftKnowledgeAdapter(RecipeKnowledgeAdapter):
    name = "shotcraft-cards"
    source_project = str(SRC.parent)
    absorb_method = "prompt_pack"
    description = "152 张镜头方法论卡（camera/data/effects/interaction/opening/outro/rhythm 七类）"

    def __init__(self) -> None:
        self._cards: list[dict] | None = None

    def _load(self) -> list[dict]:
        if self._cards is not None:
            return self._cards
        cards = []
        for f in sorted(SRC.rglob("*.md")):
            if f.name in ("ATTRIBUTION.md", "README.md"):
                continue
            slug = f.stem
            category = f.parent.name
            text = f.read_text(encoding="utf-8")
            title_m = re.search(r"^#\s+(.+)$", text, re.M)
            # essence：第一段非标题正文（动效手法描述）
            body = re.sub(r"^#.*$|^```[\s\S]*?```", "", text, flags=re.M).strip()
            essence = next((ln.strip() for ln in body.splitlines()
                            if len(ln.strip()) > 15 and not ln.startswith("|")), "")[:120]
            cards.append({"slug": slug, "category": category,
                          "title": (title_m.group(1).strip() if title_m else slug),
                          "essence": essence})
        self._cards = cards
        return cards

    def available(self) -> tuple[bool, str]:
        if not SRC.exists():
            return False, f"源目录不存在: {SRC}"
        return True, f"{len(self._load())} 张知识卡"

    def produce(self) -> dict:
        cards = self._load()
        return {"cards": cards, "count": len(cards)}

    def export_index(self, out: Path) -> None:
        out.write_text(json.dumps(self.produce(), ensure_ascii=False, indent=1), "utf-8")

    def self_check(self) -> list[str]:
        ok, msg = self.available()
        if not ok:
            return [msg]
        cards = self._load()
        errs = []
        if len(cards) < 50:
            errs.append(f"卡数异常: {len(cards)}（应 ≥50，含 48 张新批次）")
        cats = {c["category"] for c in cards}
        if "camera" not in cats or "rhythm" not in cats:
            errs.append(f"类别缺失: {cats}")
        no_essence = [c["slug"] for c in cards if not c["essence"]]
        if len(no_essence) > len(cards) // 2:
            errs.append(f"过半卡无手法摘要: {len(no_essence)}")
        return errs


ADAPTER = ShotcraftKnowledgeAdapter()
