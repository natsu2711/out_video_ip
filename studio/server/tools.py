#!/usr/bin/env python3
"""Studio 渲染辅助：单镜头重渲 / 单帧静帧。由 app.py 以子进程调用（长任务不阻塞事件循环）。
用法:
  tools.py still <job_dir> <shot_id> <frame>
  tools.py shot  <job_dir> <shot_id>
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VENV_PY = ROOT / ".venv" / "bin" / "python"
sys.path.insert(0, str(ROOT))

from scripts.s5_render import NODE, REMOTION_CLI, stage_public_assets  # noqa: E402

PREVIEW_DIR = ROOT / "studio" / "server" / "preview"


def make_props(job: Path, shot_id: str) -> Path:
    """与 s5_render.render_one 完全一致的 props 组装（staging + 写 props 文件）。"""
    proj = json.loads((job / "project.json").read_text(encoding="utf-8"))
    timing = json.loads((job / "timing.json").read_text(encoding="utf-8"))
    sb = json.loads((job / "storyboard.json").read_text(encoding="utf-8"))
    manifest_p = job / "assets" / "manifest.json"
    assets = json.loads(manifest_p.read_text(encoding="utf-8")) if manifest_p.exists() else {"ip_images": {}}
    assets = stage_public_assets(job, assets)
    props = {
        "job": {"id": sb.get("job_id", job.name), "root": str(job)},
        "project": proj,
        "timing": timing,
        "storyboard": sb,
        "assets": assets,
        "shotId": shot_id,
    }
    props_file = job / "render" / f"props-{shot_id}.json"
    props_file.parent.mkdir(parents=True, exist_ok=True)
    props_file.write_text(json.dumps(props, ensure_ascii=False), "utf-8")
    return props_file


def render_still(job: Path, shot_id: str, frame: int) -> Path:
    props = make_props(job, shot_id)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    out = PREVIEW_DIR / f"{job.name}_{shot_id}_f{frame}.png"
    cmd = [
        str(NODE), str(REMOTION_CLI), "still",
        str(ROOT / "render-engine" / "src" / "index.ts"),
        "Shot", str(out),
        "--props", str(props), "--frame", str(frame),
        "--overwrite", "--log=error",
    ]
    subprocess.run(cmd, check=True, cwd=str(ROOT / "render-engine"))
    print(f"[studio-still] {shot_id} frame={frame} -> {out}")
    return out


def render_shot(job: Path, shot_id: str) -> Path:
    from scripts.s5_render import render_one
    proj = json.loads((job / "project.json").read_text(encoding="utf-8"))
    timing = json.loads((job / "timing.json").read_text(encoding="utf-8"))
    sb = json.loads((job / "storyboard.json").read_text(encoding="utf-8"))
    return render_one(job, shot_id, proj, timing, sb)


# ---------------- 单镜效果执行器（工程化，无 LLM） ----------------

def _load_manifest(job: Path) -> tuple[Path, dict]:
    p = job / "assets" / "manifest.json"
    m = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    m.setdefault("broll_videos", {})
    return p, m


def _save_manifest(p: Path, m: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(m, ensure_ascii=False, indent=1), "utf-8")


def _shot(job: Path, shot_id: str) -> dict:
    sb = json.loads((job / "storyboard.json").read_text(encoding="utf-8"))
    return next(s for s in sb["shots"] if s["id"] == shot_id)


def stock_one(job: Path, shot_id: str, keywords: list[str] | None = None, dry_run: bool = False) -> None:
    """单镜图库素材（s4c 的单镜版）：keywords 显式给定 → 全程无 LLM。"""
    from pipeline.adapters import registry
    from pipeline.adapters import stock_footage as sf
    shot = _shot(job, shot_id)
    manifest_p, manifest = _load_manifest(job)
    if shot_id in manifest["broll_videos"]:
        print(f"[fx-stock] {shot_id}: 已有素材，跳过（先删除再换）")
        return
    adapters = registry.by_capability("stock_footage")
    adapter = adapters[0] if adapters else sf.StockFootageAdapter()
    ok, msg = adapter.available()
    if not ok:
        raise RuntimeError(f"图库不可用: {msg}（需要 PEXELS_API_KEY/PIXABAY_API_KEY）")
    terms = [k.strip() for k in (keywords or []) if k.strip()] or sf.derive_keywords(shot, None)
    res = adapter.produce(shot, keywords=terms,
                          min_duration=max(4, (shot["time"]["end_ms"] - shot["time"]["start_ms"]) // 1000 - 1))
    if not res["clips"]:
        raise RuntimeError(f"{shot_id}: 关键词 {res['keywords']} 无结果")
    clip = res["clips"][0]
    out = job / "assets" / "broll_videos" / f"{shot_id}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    if dry_run:
        print(f"[fx-stock] {shot_id}: [dry] {clip['provider']} {clip['url'][:80]} ← {terms}")
        return
    # 复用 s4c 的下载器
    sys.path.insert(0, str(ROOT / "scripts"))
    from s4c_stock_footage import download
    if not download(clip["url"], out):
        raise RuntimeError(f"{shot_id}: 下载失败")
    manifest["broll_videos"][shot_id] = {
        "path": f"assets/broll_videos/{shot_id}.mp4",
        "provider": clip["provider"], "duration": clip["duration"], "keywords": terms}
    _save_manifest(manifest_p, manifest)
    print(f"[fx-stock] ✓ {shot_id}: {clip['provider']} {clip['duration']}s ← {terms}")


def whiteboard_one(job: Path, shot_id: str) -> None:
    """单镜白板动画（s4d 的单镜版）：需先有 assets/broll/{shot}.png 源图。"""
    from pipeline.adapters import registry
    shot = _shot(job, shot_id)
    adapters = registry.by_capability("video_render")
    if not adapters:
        raise RuntimeError("whiteboard-animator 不可用（.venv/bin/pip install whiteboard-animator）")
    ad = adapters[0]
    manifest_p, manifest = _load_manifest(job)
    if shot_id in manifest["broll_videos"]:
        print(f"[fx-whiteboard] {shot_id}: 已有素材，跳过（先删除再换）")
        return
    src = job / "assets" / "broll" / f"{shot_id}.png"
    if not src.exists():
        raise RuntimeError(f"{shot_id}: 缺源图 assets/broll/{shot_id}.png（先跑 AI 生图或上传）")
    dur = (shot["time"]["end_ms"] - shot["time"]["start_ms"]) / 1000
    out = job / "assets" / "broll_videos" / f"{shot_id}.mp4"
    ad.produce({"image": src, "duration_s": dur}, out)
    manifest["broll_videos"][shot_id] = {
        "path": f"assets/broll_videos/{shot_id}.mp4",
        "provider": ad.name, "duration": round(dur, 2), "keywords": ["whiteboard"]}
    _save_manifest(manifest_p, manifest)
    print(f"[fx-whiteboard] ✓ {shot_id}: 白板动画 {dur:.1f}s")


def build_workflow_ir(title: str, steps: list[dict]) -> dict:
    """简单步骤 → 合法 archify workflow IR（确定性编译，schema v2）。
    steps: [{"label": str, "note"?: str}]，首尾节点为 external 类型。"""
    nodes = []
    for i, st in enumerate(steps):
        nodes.append({
            "id": f"n{i + 1}", "lane": "main", "col": i,
            "type": "external" if i in (0, len(steps) - 1) else "backend",
            "label": st.get("label", f"步骤{i + 1}"),
            **({"sublabel": st["note"]} if st.get("note") else {}),
        })
    return {
        "schema_version": 2,
        "diagram_type": "workflow",
        "meta": {"title": title, "quality_profile": "standard"},
        "lanes": [{"id": "main", "label": "主流程"}],
        "mainPath": [n["id"] for n in nodes],
        "nodes": nodes,
        "edges": [{"from": a["id"], "to": b["id"]} for a, b in zip(nodes, nodes[1:])],
    }


def chart_one(job: Path, shot_id: str, spec: dict) -> Path:
    """单镜图表（archify）：IR → PNG → manifest.screenshots → S5 自动 ScreenshotCard。
    spec 两种写法：{"type","ir"} 原生；或 {"kind":"workflow","title","steps":[{label,note}]}
    （走 build_workflow_ir 确定性编译）。"""
    from pipeline.adapters import registry
    if spec.get("kind") == "workflow":
        spec = {"type": "workflow", "ir": build_workflow_ir(spec.get("title", "图表"), spec.get("steps", []))}
    if "type" not in spec or "ir" not in spec:
        raise RuntimeError("chart spec 需要 {type, ir} 或 {kind:'workflow', title, steps}")
    adapters = [a for a in registry.discover().values() if a.name == "archify"]
    ad = adapters[0] if adapters else None
    if ad is None or not ad.available()[0]:
        raise RuntimeError(f"archify 不可用: {ad.available()[1] if ad else '未注册'}")
    out = job / "assets" / "screenshots" / f"{shot_id}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    ad.produce(spec, out)
    manifest_p, manifest = _load_manifest(job)
    manifest.setdefault("screenshots", {})[shot_id] = f"assets/screenshots/{shot_id}.png"
    _save_manifest(manifest_p, manifest)
    print(f"[fx-chart] ✓ {shot_id}: {spec.get('type')} → {out.name}")
    return out


def gen_image_brief(job: Path, shot_id: str, adapter_name: str, style: str | None) -> dict:
    """把单镜生图任务写入 image_briefs.json（adapter.produce 是纯模板，无 LLM），
    随后 s4e --only <shot> 消费。"""
    from pipeline.adapters import registry
    shot = _shot(job, shot_id)
    cands = [a for a in registry.by_capability("image_prompt") if a.name == adapter_name]
    if not cands:
        raise RuntimeError(f"生图 adapter 不可用: {adapter_name}")
    ad = cands[0]
    out_obj = ad.produce(shot, style)
    briefs_p = job / "assets" / "image_briefs.json"
    doc = json.loads(briefs_p.read_text(encoding="utf-8")) if briefs_p.exists() else {
        "version": "1.0", "job_id": job.name, "briefs": [], "usage": {}}
    doc.setdefault("briefs", [])
    doc["briefs"] = [b for b in doc["briefs"] if b.get("shot_id") != shot_id]
    brief = {
        "shot_id": shot_id, "adapter": ad.name, "style": out_obj.get("style", style or ""),
        "aspect": out_obj.get("aspect", "16:9"), "usage": "manual-pin",
        "intent": shot.get("intent", ""), "prompt": out_obj["prompt"],
        "reference_image": (shot.get("assets_needed") or [None])[0],
        "notes": out_obj.get("notes", ""),
        "target_path": f"assets/broll/{shot_id}.png",
    }
    doc["briefs"].append(brief)
    briefs_p.parent.mkdir(parents=True, exist_ok=True)
    briefs_p.write_text(json.dumps(doc, ensure_ascii=False, indent=1), "utf-8")
    print(f"[fx-genimage] {shot_id}: 任务已写入（adapter={ad.name}, style={brief['style'][:30]}）")
    return brief


def diagram_one(job: Path, shot_id: str, elements: list[dict], app_state: str = "light") -> Path:
    """单镜手绘图（excalidraw-diagram-skill 链）：.excalidraw JSON → PNG → manifest.screenshots。"""
    import subprocess
    RENDER = Path("/Users/bainazi/Documents/outtt/other/2other_pic/excalidraw-diagram-skill/references/render_excalidraw.py")
    if not RENDER.exists():
        raise RuntimeError(f"渲染脚本不存在: {RENDER}")
    src = job / "assets" / "screenshots" / f"{shot_id}.excalidraw"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(json.dumps({
        "type": "excalidraw", "version": 2, "source": "ip-studio",
        "appState": {"viewBackgroundColor": "#ffffff" if app_state == "light" else "#111111"},
        "elements": elements, "files": {},
    }, ensure_ascii=False), "utf-8")
    out = job / "assets" / "screenshots" / f"{shot_id}.png"
    r = subprocess.run([str(VENV_PY), str(RENDER), str(src), "--output", str(out), "--width", "1920"],
                       capture_output=True, text=True, timeout=180)
    if r.returncode != 0 or not out.exists():
        raise RuntimeError(f"excalidraw 渲染失败:\n{r.stdout[-500:]}\n{r.stderr[-500:]}")
    manifest_p, manifest = _load_manifest(job)
    manifest.setdefault("screenshots", {})[shot_id] = f"assets/screenshots/{shot_id}.png"
    _save_manifest(manifest_p, manifest)
    print(f"[fx-diagram] ✓ {shot_id}: excalidraw → {out.name} ({out.stat().st_size}B)")
    return out


def main() -> None:
    mode, job_dir = sys.argv[1], Path(sys.argv[2]).resolve()
    if mode == "still":
        render_still(job_dir, sys.argv[3], int(sys.argv[4]))
    elif mode == "shot":
        render_shot(job_dir, sys.argv[3])
    elif mode == "stock":
        kw = json.loads(sys.argv[5]) if len(sys.argv) > 5 and sys.argv[5] != "-" else None
        stock_one(job_dir, sys.argv[3], keywords=kw, dry_run=len(sys.argv) > 6 and sys.argv[6] == "dry")
    elif mode == "whiteboard":
        whiteboard_one(job_dir, sys.argv[3])
    elif mode == "chart":
        chart_one(job_dir, sys.argv[3], json.loads(sys.argv[4]))
    elif mode == "brief":
        gen_image_brief(job_dir, sys.argv[3], sys.argv[4], sys.argv[5] if len(sys.argv) > 5 and sys.argv[5] != "-" else None)
    elif mode == "diagram":
        payload = json.loads(sys.argv[4])
        diagram_one(job_dir, sys.argv[3], payload.get("elements", payload))
    else:
        raise SystemExit(f"unknown mode: {mode}")


if __name__ == "__main__":
    main()
