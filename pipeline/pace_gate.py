"""节奏/字数预算闸（消融特征：abl_a2e_pacing_gate + abl_firered_chars_budget）。

规则来源：
  - anything2explainer `reference/narration-storyboard.md` §1：每句 ≤35 字；字幕块（|）≤16 字；
    成片时长与预估偏差 >15% → 加/删句子（不许调语速硬凑）；"每句都要能画"。
  - FireRed-OpenStoryline `prompts/tasks/generate_script/zh/system.md`：分段字数预算硬约束
    （镜头时长 × 语速反推 min/max，可校验、可 lint）。

纯确定性：输入 script.json / timing.json / storyboard.json，输出可复算报告；不调 LLM。
建议级（不挡闸）：由 s3_check / ablation 消费。
"""
from __future__ import annotations

import re

# 口播语速基准（字/秒）：来自 s1 的 est_duration 口径并按本项目样片校准
CHARS_PER_SEC = 4.2
SENT_MAX = 35      # a2e：单句字数上限
BLOCK_MAX = 16     # a2e：字幕块字数上限（| 切分）
DEV_MAX = 0.15     # a2e：成片时长偏差上限
BUDGET_SLACK = 0.35  # FireRed：预算带宽（±35%，语速个体差异容忍）


def _blocks(text: str) -> list[str]:
    return [b for b in re.split(r"[|｜]", text) if b.strip()]


def sentence_report(script: dict) -> dict:
    segs = script.get("segments", [])
    over_sent = [(s["id"], len(s["text"])) for s in segs if len(s["text"]) > SENT_MAX]
    over_block = [(s["id"], len(b)) for s in segs for b in _blocks(s["text"]) if len(b) > BLOCK_MAX]
    lens = [len(s["text"]) for s in segs] or [0]
    return {
        "句数": len(segs),
        "最长句": max(lens),
        "超长句(>35)": len(over_sent),
        "超长句明细": over_sent[:8],
        "超限字幕块(>16)": len(over_block),
    }


def observed_rate(timing: dict) -> float | None:
    """从 timing 实测语速（字/秒）——音色自适应，消融暴露 4.2 常数低估实测 6.6 后加入。"""
    segs = timing.get("segments", [])
    chars = sum(len(t.get("text", "")) for t in segs)
    dur = (timing.get("duration_ms") or 0) / 1000
    if chars <= 0 or dur <= 0:
        return None
    return chars / dur


def shot_budgets(storyboard: dict, timing: dict, rate: float | None = None) -> list[dict]:
    """FireRed 口径：每镜字数预算 = 时长 × 语速 ±带宽；超预算镜列出（供加/删句决策）。
    rate 缺省时用 timing 实测语速自校准（无 timing 才回退常数）。"""
    if rate is None:
        rate = observed_rate(timing) or CHARS_PER_SEC
    tmap = {t["id"]: t for t in timing.get("segments", [])}
    out = []
    for s in storyboard.get("shots", []):
        dur = (s["time"]["end_ms"] - s["time"]["start_ms"]) / 1000
        mid = dur * rate
        vo_len = len(s.get("vo", ""))
        seg_texts = [tmap[i]["text"] for i in s["time"].get("seg_ids", []) if i in tmap]
        seg_len = sum(len(t) for t in seg_texts)
        out.append({
            "shot": s["id"], "dur_s": round(dur, 2),
            "budget": [round(mid * (1 - BUDGET_SLACK)), round(mid * (1 + BUDGET_SLACK))],
            "vo_len": vo_len, "seg_len": seg_len,
            "over": bool(vo_len > mid * (1 + BUDGET_SLACK) or vo_len < mid * (1 - BUDGET_SLACK)),
        })
    return out


def duration_deviation(script: dict, timing: dict) -> dict:
    est = (script.get("meta") or {}).get("est_duration_sec")
    actual = timing.get("duration_ms", 0) / 1000
    if not est or not actual:
        return {"est": est, "actual": round(actual, 2), "dev": None, "over": False}
    dev = abs(actual - est) / max(1.0, est)
    return {"est": est, "actual": round(actual, 2), "dev": round(dev, 3), "over": dev > DEV_MAX}


def check(script: dict, timing: dict, storyboard: dict | None = None) -> dict:
    """完整节奏报告：句子规则 + 字数预算 + 时长偏差。全部可复算。
    预算语速自动从 timing 实测校准（音色自适应）。"""
    rep: dict = {"sentences": sentence_report(script), "duration": duration_deviation(script, timing)}
    rep["observed_rate"] = observed_rate(timing)
    rep["pace_violations"] = rep["sentences"]["超长句(>35)"] + rep["sentences"]["超限字幕块(>16)"] + (
        1 if rep["duration"]["over"] else 0)
    if storyboard is not None:
        budgets = shot_budgets(storyboard, timing)
        rep["budgets"] = {
            "语速基准": round(rep["observed_rate"] or CHARS_PER_SEC, 2),
            "镜数": len(budgets),
            "超预算镜": sum(1 for b in budgets if b["over"]),
            "明细": [b for b in budgets if b["over"]][:8],
        }
    return rep


def resplit_long_sentences(script: dict, sent_max: int = SENT_MAX) -> tuple[dict, int]:
    """消融变体用：把 >sent_max 的句在标点处确定性重切（不动 timing，供指标对比）。
    返回 (新 script, 重切句数)。保护 token 简化处理：只在标点边界切，不切词。"""
    import copy
    out = copy.deepcopy(script)
    n = 0
    new_segments = []
    for seg in out.get("segments", []):
        text = seg["text"]
        if len(text) <= sent_max:
            new_segments.append(seg)
            continue
        # 标点归并切分：累积到 ≤sent_max 且遇标点即断
        parts, cur = [], ""
        for ch in text:
            cur += ch
            if len(cur) >= sent_max and ch in "，、；。！？":
                parts.append(cur)
                cur = ""
        if cur:
            if parts and len(cur) < 8:
                parts[-1] += cur
            else:
                parts.append(cur)
        if len(parts) <= 1:
            new_segments.append(seg)
            continue
        n += 1
        for k, p in enumerate(parts):
            seg2 = dict(seg)
            seg2["text"] = p
            seg2["id"] = f"{seg['id']}x{k + 1}"
            new_segments.append(seg2)
    out["segments"] = new_segments
    return out, n
