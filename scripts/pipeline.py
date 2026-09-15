#!/usr/bin/env python3
"""OUTVIDEO-PIPELINE 主控 CLI。

用法:
  scripts/pipeline.py init <job_root> <slug> <title> --story <md>   # S0
  scripts/pipeline.py run <job_dir> [--stage s2]                    # 推进到最近闸门
  scripts/pipeline.py gate <stage> --approve <job_dir>              # 人工闸门放行
  scripts/pipeline.py status <job_dir>                              # 查看状态

阶段执行器表：每阶段绑定确定性脚本（agent 不即兴，脚本即流程）。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import state as st  # noqa: E402

VENV_PY = ROOT / ".venv" / "bin" / "python"
INDEXTTS_PY = Path("/Users/bainazi/Documents/outtt/other/1other_video/index-tts/.venv/bin/python")

# 阶段 → 执行命令（顺序执行，任一失败即停）
STAGE_RUNNERS = {
    "s0": None,
    "s1": [[str(VENV_PY), str(ROOT / "scripts/s1_script.py"), "{job}"]],
    "s2": [
        [str(INDEXTTS_PY), str(ROOT / "scripts/s2_tts.py"), "{job}"],
        [str(VENV_PY), str(ROOT / "scripts/s2_align.py"), "{job}"],
    ],
    "s3": [[str(VENV_PY), str(ROOT / "scripts/s3_storyboard.py"), "{job}"],
           [str(VENV_PY), str(ROOT / "scripts/card_lint.py"), "{job}"],
           [str(VENV_PY), str(ROOT / "scripts/s3_check.py"), "{job}"],
           [str(VENV_PY), str(ROOT / "scripts/s3_table.py"), "{job}"]],
    "s4": [[str(VENV_PY), str(ROOT / "scripts/s4_manifest.py"), "{job}"],
           [str(VENV_PY), str(ROOT / "scripts/s4b_image_briefs.py"), "{job}"],
           [str(VENV_PY), str(ROOT / "scripts/s4c_stock_footage.py"), "{job}"]],
    "s5": [[str(VENV_PY), str(ROOT / "scripts/preflight.py"), "{job}"],
           [str(VENV_PY), str(ROOT / "scripts/s5_render.py"), "{job}"]],
    "s6": [
        [str(VENV_PY), str(ROOT / "scripts/s6_mix.py"), "{job}"],
        [str(VENV_PY), str(ROOT / "scripts/s6_qa.py"), "{job}"],
        [str(VENV_PY), str(ROOT / "scripts/s6_sfx_check.py"), "{job}"]],
}


def cmd_init(args: argparse.Namespace) -> None:
    subprocess.run(
        [str(VENV_PY), str(ROOT / "scripts/s0_init.py"), args.job_root, args.slug, args.title]
        + (["--story", args.story] if args.story else []),
        check=True,
    )


def run_stage(job: Path, stage: str, force: bool = False, push: bool = False) -> bool:
    # 依赖闸 1：上游必须 done（未跑/失败都挡下——实测踩坑：s2 失败后 s3 照跑，FileNotFoundError）
    for up in st.STAGE_UPSTREAM.get(stage, []):
        rec = st.load(job)["stages"].get(up, {})
        status = rec.get("status")
        if status != "done":
            print(f"[pipeline] ✗ {stage} 的上游 {up} 未完成（状态: {status}）——先跑 {up}", file=sys.stderr)
            st.set_stage(job, stage, "failed", f"upstream not done: {up} ({status})")
            return False
        # 依赖闸 2：指纹校验（done 但产物/输入已变 → 拒绝在过期产物上继续；--force/--push-through 豁免）
        if force or push:
            continue
        ok, changed = st.stage_fresh(job, up)
        if not ok:
            print(f"[pipeline] ✗ {stage} 的上游 {up} 已过期（变更: {', '.join(changed)}）——先重跑 {up}（或 --force 豁免）", file=sys.stderr)
            st.set_stage(job, stage, "failed", f"stale upstream: {up} ({', '.join(changed)})")
            return False
    st.set_stage(job, stage, "running")
    runners = STAGE_RUNNERS[stage]
    if runners is None:
        print(f"[pipeline] 阶段 {stage} 未接入脚本（由 agent 产出后 `run --stage {stage}` 校验推进）")
        return False
    for cmd in runners:
        full = [c.format(job=str(job)) for c in cmd]
        print(f"[pipeline] $ {' '.join(full)}")
        r = subprocess.run(full)
        if r.returncode != 0:
            st.set_stage(job, stage, "failed", f"cmd failed: {full[1]}")
            return False
    # 产物校验
    if not st.artifacts_ok(job, stage):
        st.set_stage(job, stage, "failed", "artifacts missing")
        print(f"[pipeline] {stage} 产物缺失: {st.STAGE_ARTIFACTS[stage]}", file=sys.stderr)
        return False
    if stage in st.GATES:
        st.set_stage(job, stage, "blocked", st.GATES[stage])
        print(f"\n[pipeline] ⏸ 人工闸门 {stage}: {st.GATES[stage]}\n")
    else:
        st.set_stage(job, stage, "done")
        st.record_completion(job, stage)   # 记录产物/输入指纹（freshness 依据）
        print(f"[pipeline] ✔ {stage} done")
    return stage not in st.GATES


def cmd_run(args: argparse.Namespace) -> None:
    job = Path(args.job_dir)
    stages = [args.stage] if args.stage else st.STAGES
    force = getattr(args, "force", False)
    push = getattr(args, "push_through", False)  # 一键成片：跳过过期闸但不重跑已完成阶段
    for stage in stages:
        cur = st.load(job)["stages"].get(stage, {})
        if cur.get("status") == "done" and not force:
            continue
        if force:
            st.set_stage(job, stage, "pending", "forced")
        if cur.get("status") == "blocked":
            print(f"[pipeline] ⏸ {stage} 等待闸门放行: {st.GATES.get(stage, '')}")
            return
        ok = run_stage(job, stage, force=force, push=push)
        if not ok:
            # 到达人工闸门（blocked）= 正常停点，不算失败；真正 failed 才退非零
            if st.load(job)["stages"].get(stage, {}).get("status") == "failed":
                sys.exit(1)  # 阶段失败 → 非零退出（此前 exit 0 让 Studio 误报"完成"）
            return
    print(f"[pipeline] 全部阶段完成")


def cmd_gate(args: argparse.Namespace) -> None:
    job = Path(args.job_dir)
    if args.approve:
        st.set_stage(job, args.stage, "done", "gate approved")
        print(f"[pipeline] ✔ 闸门 {args.stage} 已放行")
    else:
        st.set_stage(job, args.stage, "failed", "gate rejected")
        print(f"[pipeline] ✘ 闸门 {args.stage} 已驳回（重跑该阶段）")


def cmd_status(args: argparse.Namespace) -> None:
    s = st.load(args.job_dir)
    print(json.dumps(s, ensure_ascii=False, indent=2))
    print("--- freshness ---")
    for stage in st.STAGES:
        rec = s["stages"].get(stage, {})
        if rec.get("status") == "done":
            ok, changed = st.stage_fresh(args.job_dir, stage)
            print(f"{stage}: {'fresh' if ok else 'STALE ← ' + ', '.join(changed)}")
        else:
            print(f"{stage}: {rec.get('status', '未开始')}")
    nxt = st.next_runnable(args.job_dir)
    print("next runnable:", nxt or "(blocked at gate / all done)")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init")
    p.add_argument("job_root")
    p.add_argument("slug")
    p.add_argument("title")
    p.add_argument("--story")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("run")
    p.add_argument("job_dir")
    p.add_argument("--stage", choices=st.STAGES)
    p.add_argument("--force", action="store_true", help="强制重跑（含 done 阶段）")
    p.add_argument("--push-through", action="store_true", help="跳过上游过期闸，但不重跑已完成阶段（一键成片用）")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("gate")
    p.add_argument("stage", choices=list(st.GATES))
    p.add_argument("--approve", action="store_true")
    p.add_argument("job_dir")
    p.set_defaults(fn=cmd_gate)

    p = sub.add_parser("status")
    p.add_argument("job_dir")
    p.set_defaults(fn=cmd_status)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
