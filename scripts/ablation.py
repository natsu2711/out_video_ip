#!/usr/bin/env python3
"""消融实验：对同一 job 的分镜/资产计划做特征开关变体，用既有确定性指标量化各特征贡献。

变体（每个 = 关掉/打开一个特征，其余不变）：
  baseline          原样
  no_handwritten    手写系 5 卡退出配卡词汇（受影响镜头按规则兜底重配）
  no_overlay        全部 C-roll 叠层清空
  no_image_adapters image_prompt 适配器全关（无生图任务）
  all_adapters      image_prompt 全量适配器轮换（风格组合最大化）

指标（全部确定性可复算，无需渲染）：
  配方多样性 = 唯一配方数 / 镜头数；最大配方占比；生图任务数；风格组合数；叠层镜数；lint 错误数。

用法: ablation.py <job_dir> [--out docs/ablation.md]
"""
from __future__ import annotations

import copy
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import fallback, lint, variety  # noqa: E402
from pipeline.adapters import registry  # noqa: E402

HANDWRITTEN = {"card:typewriter-reveal", "card:hand-drawn-ellipse",
               "card:scribble-annotation", "card:ink-underline", "card:highlighter-sweep"}


def reassign_removed(sb: dict, removed: set[str]) -> int:
    """把被移除配方的镜头按规则兜底重配，返回重配数。"""
    cap = lint._cap(len(sb["shots"]))
    used = Counter(s["recipe_ref"] for s in sb["shots"] if s["recipe_ref"] not in removed)
    n = 0
    for i, s in enumerate(sb["shots"]):
        if s["recipe_ref"] in removed and s["recipe_ref"] not in ("TitleCard", "EndingCard"):
            r, _ = fallback.pick_recipe(s["vo"], i, dict(used), cap)
            s["recipe_ref"] = r
            used[r] += 1
            n += 1
    return n


def metrics(sb: dict, briefs: int, sources: int) -> dict:
    shots = sb["shots"]
    recipes = [s["recipe_ref"] for s in shots if s["recipe_ref"] not in ("TitleCard", "EndingCard")]
    cnt = Counter(recipes)
    overlay_shots = sum(1 for s in shots if s.get("overlay"))
    errs = lint.lint_storyboard(sb)
    return {
        "镜头数": len(shots),
        "配方多样性": f"{len(cnt)}/{len(recipes)}",
        "最大占比": f"{max(cnt.values()) / max(1, len(recipes)):.0%}",
        "生图任务": briefs,
        "画风来源": sources,
        "叠层镜": overlay_shots,
        "lint错误": len(errs),
    }


def brief_plan(sb: dict, adapter_names: set[str] | None) -> tuple[int, int]:
    """按 s4b 真实口径模拟：(生图任务数, 参与轮换的适配器数)。

    S4B 会给所有 roll=B 的镜头（含 KineticTitle/EndingCard 底图）建任务；
    这里不能私下排除首尾卡，否则消融结果和实际生图链对不上。
    """
    adapters = [a for a in registry.by_capability("image_prompt")
                if adapter_names is None or a.name in adapter_names]
    if adapter_names is not None and not adapters:
        return 0, 0
    b_shots = [s for s in sb["shots"] if s["roll"] == "B"]
    return len(b_shots), len(adapters)


