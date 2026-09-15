"""Deterministic Visual Compiler（影子阶段）：Visual IR → 镜头配置（与 storyboard 镜头同构，S5 零改动）。

纯函数铁律：同 IR + 同镜头序 → 同输出。禁随机/禁时间/禁网络/禁 LLM。
确定性检验口径：visual_plan（本模块输出）逐字节一致；渲染像素一致性归 pixelmatch 容差。
v0 原语来源 = 现有卡片库中 injectable 的稳定版面（卡片→Primitive 迁移第一步）。
映射规则：contrast / point / step 三条（docs/stage-contracts.md §S4）；其余 beat 返回 None 走现有管线。
影子协议：本模块输出只写入 storyboard 的 compiler_plan 字段，不替换现有配卡——胜负由 S7 消融判定。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_REGISTRY: dict | None = None

RELATION_BY_BEAT = {
    "hook": "single", "point": "single", "step": "sequence", "case": "single",
    "contrast": "contrast", "quote": "single", "cta": "single",
}


def _registry() -> dict:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = json.loads((ROOT / "render-engine" / "src" / "cards" / "registry.json").read_text("utf-8"))
    return _REGISTRY


def _cap16(a: list[str]) -> list[str]:
    return [t if len(t) <= 16 else t[:15] + "…" for t in a]


def extract_anchors(text: str) -> list[str]:
    """锚词：引号词 > 数字（与渲染端 content.ts 同口径）。"""
    out = re.findall(r"[「『]([^」』]+)[」』]", text)
    out += re.findall(r"[0-9一二两三四五六七八九十百千万亿%％.]+(?:个|天|周|年|块|倍|%|％)?", text)
    seen, uniq = set(), []
    for t in out:
        t = t.strip()
        if t and t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq[:2]


def derive_ir(beat: str | None, group_idx: int, total: int, text: str,
              visual_hint: str | None = None) -> dict:
    """规则版 IR（LLM 版待影子实验胜出后接入）；relation 按 beat、rhythm 按段位置。"""
    relation = RELATION_BY_BEAT.get(beat or "", "single")
    if group_idx == 0:
        rhythm = "open"
    elif group_idx == total - 1:
        rhythm = "close"
    elif beat in ("contrast", "case"):
        rhythm = "turn"
    else:
        rhythm = "build"
    return {
        "beat": beat or "point",
        "relation": relation,
        "rhythm": rhythm,
        "abstraction": "concrete" if visual_hint == "scene" else "abstract",
        "emphasis": {"anchor_words": extract_anchors(text)},
    }


def _texts(ir: dict, vo: str, n: int) -> list[str]:
    anchors = ir.get("emphasis", {}).get("anchor_words") or []
    pool = anchors + [vo[:12]]
    return _cap16([(pool[i % len(pool)] if pool else "要点") for i in range(n)])


def compile_shot(ir: dict, shot_idx: int, vo: str = "") -> dict | None:
    """IR → 镜头配置（recipe_ref/config/presentation/overlay）。无映射规则的 beat → None。"""
    beat, rhythm = ir.get("beat"), ir.get("rhythm", "build")
    anchors = ir.get("emphasis", {}).get("anchor_words") or []

    if beat == "contrast":
        # 结构：对撞/渐变对比。v0 原语：impact-open-title（injectable；raw 对比卡待 Primitive 化）
        recipe = "impact-open-title"
        presentation = "slam_in" if rhythm == "turn" else "rise_fade"
        config = {"TEXT": _cap16(anchors) if anchors else _texts(ir, vo, 1)}
    elif beat == "point":
        # 结构：论点+论据。有数字锚 → 计数器；渐进节奏 → 汇聚箭头
        has_number = bool(re.search(r"[0-9一二两三四五六七八九十百千万亿]", "".join(anchors)))
        recipe = "number-counter" if has_number else "converging-arrows"
        presentation = "slam_in" if rhythm == "open" else "blur_focus"
        n = _registry()[recipe]["arities"]["TEXT"]
        config = {"TEXT": _texts(ir, vo, n)}
    elif beat == "step":
        # 结构：步骤序列。收束节奏 → 纵向时间轴；否则阶梯堆叠
        recipe = "step-timeline-vertical" if rhythm == "close" else "numbered-step-stack"
        presentation = "rise_fade"
        n = _registry()[recipe]["arities"]["STEPS"]
        config = {"STEPS": _texts(ir, vo, n)}
    else:
        return None

    # overlay 单一来源：复用现有叠层轮换（decoration 与 overlay 正交规则不变）
    from pipeline.variety import card_overlay
    return {
        "recipe_ref": f"card:{recipe}",
        "config": config,
        "presentation": presentation,
        "overlay": card_overlay(shot_idx),
    }


def is_deterministic(ir: dict, shot_idx: int, vo: str, rounds: int = 3) -> bool:
    """确定性自检：多轮编译逐字节一致。"""
    outs = [json.dumps(compile_shot(ir, shot_idx, vo), sort_keys=True, ensure_ascii=False) for _ in range(rounds)]
    return len(set(outs)) == 1
