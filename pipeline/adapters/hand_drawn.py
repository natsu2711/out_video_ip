"""hand-drawn-styles 吸收：18 种手绘画风 prompt 配方 → image_prompt adapter。
来源：/Users/bainazi/Documents/outtt/other/1other_video/hand-drawn-styles（prompt_pack 吸收）
解析其 STYLES.md（## N.N 标题 + 代码块模板 + 【占位符】约定），填充 shot 内容。"""
from __future__ import annotations

import re
from pathlib import Path

from .base import ImagePromptAdapter

SRC = Path("/Users/bainazi/Documents/outtt/other/1other_video/hand-drawn-styles")


def _parse_styles(md: str) -> dict[str, dict]:
    """解析 STYLES.md：## 编号 标题 → {style_key: {title, template}}"""
    styles: dict[str, dict] = {}
    for m in re.finditer(r"^## ([\d.]+)[ ]+(.+?)$", md, re.M):
        num, title = m.group(1), m.group(2).strip()
        # 取该节第一个 ``` 代码块作为模板
        seg = md[m.end(): m.end() + 20000]
        tm = re.search(r"```\n(.+?)```", seg, re.S)
        if not tm:
            continue
        key = f"{num} {title.split('（')[0].split('-')[0].strip()}"
        styles[key] = {"title": title, "num": num, "template": tm.group(1).strip()}
    return styles


class HandDrawnAdapter(ImagePromptAdapter):
    name = "hand-drawn-styles"
    source_project = str(SRC)
    absorb_method = "prompt_pack"
    description = "18 种手绘画风 prompt 配方（蜡笔/水墨/水彩/像素/北欧绘本…）"

    def __init__(self) -> None:
        self._styles: dict[str, dict] | None = None

    def _load(self) -> dict[str, dict]:
        if self._styles is None:
            md = (SRC / "STYLES.md").read_text(encoding="utf-8")
            self._styles = _parse_styles(md)
        return self._styles

    def available(self) -> tuple[bool, str]:
        if not SRC.exists():
            return False, f"源目录不存在: {SRC}"
        n = len(self._load())
        if n == 0:
            return False, "STYLES.md 解析出 0 个画风"
        return True, f"{n} 个画风配方"

    def styles(self) -> list[str]:
        return list(self._load().keys())

    def produce(self, shot: dict, style: str | None = None) -> dict:
        styles = self._load()
        key = style if style in styles else self.styles()[0]
        tpl = styles[key]["template"]
        subject = (shot.get("visual") or shot.get("intent") or shot["vo"])[:60]
        prompt = tpl.replace("【主体】", subject).replace("【文字】", "不加任何文字")
        # 清掉未匹配的其它占位符（保守：保留模板原样占位符会污染生图）
        prompt = re.sub(r"【[^】]*】", "", prompt)
        return {
            "prompt": prompt,
            "style": key,
            "aspect": "16:9",
            "notes": f"hand-drawn-styles 画风 {styles[key]['num']}（源: {self.source_project}）",
        }

    def self_check(self) -> list[str]:
        errs = []
        ok, msg = self.available()
        if not ok:
            return [msg]
        styles = self._load()
        if len(styles) < 5:
            errs.append(f"画风数异常: {len(styles)}")
        # 抽 3 个模板试填充
        for key in list(styles)[:3]:
            out = self.produce({"vo": "测试文案，三个原因", "intent": "测试", "visual": "一个测试画面"}, key)
            if "测试画面" not in out["prompt"] and len(out["prompt"]) < 50:
                errs.append(f"画风 {key} 填充异常")
        return errs


ADAPTER = HandDrawnAdapter()
