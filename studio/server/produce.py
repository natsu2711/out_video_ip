#!/usr/bin/env python3
"""一键成片：s1→s6 顺序全自动执行，人工闸门自动放行。
目的：文字稿进去 → 90% 成片出来（out/video-final.mp4），用户只做微调。
路由模式读 job/studio.json 的 route_mode（auto=确定性规则 / llm=大模型），与编排页开关一致。
用法: produce.py <job_dir>
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / ".venv" / "bin" / "python"
PIPELINE = ROOT / "scripts" / "pipeline.py"

STAGES = ["s1", "s2", "s3", "s4", "s5", "s6"]
GATES = {"s3", "s5"}


def sh(cmd: list[str]) -> int:
    print(f"[produce] $ {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, cwd=str(ROOT)).returncode


def main() -> None:
    job = str(Path(sys.argv[1]).resolve())
    base = [str(PY), str(PIPELINE)]

    for stage in STAGES:
        code = sh(base + ["run", job, "--stage", stage, "--push-through"])
        if code != 0:
            print(f"[produce] ✗ {stage} 失败（exit {code}）——中止。可在编排页修复后重试。", flush=True)
            sys.exit(code)
        if stage in GATES:
            code = sh(base + ["gate", stage, "--approve", job])
            if code != 0:
                sys.exit(code)
            print(f"[produce] ✓ 闸门 {stage} 已自动放行（一键模式）", flush=True)

    print("[produce] ★ 成片完成 → out/video-final.mp4（90% 初稿；微调请用编排页）", flush=True)


if __name__ == "__main__":
    main()
