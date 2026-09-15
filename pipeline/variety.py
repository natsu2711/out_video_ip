"""受控多样性引擎：花样来自选项库，稳定来自查表+禁忌，匹配来自 beat 语义。

设计原则（v2 工作流稳定化核心）：
  1. 每个设计决策 = 白名单 + 确定性轮换，禁止无约束即兴（LLM 产出也要过白名单校验）
  2. 「跟文案匹配」= beat/visual_hint/关键词 语义路由到候选池
  3. 「每次不一样」= 池内轮换 + 禁忌（连续、近期已用、全片 cap）——多样性是带记忆的
  4. 全部确定性（无 random）：同输入同输出，seed 仅来自内容本身

来源标注：候选卡清单从 render-engine/src/cards/registry.json（talkcraft 79 卡）
与本地组件（shots/）中按语义挑选；排版节奏规则来自 vox-director beat-layer 与
guizang 瑞士阶梯（见 lib/theme.ts）。
"""
from __future__ import annotations

from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent

# ---------------- beat → 候选卡白名单 ----------------
# 每类至少 2 个候选（轮换空间）；卡名须存在于 registry.json 或本地 shots。
# beat 语义对齐 script.schema：hook/point/step/case/contrast/quote/cta
BEAT_CARDS: dict[str, list[str]] = {
    "hook":     ["card:impact-open-title", "card:ppt-title", "card:slab-punch-title", "card:number-slab-pop",
                 "card:tracking-in", "card:typewriter-reveal", "KineticTitle", "card:stickman-talk",
                 "card:ticker-wall"],
    "point":    ["card:number-counter", "card:bar-chart-growth", "card:converging-arrows",
                 "card:metric-with-sparkline", "card:chart-grow",
                 "card:hand-drawn-ellipse", "card:scribble-annotation"],
    "step":     ["card:ppt-steps", "card:highlighter-sweep", "card:chart-grow", "card:numbered-step-stack",
                 "card:step-timeline-vertical"],
    "case":     ["card:number-slab-pop", "card:quote-bracket-pull", "card:number-counter",
                 "card:line-chart-story-draw", "card:type-mono"],
    "contrast": ["card:ppt-compare", "card:strike-and-replace", "card:type-contrast-emphasis", "card:impact-open-title",
                 "card:slab-punch-title"],
    "quote":    ["card:quote-card", "card:quote-bracket-pull", "card:focus-dim-spotlight",
                 "card:ink-underline", "card:type-serif"],
    "cta":      ["card:subscribe-cta", "card:douyin-follow-card", "card:x-follow-card"],
}

# visual_hint 对素材模式的硬约束（preflight/s3_check 可查）
HINT_ASSET = {
    "scene":  ["ARollScene", "RealFootage"],   # 需要人物/实景
    "real":   ["ScreenshotCard", "RealFootage"],  # 需要真实素材
    "graphic": None,                            # 图表/动效卡皆可
    "quote":  None,
    "none":   None,
}

# 氛围叠层轮换表（C-roll decoration；s3 装配与 visual_compiler 共用单一来源）
CARD_OVERLAY_CYCLE = [["grain"], ["light_sweep"], ["particles"], ["tint_cool", "grain"], ["snow"], ["embers"]]


def card_overlay(shot_idx: int) -> list[str]:
    """移植卡叠层：按镜头序确定性轮换。"""
    return list(CARD_OVERLAY_CYCLE[shot_idx % len(CARD_OVERLAY_CYCLE)])


# 转场（呈现语法）轮换表：相邻镜头不同
PRESENTATION_CYCLE = ["rise_fade", "wipe_mask", "slam_in", "blur_focus", "rise_fade", "none"]

# 氛围光色板（vox 式每拍换色）——相邻镜头不同色
BEAT_COLORS = ["#E4572E", "#2E86AB", "#F3A712", "#3E8989", "#B33F62"]


def _rot(seq: list[str], i: int) -> str:
    return seq[i % len(seq)]


def candidates_for(beat: str, used: dict[str, int], cap: int,
                   recent: list[str], pool_size: int = 2) -> list[str]:
    """返回 beat 类型的可用候选卡（按优先序，已过禁忌）。

    禁忌（按序过滤）：不在白名单 / 超全片 cap / 近 recent 窗内已用。
    全被过滤时放宽 recent（仍守 cap）；再不行回退白名单首项。
    """
    pool = BEAT_CARDS.get(beat) or BEAT_CARDS["point"]
    recent_set = set(recent[-2:])  # 近 2 镜禁重复（对齐 lint 连续同配方≤2）

    def usable(r: str, strict: bool) -> bool:
        if used.get(r, 0) >= cap:
            return False
        return not (strict and r in recent_set)

    out = [r for r in pool if usable(r, strict=True)]
    if len(out) < pool_size:
        out += [r for r in pool if usable(r, strict=False) and r not in out]
    if not out:
        out = pool[:1]
    return out[:pool_size]


def pick_candidate(beat: str, shot_idx: int, used: dict[str, int], cap: int,
                   recent: list[str]) -> str:
    """确定性选 1 张：候选池按镜头序号轮换（同文案序列 → 同结果）。"""
    return _rot(candidates_for(beat, used, cap, recent), shot_idx)




