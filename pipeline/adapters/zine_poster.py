"""gc-minimal-zine-poster 吸收（prompt_pack）：诗性纸感留白微编辑海报 prompt 系统。
来源：/Users/bainazi/Documents/outtt/other/2other_pic/gc-minimal-zine-poster（references/style-system.md）
核心纪律（原库固定系统）：70-90% 留白纸面 + 8-25% 单一视觉事件 + 一点高饱和点色；
flat 扫描质感、无硬阴影；文字是"便签/私句"不是广告标题。适合 quote/hook 底图与封面。"""
from __future__ import annotations

from pathlib import Path

from .base import ImagePromptAdapter

SRC = Path("/Users/bainazi/Documents/outtt/other/2other_pic/gc-minimal-zine-poster")

# 固定系统（style-system.md §Fixed System 逐字内核）
FIXED = (
    "Flat scanned paper field, warm paper with fibers, fine grain, dust, scan noise, matte "
    "absorbency. 70-90% of canvas reads as open paper; one small visual event occupies 8-25%. "
    "Flat orthographic scan, diffuse light, low-to-medium contrast, no hard shadow, no mockup "
    "depth. Typography sparse like a private note, not a headline."
)
PAPER_TONES = ["warm white", "ivory", "old-paper yellow", "light gray", "light kraft beige"]
ACCENTS = ["cobalt", "ultramarine", "violet", "magenta-pink", "lemon yellow", "tomato red", "orange"]
POSITIONS = ["center-high", "lower-left third", "right-middle", "upper-right third", "center-low"]
MOODS = ["quiet", "memory-like", "seaside afternoon", "solitude", "night", "slight surrealism"]


class ZinePosterAdapter(ImagePromptAdapter):
    name = "zine-poster"
    source_project = str(SRC)
    absorb_method = "prompt_pack"
    description = "诗性纸感留白微编辑海报（70-90% 留白 + 单一视觉事件 + 一点高饱和点色）"

    def available(self) -> tuple[bool, str]:
        if not (SRC / "references" / "style-system.md").exists():
            return False, f"源不存在: {SRC}"
        return True, "固定系统+变量轴已内置（纸色/点色/构图位/情绪）"

    def styles(self) -> list[str]:
        return [f"点色:{c}" for c in ACCENTS]

    def produce(self, shot: dict, style: str | None = None) -> dict:
        subject = (shot.get("visual") or shot.get("intent") or shot["vo"])[:50]
        k = abs(hash(shot.get("id", "S000"))) % len(ACCENTS)  # 确定性：同镜同配置
        accent = ACCENTS[k if style not in self.styles() else self.styles().index(style)]
        paper = PAPER_TONES[k % len(PAPER_TONES)]
        pos = POSITIONS[k % len(POSITIONS)]
        mood = MOODS[k % len(MOODS)]
        prompt = (
            f"{FIXED} Visual event: {subject} — one primary metaphor, not a full scene. "
            f"Paper tone: {paper}. One clearly saturated {accent} accent carried by the focal "
            f"element (15-35% of the cluster, 0.8-2.5% of canvas). Cluster at {pos}. Mood: {mood}. "
            f"微小的手写中文短句作为便签式标注。16:9, 2k."
        )
        return {
            "prompt": prompt,
            "style": f"点色:{accent}",
            "aspect": "16:9",
            "notes": "zine-poster 留白海报（源: style-system.md，留白纪律固定）",
        }

    def self_check(self) -> list[str]:
        ok, msg = self.available()
        if not ok:
            return [msg]
        out = self.produce({"id": "S001", "vo": "孤独但自由", "intent": "金句", "visual": "一只纸船漂在留白纸面"})
        errs = []
        if "open paper" not in out["prompt"] or "8-25%" not in out["prompt"]:
            errs.append("留白纪律丢失")
        if len(out["prompt"]) < 100:
            errs.append("prompt 过短")
        return errs


ADAPTER = ZinePosterAdapter()
