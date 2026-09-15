#!/usr/bin/env python3
"""S4E：本地 ComfyUI 图像生产，补上 s4b prompt 到 s5 渲染之间的实图断点。

输入：assets/image_briefs.json
输出：assets/broll/<shot>.png、assets/broll_videos/<shot>.mp4、manifest.broll_videos[shot]
渲染端不变：manifest 有 broll_videos 后，S5 自动把 B-roll 升级为 RealFootage + Ken Burns。

用法:
  .venv/bin/python scripts/s4e_local_images.py <job_dir>
  .venv/bin/python scripts/s4e_local_images.py <job_dir> --limit 1 --force
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("job", type=Path)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8188)
    p.add_argument("--width", type=int, default=1024)
    p.add_argument("--height", type=int, default=576)
    p.add_argument("--steps", type=int, default=6)
    p.add_argument("--timeout", type=int, default=900, help="单张生成等待秒数")
    p.add_argument("--limit", type=int, default=0, help="只处理前 N 张；0 表示全部")
    p.add_argument("--only", action="append", default=[], help="只处理指定镜号，可重复")
    p.add_argument("--force", action="store_true", help="重新生成已存在的 PNG")
    p.add_argument("--refresh-videos", action="store_true", help="用现有 PNG 重建 MP4/manifest")
    p.add_argument("--no-video", action="store_true", help="只生 PNG，不产 MP4/不改 manifest")
    return p.parse_args()


def request_json(base: str, path: str, payload: dict | None = None, timeout: int = 60) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        base + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def strip_text_instructions(prompt: str) -> str:
    """图像模型只出视觉底图；标题、高亮和字幕始终交给 Remotion 渲染。"""
    banned = (
        "大字", "文字", "标题", "高亮「", "烧字", "手写中文", "便签式标注",
        "typography", "headline", "banner headline",
    )
    kept = [line for line in prompt.splitlines()
            if not any(term.lower() in line.lower() for term in banned)]
    return "\n".join(kept).strip()


def workflow(prompt: str, negative: str, seed: int, width: int, height: int, steps: int) -> dict:
    prompt = strip_text_instructions(prompt) + (
        "\n"
        " Absolutely no text, no letters, no numbers, no Chinese characters, "
        "no Japanese characters, no typography, no watermark, no signature, no logo."
        " Absolutely no text, no letters, no numbers, no Chinese characters, "
        "no Japanese characters, no typography, no watermark, no signature, no logo."
    )
    return {
        "1": {"class_type": "UNETLoader", "inputs": {
            "unet_name": "flux-2-klein-base-4b.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": "qwen3_4b_flux2_klein.safetensors", "type": "flux2", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": negative}},
        "6": {"class_type": "EmptyLatentImage", "inputs": {
            "width": width, "height": height, "batch_size": 1}},
        "7": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0],
            "latent_image": ["6", 0], "seed": seed, "steps": steps, "cfg": 1.0,
            "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {
            "images": ["8", 0], "filename_prefix": "out_video_ip/s4e"}},
    }


def generate(base: str, wf: dict, timeout: int) -> dict:
    res = request_json(base, "/prompt", {"prompt": wf})
    prompt_id = res["prompt_id"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        history = request_json(base, f"/history/{prompt_id}", timeout=30)
        if prompt_id in history:
            item = history[prompt_id]
            status = item.get("status", {})
            if status.get("status_str") == "error":
                raise RuntimeError(status.get("messages", "ComfyUI execution error"))
            outputs = item.get("outputs", {})
            if outputs:
                return outputs
        time.sleep(1)
    raise TimeoutError(f"ComfyUI {timeout}s 内未完成: {prompt_id}")


def download_output(base: str, outputs: dict, dst: Path) -> bool:
    for node_output in outputs.values():
        for image in node_output.get("images", []):
            if image.get("type") != "output":
                continue
            q = urllib.parse.urlencode({
                "filename": image["filename"], "subfolder": image.get("subfolder", ""),
                "type": "output",
            })
            with urllib.request.urlopen(base + "/view?" + q, timeout=120) as r:
                dst.write_bytes(r.read())
            return dst.stat().st_size > 10_000
    return False


def stable_seed(shot_id: str, style: str) -> int:
    digest = hashlib.sha256(f"{shot_id}|{style}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % (2**31 - 1)


def png_to_video(src: Path, dst: Path, duration_s: float, fps: int = 30) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-loop", "1", "-i", str(src),
        "-t", f"{max(0.5, duration_s):.3f}",
        "-vf", "format=yuv420p,scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080",
        "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-movflags", "+faststart", str(dst),
    ], check=True)


def main() -> None:
    args = parse_args()
    job = args.job.resolve()
    base = f"http://{args.host}:{args.port}"
    request_json(base, "/system_stats", timeout=10)

    brief_doc = json.loads((job / "assets" / "image_briefs.json").read_text(encoding="utf-8"))
    briefs = brief_doc.get("briefs", []) if isinstance(brief_doc, dict) else []
    if not briefs:
        raise RuntimeError("image_briefs.json 没有 briefs；先运行 scripts/s4b_image_briefs.py")
    if args.limit:
        briefs = briefs[:args.limit]
    if args.only:
        wanted = set(args.only)
        briefs = [b for b in briefs if b.get("shot_id") in wanted]

    manifest_path = job / "assets" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    report_path = job / "assets" / "local_images_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {"images": {}}

    made = videos = skipped = failed = 0
    for brief in briefs:
        shot_id = brief["shot_id"]
        png = job / brief.get("target_path", f"assets/broll/{shot_id}.png")
        png.parent.mkdir(parents=True, exist_ok=True)
        if png.exists() and not args.force:
            skipped += 1
        else:
            try:
                if not (brief.get("prompt") or "").strip():
                    raise RuntimeError("prompt 为空（黑图防线）：先在素材页改槽位或重跑 s4b")
                seed = brief.get("seed")
                if not isinstance(seed, int) or seed < 0:
                    seed = stable_seed(shot_id, brief.get("style", ""))
                    brief["seed"] = seed  # 回写：同一任务单重跑 = 同图（确定性）
                negative = brief.get("negative") or (
                    "text, letters, chinese characters, japanese characters, typography, "
                    "watermark, signature, logo, blurry, low quality")
                outputs = generate(base, workflow(
                    brief["prompt"], negative, seed,
                    args.width, args.height, args.steps,
                ), args.timeout)
                if not download_output(base, outputs, png):
                    raise RuntimeError("ComfyUI 输出下载失败或文件过小")
                made += 1
                print(f"[s4e] ✓ {shot_id}: PNG {png.name} seed={seed}")
            except Exception as exc:  # noqa: BLE001 单镜失败不阻塞其他 B-roll
                failed += 1
                report["images"][shot_id] = {"status": "error", "error": str(exc)}
                print(f"[s4e] ✗ {shot_id}: {exc}", file=sys.stderr)
                continue

        report["images"][shot_id] = {
            "status": "ok", "png": str(png.relative_to(job)),
            "adapter": brief.get("adapter", ""), "style": brief.get("style", ""),
            "width": args.width, "height": args.height, "seed": brief.get("seed"),
            "negative": (brief.get("negative") or "")[:60], "reference_image": brief.get("reference_image", ""),
        }
        refresh = args.force or args.refresh_videos
        if args.no_video or (shot_id in manifest.get("broll_videos", {}) and not refresh):
            continue
        try:
            storyboard = json.loads((job / "storyboard.json").read_text(encoding="utf-8"))
            shot = next(s for s in storyboard["shots"] if s["id"] == shot_id)
            duration = (shot["time"]["end_ms"] - shot["time"]["start_ms"]) / 1000
            fps = int(json.loads((job / "project.json").read_text(encoding="utf-8"))["canvas"]["fps"])
            video = job / "assets" / "broll_videos" / f"{shot_id}.mp4"
            png_to_video(png, video, duration, fps)
            manifest.setdefault("broll_videos", {})[shot_id] = {
                "path": video.relative_to(job).as_posix(),
                "provider": f"comfyui/{brief.get('adapter', 'local')}",
                "duration": round(duration, 2),
                "keywords": [brief.get("style", "local-image")],
            }
            report["images"][shot_id]["video"] = video.relative_to(job).as_posix()
            videos += 1
            print(f"[s4e] ✓ {shot_id}: MP4 {duration:.1f}s")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            report["images"][shot_id]["video_error"] = str(exc)
            print(f"[s4e] ✗ {shot_id}: 视频转换失败 {exc}", file=sys.stderr)

    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), "utf-8")
    if videos or (manifest.get("broll_videos") and not args.no_video):
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), "utf-8")
    print(f"[s4e] 完成：生成 {made} PNG / 转换 {videos} MP4 / 跳过 {skipped} / 失败 {failed}")


if __name__ == "__main__":
    main()
