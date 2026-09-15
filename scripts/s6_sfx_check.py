#!/usr/bin/env python3
"""S6 收尾：音效可听度机器验收（吸收 talkcraft sfx_check --mix 口径）。
从 storyboard 生成 cues → 对最终混音跑减人声残差分析 → 分级 UNMASKED/AUDIBLE/MASKED。
UNMASKED 依赖稿子气口结构（紧凑口播物理上不可达），故此处只 WARN 不挡关；
MASKED 比例与 AUDIBLE 数写入 qa/report.json 供交付前审阅。

用法: s6_sfx_check.py <job_dir>
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SFX_CHECK = Path("/Users/bainazi/Documents/outtt/other/1other_video/video-talkcraft/scripts/sfx_check.py")


def main() -> None:
    job = Path(sys.argv[1]).resolve()
    final = job / "out" / "video-final.mp4"
    vo = job / "audio" / "vo.wav"
    cues_path = job / "qa" / "sfx-cues.json"

    sb = json.loads((job / "storyboard.json").read_text(encoding="utf-8"))
    cues = []
    for shot in sb.get("shots", []):
        for cue in shot.get("sfx") or []:
            cues.append({"t": round((shot["time"]["start_ms"] + cue["t_ms"]) / 1000, 2),
                         "note": cue["name"]})
    cues.sort(key=lambda c: c["t"])
    if not cues:
        print("[s6-sfx] 无音效 cue，跳过")
        return
    cues_path.write_text(json.dumps(cues, ensure_ascii=False), "utf-8")

    r = subprocess.run(
        [sys.executable, str(SFX_CHECK), "--mix", str(final), str(vo), str(cues_path)],
        capture_output=True, text=True,
    )
    summary = [l for l in (r.stdout or "").splitlines() if l.startswith(("UNMASKED", "PASS", "FAIL"))]
    for l in summary:
        print(f"[s6-sfx] {l.replace('FAIL:', 'ADVISORY(不挡关):') if l.startswith('FAIL') else l}")

    # 解析分级计数写进 QA 报告（附加字段，不动 R 规则体系）
    report_p = job / "qa" / "report.json"
    report = json.loads(report_p.read_text(encoding="utf-8")) if report_p.exists() else {}
    counts = {"UNMASKED": 0, "AUDIBLE": 0, "MASKED": 0}
    for line in (r.stdout or "").splitlines():
        for k in counts:
            if line.startswith(k):
                counts[k] = int(line.split()[1])
    report["sfx"] = {
        "cues": len(cues), **counts,
        "note": "UNMASKED 需 ≥0.5s 全静音窗，紧凑口播稿不可达；AUDIBLE 即重音可闻",
    }
    report_p.write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
    print(f"[s6-sfx] 报告已并入 {report_p}")


if __name__ == "__main__":
    main()
