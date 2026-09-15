#!/usr/bin/env python3
"""S3：script.json + timing.json → storyboard.json（数据契约见 schemas/storyboard.schema.json）。

四层架构（每层可单独替换/重跑——「不稳定就加一层」）：
  L1 分组层（纯规则）：timing 语句级段落 → 镜头时间分组（3~8s 一镜，确定性）
  L2 配卡层（LLM 可选，逐组小任务）：每组只选一个配方 + 写画面指令——输出小，弱模型也能稳；
     单组失败只降级该组（规则配卡），不拖垮全片
  L3 装配层（纯规则）：A/B 策略、视角轮换、首尾镜、转场
  L4 验收层（确定性）：schema + lint（节奏铁律 + 反单调）；违规 → 局部规则覆盖修复
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import fallback, lint, llm, variety  # noqa: E402
from pipeline.validate import require  # noqa: E402

CARD_SLUGS: set = set()
CARD_MENU = ""

# C-roll 叠层规则（模块级：装配与重排共用——配方变更必须同步重算叠层，实测踩坑：rebalance 换配方后旧叠层残留）
OVERLAY_RULES = {
    "TransformCard": ["light_sweep"],
    "QuoteCard": ["vignette"],
    "ARollScene": [],                     # IP 镜头保持干净
    "StepsCard": [],
    "ListGrid": ["grain"],
    "EndingCard": ["particles", "tint_warm"],
    "TitleCard": [],
}
CARD_OVERLAY_CYCLE = [["grain"], ["light_sweep"], ["particles"], ["tint_cool", "grain"], ["snow"], ["embers"]]  # 单一来源在 variety（影子编译器共用）


PRESENTATION_RULES = {
    "TitleCard": "none",       # 自带三拍砸入，不再叠加
    "EndingCard": "rise_fade",
    "ARollScene": "blur_focus",
    "TransformCard": "slam_in",
    "QuoteCard": "wipe_mask",
    "StepsCard": "rise_fade",
    "ListGrid": "wipe_mask",
}
CARD_PRESENTATION_CYCLE = ["slam_in", "wipe_mask", "blur_focus", "rise_fade"]


def assign_presentation(recipe: str, i: int) -> str:
    """呈现层单一来源：装配与重排共用——配方变更必须同步重算（叠层残留教训）。"""
    if recipe in PRESENTATION_RULES:
        return PRESENTATION_RULES[recipe]
    if recipe.startswith("card:"):
        return CARD_PRESENTATION_CYCLE[i % len(CARD_PRESENTATION_CYCLE)]
    return "rise_fade"


def assign_overlay(recipe: str, i: int) -> list[str]:
    if recipe in OVERLAY_RULES:
        return list(OVERLAY_RULES[recipe])
    if recipe.startswith("card:"):
        return list(CARD_OVERLAY_CYCLE[i % len(CARD_OVERLAY_CYCLE)])
    return []

RECIPES = ["TitleCard", "QuoteCard", "ARollScene", "StepsCard",
           "TransformCard", "ListGrid", "EndingCard"]


def load_card_catalog(max_cards: int = 24, seed: str = "") -> list[dict]:
    """移植卡目录（injectable only）：确定性抽样进 LLM prompt（控上下文长度）。
    返回 [{slug, desc}]；无 registry.json 返回空（纯自研配方路径照常）。"""
    reg_path = ROOT / "render-engine" / "src" / "cards" / "registry.json"
    if not reg_path.exists():
        return []
    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    injectable = [
        {"slug": slug, "desc": e.get("desc", slug)}
        for slug, e in sorted(reg.items())
        if e.get("tier") == "injectable"
    ]
    if len(injectable) <= max_cards:
        return injectable
    import hashlib
    digest = hashlib.sha256(seed.encode()).digest()
    order = sorted(range(len(injectable)), key=lambda i: digest[i % 32])
    return [injectable[i] for i in sorted(order[:max_cards])]


def _card_menu(catalog: list[dict]) -> str:
    """按 beat 语义分组的卡菜单（受控多样性：LLM 在白名单池内选，不自由发挥）。
    分组映射来自 pipeline/variety.BEAT_CARDS。"""
    if not catalog:
        return ""
    from pipeline.variety import BEAT_CARDS
    known = {c["slug"] for c in catalog}
    by_group: dict[str, list[str]] = {}
    for beat, slugs in BEAT_CARDS.items():
        hits = [s for s in slugs if s.startswith("card:") and s[5:] in known]
        if hits:
            by_group[beat] = [f"card:{s}" for s in hits]
    lines = [f"{beat}类: {'、'.join(slugs)}" for beat, slugs in by_group.items()]
    return ("\n另有移植动效卡（以 card: 开头，动效更丰富，按语义组选，贴标签的组优先）：\n"
            + "\n".join(lines) + "\n")


SHOT_PROMPT = """你是短视频分镜师。给下面这组口播选画面配方并写画面指令。

