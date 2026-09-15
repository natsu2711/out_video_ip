"""自有 IP 生图 adapter（prompt_pack）：黑发短发女孩·蓝色短袖T恤（固定角色 + 固定水墨手绘风格）。
风格骨架吸收自 ian-xiaohei-illustrations（/Users/bainazi/Documents/outtt/other/2other_pic/
ian-xiaohei-illustrations，references/style-dna.md + prompt-template.md），角色替换为用户自有 IP
（参考图：assets/ip/*.png，第一张为基准形象）。

纪律：
- 角色锁（IP_LOCK）逐字固定：黑发短发女孩、蓝色短袖T恤、水墨/钢笔淡彩手绘。每次生图不改。
- 情绪固定：冷静、认真、略带好奇（deadpan-curious）。不许卖萌、不许儿童卡通。
- 动作轴随镜头 visual_intent 确定性映射（同 intent 同动作语言，画面收敛）。
- 风格固定：白纸底 + 墨线 + 淡彩（蓝 T 恤为唯一大面积彩色），红橙蓝批注色克制。
- 中文标注不进生图（模型会写错字）——标注一律由 Remotion 卡片槽渲染。
"""
from __future__ import annotations

import re
from pathlib import Path

from .base import ImagePromptAdapter

ROOT = Path(__file__).resolve().parents[2]
SRC = Path("/Users/bainazi/Documents/outtt/other/2other_pic/ian-xiaohei-illustrations/ian-xiaohei-illustrations")
IP_DIR = ROOT / "assets" / "ip"

# 固定画面风格预设：每个值是完整定格的风格 DNA 段，选哪个整段进 prompt（不自由发挥）
STYLE_PRESETS = {
    "ink-girl-standard": (
        "Visual DNA: warm white paper background, no texture overlay, no gradient, no heavy shadow. "
        "Ink pen line art with light watercolor washes, slightly wobbly hand-drawn strokes, not vector. "
        "Generous negative space: character and one core structure occupy 40-60% of canvas, at least "
        "35% stays blank. Color: black ink lines and hair; the blue of her T-shirt is the single "
        "dominant color accent; sparse orange/red annotation marks only where meaning requires."
    ),
    "flat-poster": (
        "Visual DNA: solid warm off-white background, flat bold color blocks, clean geometric shapes, "
        "thick uniform black outlines, minimal detail, poster-like composition. Generous negative "
        "space: character and one core structure occupy 40-60% of canvas. Color: limited palette of "
        "blue, cream, black with one small orange accent."
    ),
    "paper-collage": (
        "Visual DNA: cut-paper collage look, flat torn paper edges, subtle drop shadows between "
        "layers, warm off-white background, magazine collage feel. Generous negative space: "
        "character and one core structure occupy 40-60% of canvas. Color: blue paper for the T-shirt, "
        "cream and black paper dominant, one small red paper accent."
    ),
    "blueprint-line": (
        "Visual DNA: light blue-tinted paper, single-weight white and dark-blue technical line "
        "drawing, blueprint sketch feel, dotted construction lines, no shading. Generous negative "
        "space: character and one core structure occupy 40-60% of canvas. Character hair reads as "
        "solid dark-blue fill, T-shirt as flat mid-blue."
    ),
}

IP_LOCK = (
    "Recurring IP character required (must match the reference image identity): a young East Asian "
    "girl with short black bob hair and straight bangs, calm dark eyes, light skin, wearing a "
    "plain blue short-sleeve T-shirt. Ink-sketch illustration style consistent with the reference. "
    "She must perform the core conceptual action herself — carrying, pulling, sorting, operating, "
    "blocking, bridging, testing — never standing aside as decoration. Expression fixed: calm, "
    "focused, quietly curious (deadpan-curious). Never cute-ified, never childish, no extra "
    "outfits, no hairstyle changes, no accessories unless required by the action."
)

