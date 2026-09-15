"""vox-director 吸收（prompt_pack）：Vox 纸片拼贴海报 prompt 5 段式。
来源：/Users/bainazi/Documents/outtt/other/1other_video/vox-director（references/prompt-guide.md）
关键纪律（来自原库）：风格块跨镜头逐字复用（一致性来源）；场景描述为"分件拼贴"（可分层视差）；
标题短粗烧进图；每镜一块大胆平涂底色。仅吸收 LOOK 层，生图模型由调用方决定（零 API 依赖）。"""
from __future__ import annotations

from pathlib import Path

from .base import ImagePromptAdapter

SRC = Path("/Users/bainazi/Documents/outtt/other/1other_video/vox-director")

# 5 段式之 [1] STYLE BLOCK——逐字复用，不随镜头变（prompt-guide.md §1 原文）
STYLE_BLOCK = (
    "Mixed-media hand-cut PAPER COLLAGE, editorial zine style. Torn/scissor-cut paper edges, "
    "tape corners, halftone print dots, newspaper clippings, paper-stencil shapes, real paper "
    "drop shadows. Figures are PRINTED-texture cut-outs of real imagery, NOT CGI, NOT a 3D "
    "render — keep print grain and paper imperfections. High-contrast."
)
# [3] 底色轴：每镜换色带情绪（相邻镜头不同由调用方轮换序保证）
BG_COLORS = ["deep red", "mustard yellow", "navy blue", "forest green", "cream", "burnt orange"]


class VoxCollageAdapter(ImagePromptAdapter):
    name = "vox-collage"
    source_project = str(SRC)
    absorb_method = "prompt_pack"
    description = "Vox 纸片拼贴海报 prompt（撕纸/胶带/半调网点/大胆平涂底色/烧字标题，5 段式）"

    def available(self) -> tuple[bool, str]:
        if not SRC.exists():
            return False, f"源目录不存在: {SRC}"
        guide = SRC / "references" / "prompt-guide.md"
        if not guide.exists():
            return False, "prompt-guide.md 缺失"
        return True, "prompt 5 段式已内置（风格块+底色轴）"

    def styles(self) -> list[str]:
        return [f"底色:{c}" for c in BG_COLORS]

    def produce(self, shot: dict, style: str | None = None) -> dict:
        import re
        quotes = re.findall(r"[「『]([^」』]+)[」』]", shot.get("vo", ""))
        title = (quotes[0] if quotes else (shot.get("intent") or shot.get("vo", "")))[:10]
        subject = (shot.get("visual") or shot.get("intent") or shot["vo"])[:60]
        k = abs(hash(shot.get("id", "S000"))) % len(BG_COLORS)  # 确定性：同镜同色
        bg = BG_COLORS[k]
        prompt = (
            f"{STYLE_BLOCK} SCENE as layered paper cut-outs: {subject}; elements with clear edges, "
            f"distinct layers, each with its own drop shadow. Bold flat {bg} paper background. "
            f'Torn-paper banner headline "{title}" (short, bold). 16:9, 2k resolution. '
            f"标题用中文。"
        )
        return {
            "prompt": prompt,
            "style": f"底色:{bg}",
            "aspect": "16:9",
            "notes": "vox-director 拼贴 5 段式（源: prompt-guide.md，风格块逐字复用保跨镜一致）",
        }

    def self_check(self) -> list[str]:
        ok, msg = self.available()
        if not ok:
            return [msg]
        out = self.produce({"id": "S001", "vo": "「零元」创业。", "intent": "钩子", "visual": "女孩站在白板前"})
        errs = []
        if "PAPER COLLAGE" not in out["prompt"] or "drop shadow" not in out["prompt"]:
            errs.append("风格块丢失")
        if len(out["prompt"]) < 100:
            errs.append("prompt 过短")
        return errs


ADAPTER = VoxCollageAdapter()
