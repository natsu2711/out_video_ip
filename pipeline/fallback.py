"""规则兜底生成器：LLM 全链不可用时，管线仍以确定性规则产出合法产物。

口径：兜底产出 = 结构 100% 合法 + 文案朴素（ plainly 从原句提取）。
质量低于 LLM 档但绝不阻塞流程——这就是「便宜/无模型也能稳定出片」的底座。
"""

# 语义特征 → 配方（优先级从上到下）
KEYWORD_RULES: list[tuple[str, list[str]]] = [
    ("StepsCard", ["第一步", "第二步", "第三步", "然后", "接着", "再", "最后", "流程", "步骤"]),
    ("QuoteCard", ["「", "」", "说", "quote", "句话", "名言", "金句"]),
    ("TransformCard", ["以前", "现在", "过去", "变成", "从", "到", "而今天", "不再", "而是"]),
    ("ListGrid", ["清单", "几条", "几个", "四个", "五个", "三个", "六", "七", "盘点", "方法", "原因"]),
    ("ARollScene", ["他", "她", "我", "你", "一个人", "主角", "人物", "镜头"]),
]

# 保底轮换（混编本地组件 + talkcraft 移植卡：无模型也不单调；slug 均在 registry 内）
ROTATION = [
    "ARollScene", "card:bar-chart-growth", "card:quote-card", "card:number-counter",
    "ARollScene", "card:converging-arrows", "card:impact-open-title", "card:highlighter-sweep",
]

VIEW_CYCLE = ["host", "protagonist", "pov"]


# 保底王（beat 固定保底结构族）：LLM 降级组不走关键词配卡，直接用本 beat 的保底王。
# 同族 2 变体按镜头序确定性轮换——结构稳定成"章节样式"，变体消除模板疲劳，也不触发连续同配方铁律。
BEAT_FALLBACK: dict[str, list[str]] = {
    "hook":     ["card:ppt-steps", "card:impact-open-title"],
    "point":    ["card:bar-chart-growth", "card:number-counter"],
    "step":     ["card:ppt-steps", "card:numbered-step-stack"],
    "case":     ["card:line-chart-story-draw", "card:number-counter"],
    "contrast": ["card:ppt-compare", "card:type-contrast-emphasis"],
    "quote":    ["card:quote-card", "card:focus-dim-spotlight"],
    "cta":      ["card:subscribe-cta", "card:douyin-follow-card"],
}


def beat_fallback(beat: str | None, idx: int) -> str:
    """保底王：beat 定结构族，镜头序定变体（确定性）。beat 未知回退 point 族。"""
    variants = BEAT_FALLBACK.get(beat or "") or BEAT_FALLBACK["point"]
    return variants[idx % len(variants)]


def pick_recipe(text: str, idx: int, used: dict[str, int], cap: int) -> tuple[str, str]:
    """返回 (recipe_ref, 选择依据)。带多样性约束的规则选卡。"""
    hits = [(prio, r) for prio, (r, kws) in enumerate(KEYWORD_RULES)
            if any(k in text for k in kws)]
    hits.sort()
    for _, r in hits:
        if used.get(r, 0) < cap and r not in ("TitleCard", "EndingCard"):
            return r, "关键词命中"
    for r in ROTATION:
        if used.get(r, 0) < cap:
            return r, "轮换兜底"
    return ROTATION[idx % len(ROTATION)], "轮换兜底(超限)"


def split_sentences(text: str) -> list[str]:
    """规则分句：。！？；换行，长句按逗号二次切（≤40 字一段）。"""
    import re
    parts = [p.strip() for p in re.split(r"[。！？；\n]+", text) if p.strip()]
    out = []
    for p in parts:
        if len(p) <= 40:
            out.append(p)
            continue
        subs, cur = [], ""
        for c in re.split(r"[，,]", p):
            if cur and len(cur) + len(c) > 40:
                subs.append(cur)
                cur = c
            else:
                cur = f"{cur}，{c}" if cur else c
        if cur:
            subs.append(cur)
        out.extend(subs)
    return out


def motion_from_text(text: str) -> list[str]:
    """从原句提取画面节拍（朴素但真实响应文案——引号词/数字优先）。"""
    import re
    beats = []
    for q in re.findall(r"[「']([^」']+)[」']", text)[:2]:
        beats.append(f"「{q}」大字砸入")
    nums = re.findall(r"[0-9一二两三四五六七八九十百千万亿]+", text)
    if nums and len(beats) < 2:
        beats.append(f"数字「{nums[0]}」放大定格")
    if len(beats) < 1:
        beats.append("主体入场")
    if len(beats) < 2:
        beats.append("重音脉冲强调")
    return beats[:3]
