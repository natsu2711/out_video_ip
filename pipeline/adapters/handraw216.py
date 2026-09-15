"""handraw-style 216 画风库吸收（prompt_pack）：人物 IP 手绘风格表。
来源：/Users/bainazi/Documents/outtt/other/2other_pic/handraw-style
每条 = 编号 · 原参考名 | 生图名 | 完整视觉特征描述；编号参考图在 images/individual/NNN.png。
与 hand-drawn-styles（19 画风，模板型）互补：本库是描述型，直接拼主体即可用。"""
from __future__ import annotations

import re
from pathlib import Path

from .base import ImagePromptAdapter

SRC = Path("/Users/bainazi/Documents/outtt/other/2other_pic/handraw-style")
ROW = re.compile(r"^\|\s*(\d+)\s*·\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", re.M)


class Handraw216Adapter(ImagePromptAdapter):
    name = "handraw-style-216"
    source_project = str(SRC)
    absorb_method = "prompt_pack"
    description = "216 种人物 IP 手绘画风（社论漫画/绘本/zine…每条含完整视觉描述+编号参考图）"

    def __init__(self) -> None:
        self._styles: dict[str, dict] | None = None

    def _load(self) -> dict[str, dict]:
        if self._styles is None:
            md = (SRC / "styles_200_reorganized.md").read_text(encoding="utf-8")
            self._styles = {
                f"{n} {gen}": {"num": n, "name": gen, "desc": d}
                for n, _orig, gen, d in ROW.findall(md)
            }
        return self._styles

    def available(self) -> tuple[bool, str]:
        if not SRC.exists():
            return False, f"源目录不存在: {SRC}"
        n = len(self._load())
        if n == 0:
            return False, "styles_200_reorganized.md 解析出 0 个画风"
        return True, f"{n} 个画风（含编号参考图）"

    def styles(self) -> list[str]:
        return list(self._load().keys())

    def produce(self, shot: dict, style: str | None = None) -> dict:
        styles = self._load()
        key = style if style in styles else self.styles()[0]
        st = styles[key]
        subject = (shot.get("visual") or shot.get("intent") or shot["vo"])[:60]
        prompt = (f"{st['desc']}。画面主体：{subject}。白底手绘人物插画，简洁干净，"
                  f"不加任何文字。")
        ref = SRC / "images" / "individual" / f"{int(st['num']):03d}.png"
        return {
            "prompt": prompt,
            "style": key,
            "aspect": "16:9",
            "reference_image": str(ref) if ref.exists() else "",
            "notes": f"handraw-style 第{st['num']}号（源: {self.source_project}）",
        }

    def self_check(self) -> list[str]:
        errs = []
        ok, msg = self.available()
        if not ok:
            return [msg]
        styles = self._load()
        if len(styles) < 100:
            errs.append(f"画风数异常: {len(styles)}")
        for key in list(styles)[:3]:
            out = self.produce({"vo": "测试文案", "intent": "测试", "visual": "短发女孩在白板前讲课"}, key)
            if "短发女孩" not in out["prompt"] or len(out["prompt"]) < 50:
                errs.append(f"画风 {key} 填充异常")
        return errs


ADAPTER = Handraw216Adapter()
