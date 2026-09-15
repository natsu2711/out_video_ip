#!/usr/bin/env python3
"""S4B：分镜 → 图像资产任务单（assets/image_briefs.json）。

把注册的 image_prompt adapter（hand-drawn-styles / ian-xiaohei / …）按确定性轮换
分配给 B-roll 镜头，产出可直接喂给生图模型（GPT-Image-2 / ComfyUI）的完整 prompt。
生成图片后放入 assets/broll/ + manifest 登记 → S5 自动消费（契约见 docs/contracts.md）。

用法: s4b_image_briefs.py <job_dir> [--styles-per-shot N]
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.adapters import registry  # noqa: E402

# 语义路由推导（确定性）：S3 的 storyboard 未落 visual_intent 时，按关键词从
# 口播+意图句推导 intent 标签 → 驱动 adapter 的动作/表情映射（同意图同动作语言）
KEYWORD_INTENT = [
    ("数字", "data"), ("数据", "data"), ("百分之", "data"), ("万", "data"), ("倍", "data"),
    ("对比", "comparison"), ("比较", "comparison"), ("vs", "comparison"),
    ("以前", "before_after"), ("过去", "before_after"), ("曾经", "before_after"),
    ("现在", "before_after"), ("后来", "before_after"), ("之后", "before_after"),
    ("第一步", "process"), ("步骤", "process"), ("流程", "process"), ("然后", "process"),
    ("清单", "list"), ("几件事", "list"), ("三种", "list"), ("几个", "list"),
    ("因为", "cause_effect"), ("所以", "cause_effect"), ("导致", "cause_effect"),
    ("比如", "example"), ("举个例子", "example"), ("就像", "example"),
    ("总结", "hierarchy"), ("核心", "focus"), ("关键", "focus"), ("最重要", "focus"),
    ("路", "timeline"), ("阶段", "timeline"), ("第一", "timeline"),
    ("崩溃", "character"), ("麻木", "character"), ("焦虑", "character"), ("崩溃", "character"),
    ("我", "character"), ("你", "character"), ("人", "character"),
]


def derive_visual_intent(shot: dict) -> list[str]:
    text = f"{shot.get('vo', '')} {shot.get('intent', '')} {shot.get('visual', '')}"
    tags = []
    for kw, tag in KEYWORD_INTENT:
        if kw.lower() in text.lower() and tag not in tags:
            tags.append(tag)
        if len(tags) >= 3:
            break
    return tags or ["concept"]


def main() -> None:
    job = Path(sys.argv[1]).resolve()
    sb = json.loads((job / "storyboard.json").read_text(encoding="utf-8"))

    # 生图 adapter：默认锁定 ip-xiaohei（IP 形象为主、风格固定）；--adapter 可切换，
    # "all" 恢复旧的确定性轮换多画风模式
    pinned = None
    if "--adapter" in sys.argv:
        pinned = sys.argv[sys.argv.index("--adapter") + 1]
    elif "IP_ADAPTER" in os.environ:
        pinned = os.environ["IP_ADAPTER"]
    else:
        pinned = "ip-character"
    # 风格固定：默认 adapter 的第一个预设（人物/画风锁定，不轮换）；--style / IP_STYLE 可指定
    style_pin = None
    if "--style" in sys.argv:
        style_pin = sys.argv[sys.argv.index("--style") + 1]
    elif "IP_STYLE" in os.environ:
        style_pin = os.environ["IP_STYLE"]
    if pinned == "all":
        adapters = registry.by_capability("image_prompt")
    else:
        adapters = [a for a in registry.by_capability("image_prompt") if a.name == pinned]
        if not adapters:
            adapters = registry.by_capability("image_prompt")
            print(f"[s4b] ⚠ 指定 adapter {pinned} 不可用，回退 {[a.name for a in adapters]}", file=sys.stderr)
    if not adapters:
        print("[s4b] ⚠ 无可用 image_prompt adapter（生图任务单为可选环节，跳过）", file=sys.stderr)
        (job / "assets" / "image_briefs.json").parent.mkdir(exist_ok=True)
        (job / "assets" / "image_briefs.json").write_text("{}", "utf-8")
        sys.exit(0)
    print(f"[s4b] 可用画风 adapter: {[a.name for a in adapters]}")

    briefs = []
    k = 0
    for shot in sb["shots"]:
        # 只给 B-roll 生成图（A-roll 用 IP 形象）；text 类 B-roll 也可配底图
        if shot["roll"] != "B":
            continue
        adapter = adapters[k % len(adapters)]
        styles = adapter.styles()
        style = (style_pin if style_pin in styles else (styles[0] if styles else None))
        # 语义路由：storyboard 缺 visual_intent 时确定性推导，回写进 shot 副本（不改 storyboard）
        shot_sem = {**shot}
        if not shot_sem.get("visual_intent"):
            shot_sem["visual_intent"] = derive_visual_intent(shot)
        out = adapter.produce(shot_sem, style)
        semantic = {"visual_intent": shot_sem["visual_intent"], "beat": shot.get("beat") or "",
                    "intent_text": (shot.get("intent") or "")[:60]}
        briefs.append({
            "shot_id": shot["id"],
            "adapter": adapter.name,
            "style": out["style"],
            "aspect": out.get("aspect", "16:9"),
            "usage": f"{shot.get('b_type') or 'graphic'} 底图/配图",
            "intent": shot.get("intent", ""),
            "prompt": out["prompt"],
            "reference_image": out.get("reference_image", ""),
            "semantic": semantic,
            "slots": {**out.get("slots", {}), "intent": shot_sem.get("intent") or semantic["intent_text"]},
            "negative": ("text, letters, chinese characters, japanese characters, typography, "
                         "garbled text, gibberish letters, wrong characters, handwriting, "
                         "watermark, signature, logo, blurry, low quality, colorful background, "
                         "gradient, shadow, paper texture, cute mascot, children illustration"),
            "seed": None,
            "notes": out.get("notes", ""),
            "target_path": f"assets/broll/{shot['id']}.png",
        })
        k += 1

    out_path = job / "assets" / "image_briefs.json"
    out_path.write_text(json.dumps({
        "version": "1.0",
        "job_id": job.name,
        "briefs": briefs,
        "usage": "把 prompt+negative+seed 喂给 ComfyUI（scripts/s4e_local_images.py），图存到 target_path，S5 自动消费",
    }, ensure_ascii=False, indent=1), "utf-8")
    print(f"[s4b] ✔ {len(briefs)} 条图像任务单 → {out_path}")
    for b in briefs[:3]:
        print(f"  {b['shot_id']} [{b['adapter']}/{b['style']}] {b['prompt'][:60].replace(chr(10), ' ')}...")


if __name__ == "__main__":
    main()
