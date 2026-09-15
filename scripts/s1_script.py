#!/usr/bin/env python3
"""S1：任意文字稿 → script.json（数据契约见 schemas/script.schema.json）。

分层（每层可单独替换）：
  L1 标注层（LLM 可选）：分句 + beat 标签 + visual_hint + 数字转汉字（talkcraft 铁律：
     时间戳按文本逐字锚定，「197747」无法与「十九万七千」对位）
  L2 兜底层（纯规则）：标点分句 + 长句二次切，beat 全部 point——结构合法，文案零改写
产出经 schema 校验，失败即 exit 1（fail-fast，s2 不会拿到坏数据）。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import fallback, llm  # noqa: E402
from pipeline.validate import require  # noqa: E402

PROMPT = """你是口播短视频的脚本结构师。把下面的原始文稿整理成 JSON。

铁律：
1. 数字一律汉字写法（如 197747 → 十九万七千七百四十七、3天 → 三天、300美元 → 三百美元）
2. 【豁免】以下 token 保持原样，禁止改写：{protected}（型号/单位/版本号/比例——ASR 对英文数字串更稳，拆碎会破坏词义）
3. 每段一个信息点，8~40 字；口播语感（长书面句拆成短口播句）
4. 保留原意，不新增事实

输出 JSON（不要任何解释）：
{{"meta": {{"hook": "开场钩子一句话", "closing": "收尾一句话"}},
  "segments": [{{"id": "seg001", "text": "...", "beat": "hook|point|step|case|contrast|cta 之一",
               "visual_hint": "scene|graphic|quote|real 之一"}}]}}

segment 数控制在 {n_hint} 段左右（全文约 {chars} 字）。

原始文稿：
---
{story}
---"""


def scan_protected(text: str) -> list[str]:
    """数字豁免（protected tokens）：型号/单位/版本号/比例保留原样，按出现顺序去重保序。"""
    patterns = [
        re.compile(r"[A-Za-z][A-Za-z0-9]*[-_ ]?\d+[A-Za-z0-9]*"),   # iPhone 15 / GPT-4 / H264
        re.compile(r"\d+(?:\.\d+)?(?:Hz|hz|px|fps|GB|MB|KB|kb|km|kg|mm|cm|ms)"),  # 120Hz / 36GB
        re.compile(r"\d+[:/]\d+"),                                  # 16:9 比例
    ]
    out: list[str] = []
    for pat in patterns:
        for m in pat.finditer(text):
            tok = m.group(0)
            if tok not in out:
                out.append(tok)
    return out


def attach_protected(segs: list[dict], tokens: list[str]) -> int:
    """在 segments 内定位受保护 token 的字符区间（S2 合并对齐碎片用）。返回未命中数。"""
    for s in segs:
        pts = [{"token": t, "char_start": i, "char_end": i + len(t)}
               for t in tokens if (i := s["text"].find(t)) >= 0]
        if pts:
            s["protected_tokens"] = pts
    found = {p["token"] for s in segs for p in s.get("protected_tokens", [])}
    return len([t for t in tokens if t not in found])


def rule_segments(story: str) -> list[dict]:
    out = []
    for i, s in enumerate(fallback.split_sentences(story), 1):
        beat = "hook" if i == 1 else ("cta" if i == max(1, len(out)) else "point")
        out.append({"id": f"seg{i:03d}", "text": s, "beat": beat})
    return out


def llm_segments(story: str, protected: list[str] | None = None) -> tuple[list[dict] | None, str]:
    n_hint = max(6, len(story) // 35)
    try:
        obj, prov = llm.complete_json(
            PROMPT.format(story=story, chars=len(story), n_hint=n_hint,
                          protected="、".join(protected) if protected else "（无）"),
            system="你是严谨的脚本结构师，只输出 JSON。",
            business_check=lambda o: (
                [f"segments 为空"] if not o.get("segments")
                else [f"seg {s.get('id')} 缺 text" for s in o["segments"] if not (s.get("text") or "").strip()]
            ),
        )
        segs = obj["segments"]
        for i, s in enumerate(segs, 1):
            s.setdefault("id", f"seg{i:03d}")
            s["text"] = re.sub(r"\s+", "", s["text"])
        return segs, prov
    except llm.LLMChainError as e:
        print(f"[s1] LLM 不可用，走规则兜底: {e}")
        return None, "rule-fallback"


def main() -> None:
    job = Path(sys.argv[1]).resolve()
    story_path = job / "story.md"
    if not story_path.exists():
        print(f"[s1] ✗ 找不到 {story_path}", file=sys.stderr)
        sys.exit(1)
    story = story_path.read_text(encoding="utf-8")
    story = re.sub(r"^#.*$", "", story, flags=re.M)  # 去 markdown 标题行
    story = re.sub(r"\n{2,}", "\n", story).strip()
    protected = scan_protected(story)

    segs, prov = llm_segments(story, protected)
    if segs is None:
        segs = rule_segments(story)
        prov = "rule-fallback"
    missed = attach_protected(segs, protected)

    doc = {
        "version": "1.0",
        "job_id": job.name,
        "source": "story.md",
        "meta": {
            "hook": next((s["text"] for s in segs if s.get("beat") == "hook"), segs[0]["text"]),
            "closing": segs[-1]["text"],
            "char_count": sum(len(s["text"]) for s in segs),
            "est_duration_sec": round(sum(len(s["text"]) for s in segs) / 4.5, 1),
            "protected_tokens": protected,
        },
        "segments": segs,
    }
    out = job / "script.json"
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), "utf-8")
    require("script", out)  # fail-fast
    print(f"[s1] ✔ script.json：{len(segs)} 段（来源: {prov}；受保护 token {len(protected)} 个" + (f"，未命中 {missed}" if missed else "") + "）")


if __name__ == "__main__":
    main()
