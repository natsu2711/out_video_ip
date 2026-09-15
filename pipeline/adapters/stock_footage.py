"""stock_footage 吸收：MoneyPrinterTurbo 的核心单点能力「文案→匹配素材视频」。
来源：/Users/bainazi/Documents/outtt/1other_video/MoneyPrinterTurbo（api 吸收，吸收其
Pexels/Pixabay 搜索协议知识：端点/参数/响应结构/清晰度选择，不 vendor 其代码）。

capability = "stock_footage"
produce(shot) -> {"provider", "clips": [{url, width, height, duration}], "keywords": [...]}
依赖：PEXELS_API_KEY 或 PIXABAY_API_KEY 环境变量（免费申请）；都缺 → available()=False，
S4C 降级为「关键词任务单」模式（人工去 Pexels 网站搜）。
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request

from .base import Adapter

PEXELS_SEARCH = "https://api.pexels.com/videos/search?{q}"
PIXABAY_SEARCH = "https://pixabay.com/api/videos/?{q}"


def derive_keywords(shot: dict, llm_chain=None) -> list[str]:
    """shot → 2~3 个英文搜索词。LLM 优先（翻译+具象化），规则兜底（引号词/意图直用）。"""
    vo = shot.get("vo", "")
    intent = shot.get("intent", "")
    quoted = re.findall(r"[「『]([^」』]+)[」』]", vo)
    if llm_chain is not None:
        try:
            obj, _ = llm_chain.complete_json(
                '把下面口播翻译成 2-3 个用于素材库(Pexels)搜索的英文短语，'
                '要具象可视（人/物/场景），不要抽象概念。\n'
                f'口播：{vo[:80]}\n意图：{intent[:30]}\n'
                '输出 JSON: {"terms": ["term1", "term2"]}',
                schema={"type": "object", "required": ["terms"],
                        "properties": {"terms": {"type": "array", "items": {"type": "string"}}}},
                temperature=0.1,
            )
            terms = [t.strip() for t in obj["terms"] if t.strip()][:3]
            if terms:
                return terms
        except Exception:  # noqa: BLE001
            pass
    # 规则兜底：引号词 > 意图 > visual 截断
    terms = [q for q in quoted if len(q) <= 10]
    if intent:
        terms.append(intent[:12])
    if not terms:
        terms.append((shot.get("visual") or vo)[:12])
    return terms[:3]


class StockFootageAdapter(Adapter):
    name = "stock-footage"
    capability = "stock_footage"
    source_project = "/Users/bainazi/Documents/outtt/1other_video/MoneyPrinterTurbo"
    absorb_method = "api"
    description = "文案→匹配素材视频（Pexels/Pixabay 免费商用素材库搜索+下载）"

    def available(self) -> tuple[bool, str]:
        if os.environ.get("PEXELS_API_KEY"):
            return True, "Pexels API"
        if os.environ.get("PIXABAY_API_KEY"):
            return True, "Pixabay API"
        return False, "缺 PEXELS_API_KEY / PIXABAY_API_KEY（免费申请；缺失时 S4C 降级为关键词任务单）"

    def styles(self) -> list[str]:
        return ["pexels", "pixabay"]

    def _search_pexels(self, term: str, min_dur: int, portrait: bool) -> list[dict]:
        key = os.environ["PEXELS_API_KEY"]
        params = urllib.parse.urlencode({"query": term, "per_page": 10,
                                         "orientation": "portrait" if portrait else "landscape"})
        req = urllib.request.Request(PEXELS_SEARCH.format(q=params),
                                     headers={"Authorization": key})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
        clips = []
        for v in data.get("videos", []):
            if v.get("duration", 0) < min_dur:
                continue
            # 选最接近目标分辨率的文件（MoneyPrinterTurbo 同款策略）
            best = min(v.get("video_files", []),
                       key=lambda f: abs(f.get("width", 0) * f.get("height", 0) - 1080 * 1920))
            if best.get("link"):
                clips.append({"url": best["link"], "width": best.get("width", 0),
                              "height": best.get("height", 0), "duration": v["duration"],
                              "provider": "pexels"})
        return clips

    def _search_pixabay(self, term: str, min_dur: int) -> list[dict]:
        key = os.environ["PIXABAY_API_KEY"]
        params = urllib.parse.urlencode({"key": key, "q": term, "per_page": 10})
        req = urllib.request.Request(PIXABAY_SEARCH.format(q=params))
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
        clips = []
        for v in data.get("hits", []):
            if v.get("duration", 0) < min_dur:
                continue
            vids = v.get("videos", {})
            best = vids.get("large") or vids.get("medium") or vids.get("small")
            if best and best.get("url"):
                clips.append({"url": best["url"], "width": best.get("width", 0),
                              "height": best.get("height", 0), "duration": v["duration"],
                              "provider": "pixabay"})
        return clips

    def produce(self, shot: dict, keywords: list[str] | None = None,
                min_duration: int = 4, llm_chain=None) -> dict:
        terms = keywords or derive_keywords(shot, llm_chain)
        clips: list[dict] = []
        used_provider = ""
        for term in terms:
            if os.environ.get("PEXELS_API_KEY"):
                try:
                    clips = self._search_pexels(term, min_duration, portrait=True)
                    used_provider = "pexels"
                except Exception as e:  # noqa: BLE001
                    clips = []
                    used_provider = f"pexels-error:{e}"
            if not clips and os.environ.get("PIXABAY_API_KEY"):
                try:
                    clips = self._search_pixabay(term, min_duration)
                    used_provider = "pixabay"
                except Exception as e:  # noqa: BLE001
                    used_provider = f"pixabay-error:{e}"
            if clips:
                break
        return {"provider": used_provider, "clips": clips, "keywords": terms}

    def self_check(self) -> list[str]:
        ok, msg = self.available()
        if not ok:
            return []  # 未配 key 是合法状态（降级模式），不算错
        errs = []
        out = self.produce({"vo": "一个人在城市里奔跑", "intent": "奔跑", "visual": "城市奔跑"},
                           keywords=["city running"], min_duration=3)
        if "error" in str(out.get("provider")):
            errs.append(f"搜索失败: {out['provider']}")
        return errs
ADAPTER = StockFootageAdapter()