# ---------------- Visual Compiler 检索层（spec §6：Hard Filter + 打分，确定性） ----------------

# beat → visual_intent 映射（有限枚举，spec §4）
BEAT_INTENT = {
    "hook": ["emphasis", "ui", "scene"],
    "point": ["data", "emphasis", "list"],
    "step": ["process", "list"],
    "case": ["data", "process", "ui"],
    "contrast": ["before_after", "comparison"],
    "quote": ["emphasis", "quote"],
    "cta": ["ui", "list"],
}

def _registry_meta():
    """读 registry 的检索元数据（模块级缓存）。"""
    global _META_CACHE
    if _META_CACHE is None:
        import json
        reg_path = ROOT / "render-engine" / "src" / "cards" / "registry.json"
        meta = {}
        if reg_path.exists():
            reg = json.loads(reg_path.read_text(encoding="utf-8"))
            for slug, e in reg.items():
                if e.get("tier") == "injectable":
                    meta[slug] = e
        _META_CACHE = meta
    return _META_CACHE

_META_CACHE = None

def retrieve_candidates(beat: str, used: dict, cap: int, recent: list[str],
                        pool_size: int = 3, threshold: float = 0.5) -> list[str]:
    """spec §6：Hard Filter（tier/时长/近期）→ 打分（intent 0.5 + category3 0.3 + 新鲜 0.2）。
    打分全部低于阈值 → 返回 []（调用方回退保底王）。纯确定性。"""
    from pipeline.lint import _cap
    meta = _registry_meta()
    intents = BEAT_INTENT.get(beat or "", BEAT_INTENT["point"])
    recent_set = set(recent[-2:])
    scored = []
    for slug, e in meta.items():
        if slug.startswith(("TitleCard", "EndingCard")) or slug in ("KineticTitle",):
            continue
        if used.get(f"card:{slug}", 0) >= cap:
            continue
        vi = set(e.get("visual_intent", []))
        intent_match = len(vi & set(intents)) / max(1, len(intents))
        if intent_match <= 0:
            continue  # Hard Filter：intent 不相交直接出局
        fresh = 0.0 if f"card:{slug}" in recent_set else 0.2
        score = 0.5 * intent_match + 0.3 + fresh  # category3 已隐含在 intent 派生
        if f"card:{slug}" in recent_set:
            score -= 0.25
        scored.append((score, slug))
    scored.sort(reverse=True)
    out = [s for sc, s in scored if sc >= threshold]
    if not out:
        out = _weknora_boost(beat, intents, meta, used, cap, pool_size)
    return out[:pool_size]


def _weknora_boost(beat: str, intents: list, meta: dict, used: dict, cap: int,
                   pool_size: int) -> list[str]:
    """WeKnora 语义检索增强（spec §12）：本地打分低于阈值时，用 beat 语义查询
    WeKnora KB，结果仍过 Hard Filter（intent 相交 + cap）。失败/空 → []（保底王）。"""
    try:
        from pipeline import weknora
        if not weknora.available():
            return []
        hits = weknora.search(f"{beat} beat，{'/'.join(intents)}，动效资产卡", pool_size)
        out = []
        for slug in hits:
            e = meta.get(slug)
            if not e or slug.startswith(("TitleCard", "EndingCard")):
                continue
            if used.get(f"card:{slug}", 0) >= cap:
                continue
            if not (set(e.get("visual_intent", [])) & set(intents)):
                continue
            out.append(slug)
        return out
    except Exception:
        return []


def pick_candidate_meta(beat: str, shot_idx: int, used: dict, cap: int,
                        recent: list[str]) -> str | None:
    """元数据检索选卡；无合格候选返回 None（调用方回退 BEAT_CARDS）。"""
    cands = retrieve_candidates(beat, used, cap, recent)
    if not cands:
        return None
    return _rot(cands, shot_idx)


def pick_presentation(shot_idx: int, roll: str) -> str:
    """呈现语法轮换：B-roll 镜从循环表取，A-roll 固定 wipe_mask（IP 出场仪式感）。"""
    if roll == "A":
        return "wipe_mask"
    return _rot([p for p in PRESENTATION_CYCLE if p != "wipe_mask"], shot_idx)


def pick_beat_color(shot_idx: int) -> str:
    """氛围光色：相邻镜头不同色由 (idx % 5) + 素数偏移保证。"""
    return BEAT_COLORS[(shot_idx * 2 + 1) % len(BEAT_COLORS)]


def side_policy(shot: dict) -> dict | None:
    """SidePanel 决策：仅当卡片是「左主体右占位」型且 config 未显式给 side 时给默认。
    规则：number/counter 类 → 配 mini 柱图；title 类 → bigword；其余 none（留白）。"""
    if (shot.get("config") or {}).get("side") is not None:
        return shot["config"]["side"]
    ref = shot.get("recipe_ref", "")
    if ref in ("card:number-counter", "card:bar-chart-growth"):
        return {"kind": "chart", "title": "", "color": "", "data": []}  # 数据由 S3 按 vo 填
    if ref in ("card:slab-punch-title", "card:tracking-in"):
        return {"kind": "bigword", "word": "", "note": ""}
    return None