可选配方（只能选一个）：
TitleCard(开场大字卡) QuoteCard(金句卡) ARollScene(IP形象+场景图)
StepsCard(步骤1→2→3) TransformCard(以前↓现在 对比) ListGrid(清单网格)
{card_menu}
这组口播：{vo}
片子里它前一组用的配方：{prev}

输出 JSON（不要解释）：
{{"recipe_ref": "配方名",
  "intent": "这组画面的意图，≤14字",
  "visual": "画面内容描述，≤40字",
  "motion": ["节拍1", "节拍2"],
  "view_angle": "若选 ARollScene 填 host|protagonist|pov 之一，否则 null",
  "b_type": "text|graphic|real 之一"}}

要求：motion 必须真实响应文案（引号词/数字优先做节拍）；配方选择要与前一组错开。"""


# ---------------- L1 分组层（纯规则） ----------------

def group_segments(timing: dict, target_min: float = 3.0, target_max: float = 8.0) -> list[dict]:
    segs = timing["segments"]
    groups, cur, start = [], [], segs[0]["start_ms"]
    for s in segs:
        cur.append(s)
        dur = (s["end_ms"] - start) / 1000
        text = "".join(c["text"] for c in cur)
        # 句边界且达标 → 切组；超上限强切
        if dur >= target_min and text.endswith(("。", "！", "？", "；")) or dur >= target_max:
            groups.append({"start_ms": start, "end_ms": s["end_ms"], "segs": cur})
            cur, start = [], s["end_ms"]
    if cur:
        groups.append({"start_ms": start, "end_ms": segs[-1]["end_ms"], "segs": cur})
    # 末组过短 → 并入前组
    if len(groups) >= 2 and (groups[-1]["end_ms"] - groups[-1]["start_ms"]) < 2000:
        last = groups.pop()
        groups[-1]["end_ms"] = last["end_ms"]
        groups[-1]["segs"].extend(last["segs"])
    return groups


# ---------------- L2 配卡层（路由模式二选一：auto=确定性规则 / llm=大模型，读 studio.json） ----------------

def load_route_mode(job) -> str:
    """路由模式：job/studio.json 的 route_mode（auto|llm），env S3_ROUTE_MODE 可覆盖，缺省 llm（历史行为）。"""
    mode = "llm"
    sj = job / "studio.json"
    if sj.exists():
        try:
            mode = json.loads(sj.read_text(encoding="utf-8")).get("route_mode", mode)
        except Exception:  # noqa: BLE001
            pass
    import os
    if os.environ.get("S3_ROUTE_MODE"):
        mode = os.environ["S3_ROUTE_MODE"]
    return mode if mode in ("auto", "llm") else "llm"


def assign_card(group: dict, prev_recipe: str, used: Counter, cap: int,
                is_first: bool, is_last: bool, beat: str | None = None,
                group_idx: int = 0, mode: str = "llm",
                recent: list[str] | None = None) -> tuple[dict, str]:
    vo = "".join(s["text"] for s in group["segs"])
    recent = recent or []
    if is_first:
        return ({"recipe_ref": "TitleCard", "intent": vo[:14], "b_type": "text",
                 "motion": fallback.motion_from_text(vo), "view_angle": None}, "规则(首镜)")
    if is_last:
        return ({"recipe_ref": "EndingCard", "intent": vo[:14], "b_type": "text",
                 "motion": ["主体收束", "行动号召弹出"], "view_angle": None}, "规则(末镜)")
    if mode == "auto":
        # 自动路由（确定性三级）：① 元数据检索（spec §6 Hard Filter+打分，含 SLOTS/TEXT 槽位偏好）
        # → ② 本地组件关键词命中 → ③ beat 白名单池轮换（保底王）。全程无 LLM。
        r_meta = variety.pick_candidate_meta(beat or "point", group_idx, used, cap, recent)
        if r_meta:
            return ({"recipe_ref": f"card:{r_meta}", "intent": vo[:14], "b_type": "graphic",
                     "motion": fallback.motion_from_text(vo), "view_angle": None}, f"检索({beat or 'point'})")
        r, prov = fallback.pick_recipe(vo, group_idx, dict(used), cap)
        if prov == "关键词命中" and used.get(r, 0) < cap:
            return ({"recipe_ref": r, "intent": vo[:14], "b_type": "graphic",
                     "motion": fallback.motion_from_text(vo), "view_angle": None}, "路由(auto/关键词)")
        r = variety.pick_candidate(beat or "point", group_idx, used, cap, recent)
        return ({"recipe_ref": r, "intent": vo[:14], "b_type": "graphic",
                 "motion": fallback.motion_from_text(vo), "view_angle": None}, f"路由(auto/{beat or 'point'})")
    try:
        obj, prov = llm.complete_json(
            SHOT_PROMPT.format(vo=vo, prev=prev_recipe, card_menu=CARD_MENU),
            system="你是分镜师，只输出 JSON。",
            business_check=lambda o: (
                []
                if (o.get("recipe_ref") in RECIPES
                    or (isinstance(o.get("recipe_ref"), str)
                        and o["recipe_ref"].startswith("card:")
                        and o["recipe_ref"][5:] in CARD_SLUGS))
                and (o.get("intent") or "").strip()
                and isinstance(o.get("motion"), list) and o["motion"]
                else ["recipe_ref 必须是可选配方之一（或 card: 移植卡），intent 非空，motion 为非空数组"]
            ),
        )
        if used.get(obj["recipe_ref"], 0) >= cap and obj["recipe_ref"] not in ("TitleCard", "EndingCard"):
            obj["recipe_ref"] = fallback.pick_recipe(vo, 0, dict(used), cap)[0]  # 超 diversity 限额 → 规则改配
            prov += "+规则改配"
        return obj, prov
    except llm.LLMChainError:
        # 保底王：不走关键词配卡，直接用 beat 固定保底结构族（同族变体按组序轮换防模板疲劳）
        r = fallback.beat_fallback(beat, group_idx)
        return ({"recipe_ref": r, "intent": vo[:14], "b_type": "graphic",
                 "motion": fallback.motion_from_text(vo), "view_angle": None,
                 "degraded": True}, f"保底王({beat or 'point'})")


# ---------------- L3 装配层（纯规则） ----------------

def assemble(groups: list[dict], cards: list[dict], job_id: str) -> dict:
    shots, view_i = [], 0
    aroll_positions = [i for i, c in enumerate(cards) if c["recipe_ref"] == "ARollScene"]
    for i, (g, c) in enumerate(zip(groups, cards)):
        recipe = c["recipe_ref"]
        roll = "A" if recipe == "ARollScene" else "B"
        view_angle = c.get("view_angle")
        if recipe == "ARollScene":
            if not view_angle or view_angle == "null":
                view_angle = fallback.VIEW_CYCLE[view_i % len(fallback.VIEW_CYCLE)]
            view_i += 1
        shots.append({
            "id": f"S{i + 1:03d}",
            "time": {"start_ms": g["start_ms"], "end_ms": g["end_ms"],
                     "seg_ids": [s["id"] for s in g["segs"]]},
            "vo": "".join(s["text"] for s in g["segs"]),
            "roll": roll,
            "b_type": None if roll == "A" else (c.get("b_type") if c.get("b_type") in ("text", "graphic", "real") else "graphic"),
            "view_angle": view_angle if roll == "A" else None,
            "intent": (c.get("intent") or "")[:20],
            "visual": c.get("visual") or g and "".join(s["text"] for s in g["segs"])[:40],
            "motion": (c.get("motion") or ["主体入场"])[:3],
            "transition_in": "push-through" if i in aroll_positions else "cut",
            "recipe_ref": recipe,
            "assets_needed": ["ip_image"] if roll == "A" else [],
            "overlay": assign_overlay(recipe, i),
            "presentation": assign_presentation(recipe, i),
            "degraded": bool(c.get("degraded")),
            "status": "pending",
        })
    a = sum(1 for s in shots if s["roll"] == "A")
    deg = [s["id"] for s in shots if s.get("degraded")]
    sb = {"version": "1.0", "job_id": job_id, "shots": shots,
          "rhythm_check": {"a_b_ratio": [a, len(shots) - a]}}
    if deg:
        sb["meta"] = {"degraded_groups": deg}   # 降级组清单（编排表 ⚠️ 标记）
    return sb


# ---------------- L4 验收层（schema + lint，违规一次性确定性重排） ----------------

def rebalance(sb: dict) -> list[str]:
    """反单调违规 → 确定性一次收敛重排（不再逐错修复——逐错会震荡：改 A-roll 制造 B 连跑，改回又制造间隔违规）。

    策略：先固定 A-roll 均匀落位（间距天然 ≥AROLL_GAP、B 连跑天然 ≤间隔）；
    其余镜保留 LLM 配方，仅在与前镜重复或超限时换卡。LLM 文案全保留，只换配方标签。"""
    shots = sb["shots"]
    n = len(shots)
    # A-roll 均匀分布格点：a_count 受 max_fit/cap 双约束，在 [2, n-2] 等距铺开
    # （旧固定步长在尾部留 4 连 B——实测踩坑 S019；等距铺开间距天然 ≥AROLL_GAP）
    desired = max(3, round(n * 0.3))
    max_fit = len(range(2, max(2, n - 1), lint.AROLL_GAP + 1))
    cap = lint._cap(n)
    a_count = min(desired, max_fit, cap)  # A-roll 也受全片配方 cap 约束（19 镜 desired=6 > cap=5 实测踩坑）
    if a_count >= 2:
        # A-roll 铺点：首 A@3（首段 B = idx0-2 恰 3 个 ≤lint 上限），末 A ≤ n-4（尾段 B ≤3），
        # 中段间距在 [AROLL_GAP+1, 4] 内均分（间距 <4 → B 连跑 ≤3；>3 → A-roll 间隔达标）。
        first, last = 3, max(3, n - 4)
        span = max(0, last - first)
        base, extra = divmod(span, a_count - 1)
        gaps = [min(4, max(lint.AROLL_GAP + 1, base + (1 if i < extra else 0)))
                for i in range(a_count - 1)]
        a_pos_list = [first]
        for g in gaps:
            nxt = a_pos_list[-1] + g
            if nxt > n - 2:
                break
            a_pos_list.append(nxt)
        a_pos = set(a_pos_list)
    else:
        a_pos = {2}
    used: Counter = Counter()
    view_i = 0
    prev_recipe = None
    for i, s in enumerate(shots):
        if i == 0:
            want = "TitleCard"
        elif i == n - 1:
            want = "EndingCard"
        elif i in a_pos:
            want = "ARollScene"
        else:
            want = s["recipe_ref"]
            if want == "ARollScene" or used.get(want, 0) >= cap:  # 不在 A 位或超限 → 换成 B 配方
                want = fallback.pick_recipe(s["vo"], i, dict(used), cap)[0]
                if want == "ARollScene":  # pick_recipe 可能又命中 ARollScene（实测踩坑）→ 硬排除
                    want = next((r for r in fallback.ROTATION
                                 if r != "ARollScene" and used.get(r, 0) < cap), "QuoteCard")
        if want == prev_recipe and i not in (0, n - 1):
            want = fallback.pick_recipe(s["vo"], i, {**dict(used), want: cap}, cap)[0]
            if want == prev_recipe:  # 兑底轮换里再避前镜
                want = next((r for r in fallback.ROTATION
                             if r != prev_recipe and used.get(r, 0) < cap), "ListGrid")
        # 终守卫：非 A 位绝不落 ARollScene（查重分支的 pick_recipe 也可能命中，实测踩坑）
        if i not in (0, n - 1) and want == "ARollScene" and i not in a_pos:
            want = next((r for r in fallback.ROTATION
                         if r != "ARollScene" and r != prev_recipe and used.get(r, 0) < cap), "QuoteCard")
        # 应用（叠层随配方同步重算——层与主体一致性由机器保证）；
        # 配方被 rebalance 改写 → 不再是 LLM 降级保底王，清 degraded 标记
        if want != s["recipe_ref"]:
            s["degraded"] = False
        s["recipe_ref"] = want
        s["overlay"] = assign_overlay(want, i)
        s["presentation"] = assign_presentation(want, i)
        used[want] += 1
        if want == "ARollScene":
            s["roll"] = "A"
            s["view_angle"] = fallback.VIEW_CYCLE[view_i % len(fallback.VIEW_CYCLE)]
            view_i += 1
            s["b_type"] = None
        else:
            if want in ("TitleCard", "EndingCard"):
                s["roll"] = "B"
            else:
                s["roll"] = "B"
            s["view_angle"] = None
            if s.get("b_type") is None:
                s["b_type"] = "graphic"
        prev_recipe = want
    return lint.lint_storyboard(sb)


def main() -> None:
    job = Path(sys.argv[1]).resolve()
    timing = json.loads((job / "timing.json").read_text(encoding="utf-8"))
    script = json.loads((job / "script.json").read_text(encoding="utf-8"))

    # 移植卡目录（确定性抽样，job_id 做 seed → 同 job 复现）
    global CARD_SLUGS, CARD_MENU
    catalog = load_card_catalog(seed=job.name)
    CARD_SLUGS = {c["slug"] for c in catalog}
    CARD_MENU = _card_menu(catalog)
    if catalog:
        print(f"[s3] 移植卡目录: {len(catalog)} 张可选中（共 79 张已移植）")

    # L1 分组（纯规则）
    groups = group_segments(timing)
    print(f"[s3] L1 分组: {len(timing['segments'])} 句 → {len(groups)} 镜")

    # 组 beat：取组内首个 timing 段的 seg_ref → script segment 的 beat（保底王/影子 IR 用）
    seg_beats = {f"seg{i:03d}": s.get("beat") for i, s in enumerate(script.get("segments", []))}
    for g in groups:
        g["beat"] = next((seg_beats.get(s.get("seg_ref")) for s in g["segs"] if seg_beats.get(s.get("seg_ref"))), None)

    # L2 配卡（路由模式二选一：auto=确定性规则 / llm=大模型；studio.json 数据开关）
    route_mode = load_route_mode(job)
    print(f"[s3] 路由模式: {route_mode}" + ("（本地确定性规则，无 LLM）" if route_mode == "auto" else "（大模型选卡，白名单池内）"))
    cards, provs = [], Counter()
    used: Counter = Counter()
    recent: list[str] = []
    cap = lint._cap(len(groups))
    for i, g in enumerate(groups):
        c, p = assign_card(g, cards[-1]["recipe_ref"] if cards else "无",
                           used, cap, i == 0, i == len(groups) - 1, g.get("beat"), i,
                           mode=route_mode, recent=recent)
        used[c["recipe_ref"]] += 1
        recent.append(c["recipe_ref"])
        cards.append(c)
        provs[p.split("(")[0]] += 1
    print(f"[s3] L2 配卡: {dict(provs)}")

    # 移植卡确定性注入：卡位 = 中段 i%6∈{0,3} 且非 A-roll 格点（LLM 已选卡的位置保留）
    if catalog:
        cycle = [c["slug"] for c in catalog]
        k = 0
        for i in range(2, len(cards) - 1):
            if i % 6 in (0, 3) and not cards[i]["recipe_ref"].startswith("card:"):
                cards[i]["recipe_ref"] = f"card:{cycle[k % len(cycle)]}"
                k += 1
        print(f"[s3] 卡位注入: {k} 镜用移植卡")

    # L3 装配 + L4 验收重排（一次收敛）
    sb = assemble(groups, cards, job.name)
    remain = rebalance(sb)

    # 影子编译器：规则版 Visual IR + compiler_plan 只存不渲（胜负由 S7 消融判定）
    from pipeline import visual_compiler as vc
    total = len(sb["shots"])
    for i, shot in enumerate(sb["shots"]):
        if shot["roll"] == "A" or shot["recipe_ref"] in ("TitleCard", "EndingCard"):
            continue
        beat = groups[i]["beat"] if i < len(groups) else None
        if beat not in vc.RELATION_BY_BEAT or beat in ("hook", "quote", "cta"):
            continue
        ir = vc.derive_ir(beat, i, total, shot["vo"], (shot.get("visual_hint") or shot.get("b_type")))
        shot["ir"] = ir
        shot["compiler_plan"] = vc.compile_shot(ir, i, shot["vo"])
    n_shadow = sum(1 for s in sb["shots"] if s.get("compiler_plan"))
    if n_shadow:
        print(f"[s3] 影子编译器: {n_shadow} 镜产出 compiler_plan（不渲染，仅供消融）")
    a = sum(1 for s in sb["shots"] if s["roll"] == "A")
    sb["rhythm_check"] = {"a_b_ratio": [a, len(sb["shots"]) - a]}
    if remain:
        print("[s3] ✗ lint 仍有未清项:", remain, file=sys.stderr)
        sys.exit(1)

    out = job / "storyboard.json"
    out.write_text(json.dumps(sb, ensure_ascii=False, indent=2), "utf-8")
    require("storyboard", out)
    print(f"[s3] ✔ storyboard.json：{len(sb['shots'])} 镜, A/B={sb['rhythm_check']['a_b_ratio']}, "
          f"配方分布={dict(Counter(s['recipe_ref'] for s in sb['shots']))}")


if __name__ == "__main__":
    main()
