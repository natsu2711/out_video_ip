#!/usr/bin/env python3
"""S2a: index-tts 适配器 —— script.json 整段合成为 vo.wav。
必须在 index-tts 的 venv 下运行（pipeline 主控会自动选择解释器）。

铁律（来自方法论）：整段合成，禁止外部按句拼接。
index-tts 内部按 token 上限自动分段属于模型机制（同一 speaker prompt + 同一次加载，
声学一致），与外部 API 分句拼接的音量/音色漂移是两回事。

用法: <index-tts-venv-python> s2_tts.py <job_dir>
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

INDEXTTS_HOME = os.environ.get(
    "INDEXTTS_HOME", "/Users/bainazi/Documents/outtt/other/1other_video/index-tts"
)
sys.path.insert(0, INDEXTTS_HOME)
os.environ.setdefault("HF_HUB_CACHE", f"{INDEXTTS_HOME}/checkpoints/hf_cache")

CKPT = f"{INDEXTTS_HOME}/checkpoints"


def main() -> None:
    job_dir = Path(sys.argv[1])
    script = json.loads((job_dir / "script.json").read_text(encoding="utf-8"))
    proj = json.loads((job_dir / "project.json").read_text(encoding="utf-8"))

    # 整段文本：保留标点（模型用标点控制韵律），段落间用换行
    full_text = "\n".join(seg["text"] for seg in script["segments"])
    out_wav = job_dir / "audio" / "vo.wav"
    print(f"[s2-tts] {len(full_text)} chars, voice={proj['voice']['ref_audio']}")

    from indextts.infer_v2_5 import IndexTTS2

    t0 = time.time()
    tts = IndexTTS2(cfg_path=f"{CKPT}/config.yaml", model_dir=CKPT)
    print(f"[s2-tts] model loaded in {time.time()-t0:.0f}s, device={tts.device}")

    t0 = time.time()
    tts.infer(
        spk_audio_prompt=proj["voice"]["ref_audio"],
        text=full_text,
        output_path=str(out_wav),
        lang="zh",
        duration_factor=proj["voice"]["speed"],
        interval_silence=200,
    )
    print(f"[s2-tts] synthesized in {time.time()-t0:.0f}s → {out_wav}")

    # 打印精确总时长（毫秒）
    import wave
    with wave.open(str(out_wav), "rb") as w:
        dur_ms = int(w.getnframes() / w.getframerate() * 1000)
        meta = {"wav": str(out_wav), "duration_ms": dur_ms, "sr": w.getframerate(), "channels": w.getnchannels()}
    (job_dir / "audio" / "vo.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), "utf-8")
    print(f"[s2-tts] duration_ms={dur_ms}")


if __name__ == "__main__":
    main()