# visual_intent → 女孩的动作脚本（确定性映射：同 intent 同动作语言）
INTENT_ACTION = {
    "data": ("stacking and weighing small ink-drawn number blocks onto a simple balance scale", "数字块/天平"),
    "emphasis": ("holding up one large blank sign while the key object sits behind her", "空白举牌/主物件"),
    "comparison": ("standing between two distinct groups, pulling one rope that spans both", "两极拉线"),
    "before_after": ("pushing a paper divider that splits the frame into before and after halves", "分界闸门"),
    "process": ("turning a hand-crank that feeds objects through three connected stages", "三级传动"),
    "list": ("sorting identical items one by one into rows of empty bins", "分拣入格"),
    "quote": ("carrying a large blank speech bubble above her head while walking a thin ink line", "头顶气泡走线"),
    "ui": ("pressing one oversized button that triggers a small mechanical change", "超大按钮"),
    "scene": ("opening a small door in a big blank wall, revealing a tiny interior world", "墙上小门"),
    "character": ("carrying a stack of items that is clearly too big, calm-faced", "扛过大的堆"),
    "chart": ("climbing the bars of a hand-drawn bar chart like a ladder", "柱状梯"),
    "trend": ("riding an ink arrow that sweeps up across the frame", "乘箭头爬升"),
    "timeline": ("walking along a dashed path with three milestones", "里程碑小路"),
    "cause_effect": ("feeding a ball into a funnel that rolls out a changed shape", "漏斗变形"),
    "hierarchy": ("standing on top of stacked boxes looking calm", "叠箱顶站"),
    "focus": ("shining a small flashlight onto the single key object", "手电聚焦"),
    "concept": ("assembling an abstract shape from scattered ink parts", "散件拼形"),
    "relationship": ("connecting two nodes with a drawn line she holds at both ends", "双端连线"),
}
FALLBACK_ACTION = ("operating a strange but plausible ink-drawn machine that transforms input to output", "奇异小机器")

# 情绪/表情轴（夸张化）：intent → 表情描述。人物一致，表情按叙事放大。
EXPRESSION_PRESETS = {
    "data": "exaggerated wide-eyed astonishment, mouth open, eyebrows high",
    "emphasis": "big open-mouth shout, brows raised high, arm swung up",
    "comparison": "head tilted strongly, one eyebrow way up, skeptical grin",
    "before_after": "dramatic gasp, eyes wide, hands thrown up",
    "process": "intense determined squint, teeth clenched, leaning into the work",
    "list": " brisk excited pointing, big smile, eyes sparkling",
    "quote": "proud chest-out pose, eyes closed, huge satisfied grin",
    "ui": "startled jump-back, hands up, huge surprised eyes",
    "scene": "gentle awe, mouth slightly open, sparkling curious eyes",
    "character": "over-the-top strained effort, puffed cheeks, sweat drop",
    "chart": "triumphant fist pump, huge grin, eyes shining",
    "trend": "thrilled whoosh expression, hair blown back, big open smile",
    "timeline": "comically exhausted march, droopy eyes, tongue out",
    "cause_effect": "shocked realization, jaw dropped, pointing at the result",
    "hierarchy": "smug relaxed pose, chin up, tiny crown of confidence",
    "focus": "hyper-concentrated stare, one eye squinted, brow furrowed deep",
    "concept": "eureka expression, bulb-like spark above head, huge eyes",
    "relationship": "earnest pleading face, both hands pulling, full-body lean",
}
FALLBACK_EXPRESSION = "exaggerated surprised-curious face, big bright eyes, expressive brows"

# 界面可选的表情档位（下拉）
EXPRESSION_OPTIONS = [
    ("auto", "按意图自动（夸张）"),
    ("surprised", "夸张惊讶"),
    ("shout", "大喊/强调"),
    ("effort", "用力/吃力"),
    ("joy", "开心/得意"),
    ("focus", "极度专注"),
    ("skeptical", "怀疑/挑眉"),
]


def resolve_expression(shot: dict, choice: str | None = None) -> str:
    if choice and choice != "auto":
        return dict(EXPRESSION_OPTIONS).get(choice, FALLBACK_EXPRESSION)
    intents = shot.get("visual_intent") or []
    if isinstance(intents, str):
        intents = [intents]
    for it in intents:
        if it in EXPRESSION_PRESETS:
            return EXPRESSION_PRESETS[it]
    return FALLBACK_EXPRESSION