def main() -> None:
    job = Path(sys.argv[1]).resolve()
    sb = json.loads((job / "storyboard.json").read_text(encoding="utf-8"))

    all_img = {a.name for a in registry.by_capability("image_prompt")}
    variants: dict[str, dict] = {}

    v = copy.deepcopy(sb)
    variants["baseline"] = (v, *brief_plan(v, all_img))
    v = copy.deepcopy(sb)
    reassign_removed(v, HANDWRITTEN)
    variants["no_handwritten"] = (v, *brief_plan(v, all_img))
    v = copy.deepcopy(sb)
    for s in v["shots"]:
        s["overlay"] = []
    variants["no_overlay"] = (v, *brief_plan(v, all_img))
    variants["no_image_adapters"] = (copy.deepcopy(sb), *brief_plan(sb, set()))
    variants["only_legacy_adapter"] = (copy.deepcopy(sb), *brief_plan(sb, {"hand-drawn-styles"}))

    # 影子编译器变体：应用 compiler_plan（存在则替换配方/配置/呈现/叠层）
    from pipeline import visual_compiler as vc
    v = copy.deepcopy(sb)
    applied = det_ok = 0
    det_ok = True
    for i, s in enumerate(v["shots"]):
        plan = s.get("compiler_plan")
        if not plan:
            continue
        recomputed = vc.compile_shot(s["ir"], i, s["vo"])
        if json.dumps(recomputed, sort_keys=True) != json.dumps(plan, sort_keys=True):
            det_ok = False
        s["recipe_ref"] = plan["recipe_ref"]
        s["config"] = plan["config"]
        s["presentation"] = plan["presentation"]
        s["overlay"] = plan["overlay"]
        applied += 1
    variants["compiler_on"] = (v, *brief_plan(v, all_img))
    print(f"[ablation] 影子编译器: 应用 {applied} 镜，确定性 {'PASS' if det_ok else 'FAIL'}（判定标准：plan 逐字节一致）")
    if applied:
        compiler_note = (f"`compiler_on` 应用 {applied} 镜；确定性 "
                         f"{'PASS' if det_ok else 'FAIL'}（同一 IR 必须产出同一 plan）。")
    else:
        compiler_note = ("`compiler_on` 应用 0 镜：本 job 由旧版 S3 产出，"
                         "没有 `ir`/`compiler_plan`。PASS 只说明空集自检通过，"
                         "不能证明编译器有画面收益；需用新 S3 job 复测。")

    rows = {}
    for name, (sb_, briefs, sources) in variants.items():
        rows[name] = metrics(sb_, briefs, sources)

    cols = list(next(iter(rows.values())).keys())
    lines = ["| 变体 | " + " | ".join(cols) + " |",
             "|" + "---|" * (len(cols) + 1)]
    for name, m in rows.items():
        lines.append(f"| {name} | " + " | ".join(str(m[c]) for c in cols) + " |")
    manifest_path = job / "assets" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    broll = manifest.get("broll_videos") or {}
    real_broll = sum(1 for e in broll.values() if (job / e.get("path", "")).exists())
    real_note = (f"当前产物：manifest 登记 {len(broll)} 个 B-roll 视频，"
                 f"其中 {real_broll} 个文件存在；这是 S4B→S4E→S5 真实消费链，"
                 "与上面的 prompt 级消融口径分开读。")
    table = "\n".join(lines)

    # ---- 外部能力消融 1：节奏/字数预算闸（abl_a2e_pacing_gate + abl_firered_chars_budget）----
    script_p = job / "script.json"
    timing_p = job / "timing.json"
    pace_note = ""
    try:
        from pipeline import pace_gate
        script = json.loads(script_p.read_text(encoding="utf-8")) if script_p.exists() else None
        timing = json.loads(timing_p.read_text(encoding="utf-8")) if timing_p.exists() else None
        if script and timing:
            def pace_cols(sv: dict) -> dict:
                rep = pace_gate.check(sv, timing, sb)
                dev = rep["duration"]["dev"]
                return {"超长句": rep["sentences"]["超长句(>35)"],
                        "超预算镜": rep.get("budgets", {}).get("超预算镜", "-"),
                        "时长偏差": f"{dev:.0%}" if dev is not None else "-"}
            pace_scripts = {"baseline": script}
            v_script, n_split = pace_gate.resplit_long_sentences(script)
            if n_split:
                variants["pace_gate_on"] = (copy.deepcopy(sb), *brief_plan(sb, all_img))
                pace_scripts["pace_gate_on"] = v_script
            for name, m in rows.items():
                m.update(pace_cols(pace_scripts.get(name, script)))
            cols = list(next(iter(rows.values())).keys())
            lines = ["| 变体 | " + " | ".join(cols) + " |",
                     "|" + "---|" * (len(cols) + 1)]
            for name, m in rows.items():
                lines.append(f"| {name} | " + " | ".join(str(m[c]) for c in cols) + " |")
            table = "\n".join(lines)
            dev0 = pace_gate.duration_deviation(script, timing)
            rep0 = pace_gate.check(script, timing, sb)
            blk = rep0["sentences"]["超限字幕块(>16)"]
            pace_note = (f"`pace_gate_on`：a2e 节奏规则（句≤35 字/字幕块≤16/时长偏差≤15%）+ FireRed 字数预算"
                         f"（时长×语速±35%，语速按 timing 实测自校准）。重切长句 {n_split} 句；"
                         f"时长偏差 {dev0.get('dev', 0) or 0:.0%}（>{pace_gate.DEV_MAX:.0%} 时建议加删句而非调语速）；"
                         f"超限字幕块 {blk} 处（KaraokeLine 整句渲染 vs a2e 的 |分块口径，供字幕带优化参考）。")
        else:
            pace_note = "pace_gate：缺 script.json/timing.json，本 job 跳过节奏消融。"
    except Exception as e:  # noqa: BLE001 消融不挡主流程
        pace_note = f"pace_gate 消融失败: {e}"

    # ---- 外部能力消融 2：密度/死空白闸（abl_easel_density_gate，Easel layout-laws）----
    density_note = ""
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from s6_density_gate import run as density_run
        drep = density_run(job)
        if drep.get("available", True):
            density_note = (f"`density_gate`（建议级）：抽帧 {drep['frames']} 帧，内容填充中位 {drep['fill_median']}，"
                            f"最长死空白带中位 {drep['max_dead_median']}，fail 帧 {drep['fail_frames']}"
                            f"（阈值 fill≥0.60/死带≤0.22，layout-laws 卡片口径偏严，先观测再收紧）→ qa/density-report.json")
        else:
            density_note = "density_gate：无 qa/metric-frames 也无成片，跳过。"
    except Exception as e:  # noqa: BLE001
        density_note = f"density_gate 消融失败: {e}"

    out = job / "docs" / "ablation.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(f"# 消融实验报告（{job.name}）\n\n"
                   f"特征开关对比，指标全部确定性可复算（无需渲染）。\n\n"
                   f"{compiler_note}\n\n{table}\n\n{real_note}\n\n"
                   f"## 外部能力消融\n\n- {pace_note}\n- {density_note}\n", "utf-8")
    print(table)
    print(real_note)
    print(pace_note)
    print(density_note)
    print(f"\n[s4-ablation] → {out}")


if __name__ == "__main__":
    main()
