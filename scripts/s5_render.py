#!/usr/bin/env python3
"""S5 渲染链：逐镜头调用 Remotion 渲染 → ffmpeg concat → 无音频完整视频。
用法: s5_render.py <job_dir>
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_PY = ROOT / ".venv" / "bin" / "python"
NODE = Path("/Users/bainazi/.local/bin/node")
REMOTION_CLI = ROOT / "render-engine" / "node_modules" / ".bin" / "remotion"


def stage_public_assets(job_dir: Path, manifest: dict) -> dict:
    """把 manifest 引用的本地图片拷入 render-engine/public/，改写为 public 相对路径。
    Remotion 组件跑在浏览器里，文件系统绝对路径会 404，必须走 staticFile。"""
    public_ip = ROOT / "render-engine" / "public" / "ip"
    public_ip.mkdir(parents=True, exist_ok=True)
    out = {"ip_images": {}}
    for view, p in (manifest.get("ip_images") or {}).items():
        src = Path(p)
        if src.exists() and not src.is_relative_to(public_ip):
            dst = public_ip / src.name
            shutil.copy2(src, dst)
            out["ip_images"][view] = f"ip/{src.name}"
        else:
            out["ip_images"][view] = p
    # 逐镜场景图同样 staging（ARollScene 经 staticFile 消费）
    out["ip_scenes"] = {}
    public_ips = ROOT / "render-engine" / "public" / "ip"
    public_ips.mkdir(parents=True, exist_ok=True)
    for shot_id, p in (manifest.get("ip_scenes") or {}).items():
        src_p = Path(p)
        if not src_p.is_absolute():
            src_p = job_dir / src_p
        if src_p.exists() and not src_p.is_relative_to(public_ips):
            dst = public_ips / src_p.name
            shutil.copy2(src_p, dst)
            out["ip_scenes"][shot_id] = f"ip/{src_p.name}"
        else:
            out["ip_scenes"][shot_id] = str(src_p)
    # B-roll 真实素材同样 staging（RealFootage 经 staticFile 消费）
    out["broll_videos"] = {}
    public_broll = ROOT / "render-engine" / "public" / "broll"
    public_broll.mkdir(parents=True, exist_ok=True)
    for shot_id, entry in (manifest.get("broll_videos") or {}).items():
        src_p = Path(entry["path"])
        if not src_p.is_absolute():
            src_p = job_dir / src_p
        if src_p.exists() and not src_p.is_relative_to(public_broll):
            dst = public_broll / src_p.name
            shutil.copy2(src_p, dst)
            entry = {**entry, "path": f"broll/{src_p.name}"}
        elif src_p.is_relative_to(public_broll):
            entry = {**entry, "path": str(src_p.relative_to(public_broll.parent))}
        out["broll_videos"][shot_id] = entry
    # 真实网页截图同样 staging（ScreenshotCard 经 staticFile 消费）
    out["screenshots"] = {}
    public_shots = ROOT / "render-engine" / "public" / "screenshots"
    public_shots.mkdir(parents=True, exist_ok=True)
    for shot_id, p in (manifest.get("screenshots") or {}).items():
        src_p = Path(p)
        if not src_p.is_absolute():
            src_p = job_dir / src_p
        if src_p.exists() and not src_p.is_relative_to(public_shots):
            dst = public_shots / src_p.name
            shutil.copy2(src_p, dst)
            out["screenshots"][shot_id] = f"screenshots/{src_p.name}"
        else:
            out["screenshots"][shot_id] = str(src_p)
    out["bgm"] = manifest.get("bgm")
    return out


def render_one(job_dir: Path, shot_id: str, project: dict, timing: dict, sb: dict) -> Path:
    """单个镜头渲染：调 remotion render（Remotion 4）"""
    shot = next(s for s in sb["shots"] if s["id"] == shot_id)
    fps = project["canvas"]["fps"]
    # 按时长差直接取整（与 TS calculateMetadata 完全一致，避免边界分别 floor 的浮点误差）
    duration = max(1, int((shot["time"]["end_ms"] - shot["time"]["start_ms"]) / 1000 * fps))

    seg_dir = job_dir / "render" / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)
    out_path = seg_dir / f"{shot_id}.mp4"

    # 组装完整 JobData props（Remotion 组件跑在浏览器环境，禁止 fs 读文件，
    # 数据全部由 Python 侧读好传入）；props 写临时 JSON 文件避免超长命令行
    manifest_p = job_dir / "assets" / "manifest.json"
    assets = json.loads(manifest_p.read_text(encoding="utf-8")) if manifest_p.exists() else {"ip_images": {}}
    assets = stage_public_assets(job_dir, assets)
    props_data = {
        "job": {"id": sb.get("job_id", job_dir.name), "root": str(job_dir)},
        "project": project,
        "timing": timing,
        "storyboard": sb,
        "assets": assets,
        "shotId": shot_id,
    }
    props_file = job_dir / "render" / f"props-{shot_id}.json"
    props_file.parent.mkdir(parents=True, exist_ok=True)
    props_file.write_text(json.dumps(props_data, ensure_ascii=False), "utf-8")

    # Remotion 4 CLI: render <entry> <comp-id> <out> --props=<json文件路径> --frames=A-B
    # ★ 必须 cwd=render-engine：staticFile 静态资产挂载随 cwd 变化，
    #   从项目根跑会导致 public/ 资源 404（实测踩坑：镜头组件无图）
    cmd = [
        str(NODE),
        str(REMOTION_CLI),
        "render",
        str(ROOT / "render-engine" / "src" / "index.ts"),
        "Shot",
        str(out_path),
        "--props",
        str(props_file),
        "--frames",
        f"0-{duration - 1}",  # Remotion 帧范围是闭区间，共 duration 帧,
        "--overwrite",
        "--jpeg-quality=80",
        "--log=error",
    ]
    print(f"[s5-render] {shot_id}: {duration}f ({duration/project['canvas']['fps']:.1f}s)")
    subprocess.run(cmd, check=True, cwd=str(ROOT / "render-engine"))
    return out_path


def concat_segments(job_dir: Path, segments: list[Path]) -> Path:
    """ffmpeg concat: list.txt → out/video-silent.mp4"""
    concat_txt = job_dir / "render" / "concat.txt"
    with concat_txt.open("w") as f:
        for s in segments:
            f.write(f"file '{s.resolve()}'\n")  # 绝对路径，避免 cwd 依赖

    out = job_dir / "out" / "video-silent.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_txt),
            "-c",
            "copy",
            "-y",
            str(out),
        ],
        check=True,
    )
    return out


def main() -> None:
    job = Path(sys.argv[1]).resolve()  # cwd=render-engine 下相对路径会失效，必须绝对化
    # webpack 缓存已在 remotion.config.ts 里用 setCachingEnabled(false) 关闭
    # （缓存对源码变更的失效不可靠，曾导致渲出旧镜头组件），不再依赖清理。

    proj = json.loads((job / "project.json").read_text(encoding="utf-8"))
    timing = json.loads((job / "timing.json").read_text(encoding="utf-8"))
    sb = json.loads((job / "storyboard.json").read_text(encoding="utf-8"))

    seg_paths = []
    for shot in sb["shots"]:
        out = render_one(job, shot["id"], proj, timing, sb)
        seg_paths.append(out)

    video = concat_segments(job, seg_paths)
    print(f"[s5-render] → {video}")


if __name__ == "__main__":
    main()