def pick_intent_action(shot: dict) -> tuple[str, str]:
    intents = shot.get("visual_intent") or []
    if isinstance(intents, str):
        intents = [intents]
    for it in intents:
        if it in INTENT_ACTION:
            return INTENT_ACTION[it]
    if intents:
        return INTENT_ACTION.get(str(intents[0]).strip(), FALLBACK_ACTION)
    return FALLBACK_ACTION


def _reference_image() -> str:
    """基准 IP 参考图（相对 project assets 的路径；喂给支持垫图的 ComfyUI 工作流）。"""
    if IP_DIR.is_dir():
        pngs = sorted(IP_DIR.glob("*.png"))
        if pngs:
            return f"assets/ip/{pngs[0].name}"
    return ""


def build_prompt(style_key: str, action: str, expression: str, scene: str, intent: str) -> str:
    """固定槽位 → prompt。唯一的拼装点：adapter.produce 与 studio 修改接口共用，
    保证界面结构化编辑与 S4B 自动生成产出同构的 prompt。"""
    preset = STYLE_PRESETS.get(style_key) or STYLE_PRESETS["ink-girl-standard"]
    return "\n".join([
        "Generate one standalone 16:9 horizontal illustration.",
        preset,
        IP_LOCK,
        f"Expression: {expression}. Push the emotion clearly beyond neutral — readable at a glance.",
        f"Scene action: the girl is {action}. One core action only.",
        f"Scene content (what happens, from the narration): {scene}",
        f"Narrative intent (visual meaning to express): {intent}",
        "Constraints: the picture must visualize the scene content above — specific objects, "
        "numbers-as-objects, places and situations the narration mentions, not a generic scene. "
        "The image contains no text of any kind: do not write, spell or scribble any characters, "
        "letters or numbers anywhere.",
    ])


class IpCharacterAdapter(ImagePromptAdapter):
    name = "ip-character"
    source_project = str(SRC)
    absorb_method = "prompt_pack"
    description = "自有 IP 生图（黑发短发女孩·蓝色短袖T恤；水墨手绘固定风格；情绪/动作确定性映射）"

    def available(self) -> tuple[bool, str]:
        if not _reference_image():
            return False, "缺 IP 参考图（assets/ip/*.png）"
        if not (SRC / "references" / "style-dna.md").exists():
            return True, "IP 参考图就绪（小黑风格源缺失，仅用内置风格 DNA）"
        return True, "IP 参考图 + 风格 DNA + intent→动作映射就绪"

    def styles(self) -> list[str]:
        """固定风格预设清单：每个都是定格 DNA，作为数据格式卡槽供编排选择。"""
        return list(STYLE_PRESETS.keys())

    def produce(self, shot: dict, style: str | None = None) -> dict:
        """固定槽位 JSON → prompt。字段全部来自上一阶段语义规划结果，不做自由发挥：
        style_dna（固定预设整段）+ character_lock（逐字固定）+ action/intent（映射表）
        + elements（映射表）。绝不喂中文原文（防模型画出乱码文字）。"""
        intent = (shot.get("intent") or shot.get("visual") or "").strip()
        style_key = style if style in STYLE_PRESETS else "ink-girl-standard"
        action, elems = pick_intent_action(shot)
        expression = resolve_expression(shot, (shot.get("expression") or "auto"))
        scene = re.sub(r"\s+", " ", (shot.get("vo") or "").strip())[:120]
        prompt = build_prompt(style_key, action, expression, scene, intent[:60])
        return {
            "prompt": prompt,
            "style": style_key,
            "aspect": "16:9",
            "reference_image": _reference_image(),
            # 结构化槽位：素材页按字段展示/修改（不暴露自由文本 prompt）
            "slots": {
                "style": style_key,
                "action": action,
                "expression": "auto",
                "scene": scene,
                "intent": intent[:60],
            },
            "notes": "固定槽位拼装；表情夸张轴；无文字；标注由 Remotion 槽位渲染",
        }

    def self_check(self) -> list[str]:
        errs = []
        for frag in ("short black bob hair", "blue short-sleeve T-shirt"):
            if frag not in IP_LOCK:
                errs.append(f"IP 锁缺失: {frag}")
        if len(EXPRESSION_PRESETS) < 10:
            errs.append("表情映射不完整")
        if not INTENT_ACTION:
            errs.append("intent→动作映射为空")
        return errs


ADAPTER = IpCharacterAdapter()
