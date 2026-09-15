"""状态机：阶段只进不退，产物校验通过才推进。
参考 lanshu-create-ai-presenter-video 的 production state machine 模式。
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

STAGES = ["s0", "s1", "s2", "s3", "s4", "s5", "s6"]

# 每个阶段的产物（存在且校验通过才算 done）
STAGE_ARTIFACTS = {
    "s0": ["project.json"],
    "s1": ["script.json"],
    "s2": ["audio/vo.wav", "audio/vo.meta.json", "timing.json"],
    "s3": ["storyboard.json", "docs/storyboard-table.md"],
    "s4": ["assets/manifest.json"],
    "s5": ["render/segments/*.mp4", "out/video-silent.mp4"],
    "s6": ["out/video-final.mp4", "qa/report.json"],
}

# 人工闸门：产物生成后停在 blocked，等待人工确认
GATES = {
    "s3": "审阅编排表（docs/storyboard-table.md），确认后: pipeline gate s3 --approve <job_dir>",
    "s5": "审阅 60s 样片（render/preview-60s.mp4），确认后: pipeline gate s5 --approve <job_dir>",
}


class StateError(RuntimeError):
    pass


def load(job_dir: str | Path) -> dict:
    p = Path(job_dir) / "state.json"
    if not p.exists():
        return {"pipeline_version": "1.0", "stages": {}, "current": None}
    return json.loads(p.read_text(encoding="utf-8"))


def save(job_dir: str | Path, state: dict) -> None:
    p = Path(job_dir) / "state.json"
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def set_stage(job_dir: str | Path, stage: str, status: str, note: str = "") -> dict:
    """status: pending | running | blocked(gate) | done | failed"""
    if stage not in STAGES:
        raise StateError(f"unknown stage: {stage}")
    state = load(job_dir)
    state["stages"][stage] = {
        "status": status,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "note": note,
    }
    save(job_dir, state)
    return state


def next_runnable(job_dir: str | Path) -> str | None:
    """返回最早未 done 的阶段；闸门 blocked 需人工解除后返回其后阶段。"""
    for stage in STAGES:
        st = load(job_dir)["stages"].get(stage)
        if not st or st["status"] != "done":
            if st and st["status"] == "blocked":
                return None  # 等闸门，pipeline 会打印提示
            return stage
    return None


def artifacts_ok(job_dir: str | Path, stage: str) -> bool:
    job = Path(job_dir)
    for rel in STAGE_ARTIFACTS[stage]:
        if "*" in rel:
            glob_pat = rel.replace("*.mp4", "*.mp4")
            if not list(job.glob(glob_pat)):
                return False
        else:
            if not (job / rel).exists():
                return False
    return True


# ---------------- 依赖指纹（fresh / stale 判定，契约化第一阶段） ----------------

# 阶段直接上游：下游只能消费上游 Contract；上游 stale 时禁止在过期产物上继续
STAGE_UPSTREAM: dict[str, list[str]] = {
    "s1": ["s0"],
    "s2": ["s1", "s0"],
    "s3": ["s2"],
    "s4": ["s3"],
    "s5": ["s4", "s3", "s2", "s0"],
    "s6": ["s5", "s2"],
}
# 非产物输入文件（变化即 stale）
STAGE_INPUTS: dict[str, list[str]] = {"s1": ["story.md"]}


def file_hash(p: Path) -> str | None:
    """SHA-256 前 16 位（内容指纹）。"""
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.exists() else None


def resolve_artifacts(job: Path, stage: str) -> dict[str, str | None]:
    """展开阶段产物（含 glob）→ {相对路径: hash}。"""
    out: dict[str, str | None] = {}
    for rel in STAGE_ARTIFACTS[stage]:
        if "*" in rel:
            for f in sorted(job.glob(rel)):
                out[str(f.relative_to(job))] = file_hash(f)
        else:
            out[rel] = file_hash(job / rel)
    return out


def record_completion(job_dir: str | Path, stage: str) -> None:
    """阶段 done 时记录产物 + 输入指纹（freshness 判定依据）。"""
    job = Path(job_dir)
    state = load(job)
    rec = state["stages"].get(stage, {})
    rec["artifact_hashes"] = resolve_artifacts(job, stage)
    rec["input_hashes"] = {rel: file_hash(job / rel) for rel in STAGE_INPUTS.get(stage, [])}
    state["stages"][stage] = rec
    save(job, state)


def stage_fresh(job_dir: str | Path, stage: str) -> tuple[bool, list[str]]:
    """(fresh, 变更清单)：产物/输入 hash 与完成时不一致 → stale。未完成阶段返回 (False, [提示])。"""
    job = Path(job_dir)
    rec = load(job)["stages"].get(stage, {})
    if not rec or rec.get("status") != "done":
        return False, [f"{stage} 未完成"]
    changed = [rel for rel, h in {**rec.get("artifact_hashes", {}), **rec.get("input_hashes", {})}.items()
               if h is not None and file_hash(job / rel) != h]
    return (not changed), changed