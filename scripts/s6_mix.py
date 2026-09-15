#!/usr/bin/env python3
"""S6 交付链：混音（VO+BGM ducking）+ 响度归一 → 最终成品。
用法: s6_mix.py <job_dir>

BGM 闪避配方来自 vox-director（sidechaincompress threshold=0.02 ratio=12）：
VO 说话时 BGM 自动压低，停顿时回升；片尾 2s 淡出。
BGM 路径取 assets/manifest.json 的 "bgm" 字段，为空则只混 VO。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def probe_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(r.stdout)["format"]["duration"])


def collect_cues(job: Path) -> list[dict]:
    """从 storyboard.shots[].sfx 收集音效 cue → 绝对时刻（shot.start + t_ms）。
    素材库：render-engine/public/sfx/<name>.mp3（源自 video-talkcraft 实测样板）。"""
    sb = json.loads((job / "storyboard.json").read_text(encoding="utf-8"))
    cues = []
    for shot in sb.get("shots", []):
        for cue in shot.get("sfx") or []:
            cues.append({
                "t_ms": shot["time"]["start_ms"] + cue["t_ms"],
                "name": cue["name"],
                "gain": cue.get("gain", 1.0),
            })
    cues.sort(key=lambda c: c["t_ms"])
    return cues


def mix(job: Path, vo: Path, silent: Path, out: Path, bgm: Path | None) -> None:
    dur = probe_duration(silent)
    sfx_dir = ROOT / "render-engine" / "public" / "sfx"
    cues = collect_cues(job)
    # 音效轨：每条 cue 一路 adelay + volume，再与 VO amix（VO 主导，SFX 总量压低）。
    # amix normalize=0 防止多路把人声稀释；音效叠加处靠 cue 间距错开（talkcraft 排布纪律）。
    sfx_inputs, sfx_filters, sfx_labels = [], [], []
    for i, cue in enumerate(cues):
        f = sfx_dir / f"{cue['name']}.mp3"
        if not f.exists():
            f = sfx_dir / f"pk-{cue['name']}.mp3"  # talkcraft 音效库 pk- 前缀回退
        if not f.exists():
            print(f"[s6-mix] ⚠ 音效缺失，跳过: {cue['name']}")
            continue
        sfx_inputs += ["-i", str(f)]
        idx = 2 + len(sfx_labels)  # 0=silent 1=vo, sfx 从 2 起（bgm 若有则接在 sfx 后，见下方 inputs 顺序）
        delay = max(0, int(cue["t_ms"]))
        sfx_filters.append(
            f"[{idx}:a]volume={min(2.5, 1.0 * cue["gain"]):.3f},adelay={delay}:all=1,apad=whole_dur={dur:.3f}[s{i}]"
        )
        sfx_labels.append(f"[s{i}]")
    # ★ 显式 -map：Remotion 分段自带一条静音音轨，concat 后 silent.mp4 含静音轨，
    #   ffmpeg 默认流选择会挑中它（48k 立体声）而丢掉真人 VO → 成片静音（实测踩坑）。
    #   视频=输入0，人声=输入1，必须显式指定。
    if bgm:
        # bgm 接在 sfx 输入之后
        bgm_idx = 2 + len(sfx_labels)
        sfx_inputs += ["-i", str(bgm)]
        fade_st = max(dur - 2.0, 0.0)
        sfx_filters.append(
            f"[{bgm_idx}:a]volume=0.55,aloop=loop=-1:size=2000000000,atrim=0:{dur:.3f},"
            f"afade=t=out:st={fade_st:.3f}:d=2[bgt];"
            "[1:a]asplit=2[voA][voB];"
            "[bgt][voA]sidechaincompress=threshold=0.02:ratio=12:attack=5:release=350[bgd];"
        )
        mix_labels = sfx_labels + ["[voB]", "[bgd]"]
        n_in = len(mix_labels)
        sfx_filters.append(
            "".join(mix_labels)
            + f"amix=inputs={n_in}:normalize=0:duration=longest,atrim=0:{dur:.3f}[a]"
        )
        filt = ";".join(sfx_filters)
        cmd = [
            "ffmpeg", "-i", str(silent), "-i", str(vo), *sfx_inputs,
            "-filter_complex", filt,
            "-map", "0:v:0", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-y", str(out),
        ]
        print(f"[s6-mix] 混 VO + {len(sfx_labels)}条音效 + BGM（sidechain 闪避）")
    elif sfx_labels:
        # 无 BGM：VO + SFX
        sfx_filters.append(
            "".join(sfx_labels)
            + "[1:a]"
            + f"amix=inputs={len(sfx_labels) + 1}:normalize=0:duration=longest,atrim=0:{dur:.3f}[a]"
        )
        filt = ";".join(sfx_filters)
        cmd = [
            "ffmpeg", "-i", str(silent), "-i", str(vo), *sfx_inputs,
            "-filter_complex", filt,
            "-map", "0:v:0", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-y", str(out),
        ]
        print(f"[s6-mix] 混 VO + {len(sfx_labels)}条音效")
    else:
        cmd = [
            "ffmpeg", "-i", str(silent), "-i", str(vo),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-y", str(out),
        ]
        print("[s6-mix] 混 VO（无 BGM/音效）")
    subprocess.run(cmd, check=True)


def loudnorm(out: Path) -> None:
    """两遍 loudnorm 归一到 -16 LUFS：第一遍探测 measured_*，第二遍线性归一"""
    tmp = out.with_suffix(".tmp.mp4")
    # 第一遍：print_format=json 从 stderr 提取测量值
    r = subprocess.run(
        [
            "ffmpeg", "-i", str(out),
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
            "-f", "null", "-",
        ],
        capture_output=True, text=True, check=True,
    )
    start = r.stderr.rfind("{")
    end = r.stderr.rfind("}")
    measured = {}
    if start != -1 and end != -1:
        try:
            measured = json.loads(r.stderr[start:end + 1])
        except json.JSONDecodeError:
            measured = {}

    if measured.get("input_i"):
        af = (
            "loudnorm=I=-16:TP=-1.5:LRA=11"
            f":measured_I={measured['input_i']}"
            f":measured_TP={measured['input_tp']}"
            f":measured_LRA={measured['input_lra']}"
            f":measured_thresh={measured['input_thresh']}"
            f":offset={measured.get('target_offset', 0)}"
            ":linear=true"
        )
    else:
        af = "loudnorm=I=-16:TP=-1.5:LRA=11"
    subprocess.run(
        ["ffmpeg", "-i", str(out), "-af", af,
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-y", str(tmp)],
        check=True,
    )
    tmp.replace(out)


def main() -> None:
    job = Path(sys.argv[1])
    vo = job / "audio" / "vo.wav"
    silent = job / "out" / "video-silent.mp4"
    out = job / "out" / "video-final.mp4"

    bgm = None
    manifest_p = job / "assets" / "manifest.json"
    if manifest_p.exists():
        bgm = json.loads(manifest_p.read_text(encoding="utf-8")).get("bgm")
        if bgm and not Path(bgm).exists():
            print(f"[s6-mix] 警告: manifest 的 bgm 不存在，忽略 → {bgm}")
            bgm = None

    mix(job, vo, silent, out, Path(bgm) if bgm else None)
    loudnorm(out)
    print(f"[s6-mix] → {out}")


if __name__ == "__main__":
    main()
