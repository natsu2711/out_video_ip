#!/usr/bin/env python3
"""Phase 1：给 registry 全部卡生成检索元数据（确定性，无 LLM）。

按 slug 关键词 + sc 来源分类推导：
  visual_intent（枚举见 spec §4）、content_types、energy。
幂等可重跑；已有字段不覆盖。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REG = ROOT / "render-engine" / "src" / "cards" / "registry.json"

# slug 关键词 → visual_intent（按序首个命中；多标签取前 2）
INTENT_KW = [
    ("before_after", ["before-after", "compare", "contrast", "replace", "strike", "versus", "swap", "transform", "type-contrast"]),
    ("data", ["chart", "bar", "line", "metric", "counter", "number", "kpi", "gauge", "digit", "sparkline", "stat", "growth", "progress", "odometer"]),
    ("timeline", ["timeline", "chapter", "stage", "milestone"]),
    ("process", ["step", "checklist", "pipeline", "numbered", "flow", "sequence"]),
    ("quote", ["quote", "highlight", "ink-underline", "keyword-pop", "bracket"]),
    ("emphasis", ["slam", "impact", "punch", "flash", "stomp", "pop", "zoom", "magnifier", "focus", "spotlight", "highlight"]),
    ("transition", ["transition", "wipe", "whip", "morph", "weld", "overexpose", "pullback", "push-through", "black-slam", "color-slam", "caret", "page-turn", "hidden-cut", "dissolve"]),
    ("ui", ["ui-", "terminal", "chat", "claude", "gpt", "browser", "dashboard", "danmu", "news-card", "info-term", "evidence", "scroll", "waterfall", "page-cam"]),
    ("character", ["aroll", "host", "stickman", "ip-", "emote", "actor", "avatar"]),
    ("scene", ["map", "route", "landscape", "world", "long-take", "orbit", "sway", "camera", "parallax", "depth"]),
    ("list", ["list", "grid", "matrix", "chips", "pills", "ticker", "carousel", "stack", "deck", "alt-block"]),
    ("hierarchy", ["matrix", "tier", "tower", "hierarchy", "tree"]),
    ("relationship", ["converging", "arrow", "route", "relationship", "node"]),
]

ENERGY_KW = [
    ("high", ["slam", "impact", "stomp", "flash", "burst", "confetti", "whip", "punch", "crash", "explosion"]),
    ("low", ["slow", "drift", "float", "calm", "soft", "gentle", "boil"]),
]

def intents_for(slug: str, sc_cat: str) -> list[str]:
    out = []
    # sc 目录分类直接给强先验
    sc_map = {
        "data": ["data"], "typography": ["emphasis"], "opening": ["emphasis"],
        "transition": ["transition"], "rhythm": ["process"], "camera": ["scene"],
        "effects": ["emphasis"], "interaction": ["ui"], "ui-entrance": ["ui"],
        "outro": ["cta"],
    }
    if sc_cat and sc_cat in sc_map:
        out += sc_map[sc_cat]
    for intent, kws in INTENT_KW:
        if any(k in slug for k in kws):
            out.append(intent)
    seen, dedup = set(), []
    for i in out:
        if i not in seen:
            seen.add(i)
            dedup.append(i)
    return dedup[:3] or ["emphasis"]

def energy_for(slug: str) -> str:
    for e, kws in ENERGY_KW:
        if any(k in slug for k in kws):
            return e
    return "medium"

def content_types_for(e: dict) -> list[str]:
    types = []
    arities = e.get("arities") or {}
    if any(k.startswith("TEXT") for k in arities):
        types.append("text")
    if e.get("images") or "SLOTS" in arities:
        types.append("image")
    if any(k in e.get("slug", "") for k in ("counter", "digit", "number", "metric", "kpi", "gauge")):
        types.append("number")
    return types or ["text"]

def main() -> None:
    reg = json.loads(REG.read_text(encoding="utf-8"))
    n = 0
    for slug, e in reg.items():
        if e.get("tier") not in ("injectable", "raw"):
            continue
        if not e.get("visual_intent"):
            sc_cat = e.get("category", "").replace("sc:", "")
            e["visual_intent"] = intents_for(slug, sc_cat)
            e["content_types"] = content_types_for(e)
            e["energy"] = energy_for(slug)
            dur = e.get("durationInFrames") or 110
            e["duration_sec"] = {"min": round(dur / 30 * 0.9, 1), "max": round(dur / 30 * 1.1, 1)}
            n += 1
    REG.write_text(json.dumps(reg, ensure_ascii=False, indent=1), "utf-8")
    print(f"[metadata] {n} 张卡元数据已生成")

if __name__ == "__main__":
    main()
