"""IP Studio 后端：把 out_video-ip 流水线（CLI + 产物文件）暴露成本地 HTTP API。
只做薄封装：状态读 state.json，执行走现有脚本，编辑走 schema 校验 + .bak 备份。
启动: .venv/bin/python -m uvicorn studio.server.app:app --port 8321
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pipeline import state as st  # noqa: E402
from pipeline.theme_tokens import THEME_MAP  # noqa: E402
from pipeline.validate import validate_file  # noqa: E402

VENV_PY = ROOT / ".venv" / "bin" / "python"
PIPELINE_CLI = ROOT / "scripts" / "pipeline.py"
JOBS_DIR = ROOT / "jobs"
LOGS_DIR = ROOT / "studio" / "server" / "logs"
PREVIEW_DIR = ROOT / "studio" / "server" / "preview"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="OUTVIDEO IP Studio")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ---------------- 产物登记 ----------------
# name -> (相对路径, schema 名（None 不校验）, 可编辑)
ARTIFACTS: dict[str, tuple[str, str | None, bool]] = {
    "project": ("project.json", "project", True),
    "script": ("script.json", "script", True),
    "timing": ("timing.json", "timing", False),
    "storyboard": ("storyboard.json", "storyboard", True),
    "manifest": ("assets/manifest.json", None, True),
    "briefs": ("assets/image_briefs.json", None, False),
    "stock_keywords": ("assets/stock_keywords.json", None, False),
    "relevance": ("assets/relevance-report.json", None, False),
    "local_images": ("assets/local_images_report.json", None, False),
    "qa": ("qa/report.json", None, False),
    "sfx_cues": ("qa/sfx-cues.json", None, False),
    "frame_metrics": ("qa/frame-metrics-report.json", None, False),
    "table_md": ("docs/storyboard-table.md", None, False),
    "ablation": ("docs/ablation.md", None, False),
    "story": ("story.md", None, True),
    "align_review": ("audio/align-review.csv", None, False),
}

# 辅助工具（阶段内的单步重跑）
TOOLS: dict[str, dict] = {
    "s3_check": {"script": "scripts/s3_check.py"},
    "card_lint": {"script": "scripts/card_lint.py"},
    "s3_table": {"script": "scripts/s3_table.py"},
    "preflight": {"script": "scripts/preflight.py"},
    "apply_theme": {"script": "scripts/apply_theme.py"},
    "s4_manifest": {"script": "scripts/s4_manifest.py"},
    "s4b": {"script": "scripts/s4b_image_briefs.py"},
    "s4c": {"script": "scripts/s4c_stock_footage.py", "flags": ["dry_run:--dry-run"]},
    "s4e": {"script": "scripts/s4e_local_images.py",
            "opts": {"only:--only": "only", "force:--force": None, "no_video:--no-video": None}},
    "s4_relevance": {"script": "scripts/s4_relevance_check.py"},
    "s6_qa": {"script": "scripts/s6_qa.py"},
    "s6_sfx_check": {"script": "scripts/s6_sfx_check.py"},
    "ablation": {"script": "scripts/ablation.py"},
}

SHOT_COMPONENTS = [
    "KineticTitle", "TitleCard", "QuoteCard", "ChapterCard", "CompareCard", "ARollScene",
    "ImageLedCover", "PipelineSteps", "CompareCardEnhanced", "KPI_Tower", "MatrixHero",
    "MapCard", "StepsCard", "TransformCard", "ListGrid", "EndingCard",
]
OVERLAYS = ["particles", "light_sweep", "grain", "vignette", "tint_warm", "tint_cool", "snow", "embers"]
PRESENTATIONS = ["wipe_mask", "rise_fade", "slam_in", "blur_focus", "none"]
BEATS = ["hook", "point", "step", "case", "contrast", "cta"]
VISUAL_HINTS = ["scene", "graphic", "quote", "real"]
VIEW_ANGLES = ["host", "protagonist", "supporting", "pov"]
B_TYPES = ["real", "graphic", "text"]
TRANSITIONS = ["cut", "push-through", "whip-pan", "slam", "dissolve", "wipe"]

# 外部吸收库的只读参考根（白名单，供 /api/external-file 预览参考图）
EXTERNAL_ROOTS = {
    "handraw": Path("/Users/bainazi/Documents/outtt/other/2other_pic/handraw-style"),
    "handdrawn": Path("/Users/bainazi/Documents/outtt/other/1other_video/hand-drawn-styles"),
}

# 蒸馏源（资产库页「蒸馏」用）：可扫描的外部项目 → 可吸收物模式
DISTILL_SOURCES = {
    "overlay-studio": {
        "root": "/Users/bainazi/Documents/outtt/other/1other_video/overlay-studio/motion-playground",
        "desc": "动效特效库（React 组件 + 参数 schema）",
        "patterns": [
            {"kind": "tsx_effect", "glob": "src/effects/**/*.tsx", "desc": "特效组件（registry 声明参数）"},
            {"kind": "registry", "glob": "src/effects/registry.ts", "desc": "特效注册表（组/参数 schema）"},
            {"kind": "css", "glob": "src/effects/**/*.css", "desc": "特效样式"},
        ],
    },
    "skills-visual": {
        "root": "/Users/bainazi/Documents/outtt/other/1other_video/vibe_motion_skills",
        "desc": "视觉效果 skill 集合（渲染脚本 + tsx 资产卡 + 方法论）",
        "patterns": [
            {"kind": "tsx_card", "glob": "*/assets/*.tsx", "desc": "Remotion 资产卡"},
            {"kind": "renderer", "glob": "*/scripts/*.py", "desc": "确定性渲染/审计脚本"},
            {"kind": "knowledge", "glob": "*/references/*.md", "desc": "方法论文档"},
        ],
    },
    "remotion-dev": {
        "root": "/Users/bainazi/Documents/outtt/other/1other_video/remotion-dev_skills/skills",
        "desc": "Remotion 官方技巧 skill 集",
        "patterns": [
            {"kind": "knowledge", "glob": "*/SKILL.md", "desc": "技巧文档"},
            {"kind": "tsx", "glob": "**/*.tsx", "desc": "示例组件"},
        ],
    },
    "shotcraft": {
        "root": "/Users/bainazi/Documents/outtt/other/1other_video/video-shotcraft/references/shots",
        "desc": "镜头方法论卡（152 张 md）",
        "patterns": [
            {"kind": "method_card", "glob": "**/*.md", "desc": "方法论卡（已索引 152 张）"},
        ],
    },
    "vox-director": {
        "root": "/Users/bainazi/Documents/outtt/other/1other_video/vox-director",
        "desc": "Vox 叙事纪录片方法论（拼贴海报 prompt / 分镜语法）",
        "patterns": [
            {"kind": "knowledge", "glob": "references/**/*.md", "desc": "方法论文档"},
            {"kind": "prompt_pack", "glob": "assets/**/*.md", "desc": "prompt 配方"},
            {"kind": "knowledge", "glob": "*.md", "desc": "项目文档"},
        ],
    },
    "out_video_ppt": {
        "root": "/Users/bainazi/Documents/outtt/1out_video/out_video_ppt",
        "desc": "自有 PPT 风格视频管线（风格 token 包 / 箭头·吉祥物元素 / Build 场景）",
        "patterns": [
            {"kind": "tsx_element", "glob": "src/elements/*.tsx", "desc": "可卡化的元素组件"},
            {"kind": "style_pack", "glob": "src/styles/*.ts", "desc": "风格 token 包"},
            {"kind": "knowledge", "glob": "docs/**/*.md", "desc": "管线/风格文档"},
        ],
    },
}

# ---------------- 运行器 ----------------
RUNS: dict[str, dict] = {}
_RUN_LOCK = threading.Lock()


class RunError(HTTPException):
    pass


def _job_dir(job_id: str) -> Path:
    if not re.fullmatch(r"[0-9A-Za-z._\-]+", job_id):
        raise HTTPException(400, "bad job id")
    p = (JOBS_DIR / job_id).resolve()
    if not p.is_relative_to(JOBS_DIR.resolve()) or not p.is_dir():
        raise HTTPException(404, f"job not found: {job_id}")
    return p


def _log(run: dict, line: str) -> None:
    with open(run["log_path"], "a", encoding="utf-8") as f:
        f.write(line.rstrip("\n") + "\n")


def _start_run(job_id: str, label: str, cmd: list[str], cwd: Path | None = None) -> str:
    with _RUN_LOCK:
        for r in RUNS.values():
            if r["job"] == job_id and r["status"] == "running":
                raise HTTPException(409, f"job {job_id} 已有任务在跑: {r['label']}（run {r['id']}）")
        run_id = uuid.uuid4().hex[:12]
        log_path = LOGS_DIR / f"{job_id}_{run_id}.log"
        run = {"id": run_id, "job": job_id, "label": label, "cmd": cmd,
               "status": "running", "log_path": str(log_path), "started": time.time(), "ended": None, "returncode": None}
        RUNS[run_id] = run

    def _work() -> None:
        try:
            proc = subprocess.Popen(cmd, cwd=str(cwd or ROOT), stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, bufsize=1)
            run["pid"] = proc.pid
            assert proc.stdout is not None
            for line in proc.stdout:
                _log(run, line)
            code = proc.wait()
            run["returncode"] = code
            run["status"] = "done" if code == 0 else "failed"
            _log(run, f"[studio] 进程退出 code={code} ({run['status']})")
        except Exception as e:  # noqa: BLE001
            run["status"] = "failed"
            _log(run, f"[studio] 启动失败: {e}")
        finally:
            run["ended"] = time.time()

    threading.Thread(target=_work, daemon=True).start()
    return run_id


def _stage_artifact_exists(job_dir: Path) -> dict[str, list[dict]]:
    """每个阶段登记产物的存在性（支持 * 通配），供流水线视图显示。"""
    out: dict[str, list[dict]] = {}
    for stage, rels in st.STAGE_ARTIFACTS.items():
        items = []
        for rel in rels:
            if "*" in rel:
                matches = sorted(job_dir.glob(rel))
                items.append({"rel": rel, "exists": bool(matches), "count": len(matches)})
            else:
                items.append({"rel": rel, "exists": (job_dir / rel).exists()})
        out[stage] = items
    return out


def _job_summary(job_dir: Path, with_fresh: bool = True) -> dict:
    state = st.load(job_dir)
    project = {}
    pj = job_dir / "project.json"
    if pj.exists():
        project = json.loads(pj.read_text(encoding="utf-8"))
    stages = {}
    for s in st.STAGES:
        rec = state.get("stages", {}).get(s, {})
        info = {"status": rec.get("status", "pending"), "note": rec.get("note", ""), "ts": rec.get("ts")}
        if info["status"] == "done" and with_fresh:
            ok, changed = st.stage_fresh(job_dir, s)
            info["fresh"] = ok
            if not ok:
                info["stale"] = changed
        stages[s] = info
    return {
        "id": job_dir.name,
        "title": project.get("title", job_dir.name),
        "canvas": project.get("canvas"),
        "theme": (project.get("style") or {}).get("theme"),
        "stages": stages,
        "current": state.get("current"),
        "next_runnable": st.next_runnable(job_dir),
        "gates": st.GATES,
        "meta": state.get("meta", {}),
        "stage_artifacts": _stage_artifact_exists(job_dir),
    }


# ---------------- 基础接口 ----------------
@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "root": str(ROOT)}



# ---------------- RAG 召回调试 ----------------
QUERY_INTENT_HINTS = {
    "数字": ["data", "emphasis"], "数据": ["data"], "图表": ["data"], "对比": ["before_after", "comparison"],
    "步骤": ["process", "list"], "流程": ["process"], "列表": ["list"], "清单": ["list"],
    "金句": ["quote", "emphasis"], "引用": ["quote"], "强调": ["emphasis"], "冲击": ["emphasis"],
    "开场": ["scene"], "界面": ["ui"], "UI": ["ui"], "操作": ["ui", "process"],
    "前后": ["before_after"], "变化": ["before_after", "comparison"], "结尾": ["cta", "emphasis"],
}

@app.get("/api/recall")
def recall(query: str = Query(""), beat: str = Query("point"),
           top_k: int = Query(5), job_id: str = Query("")) -> dict:
    """RAG 召回调试：给定一句描述/beat，返回排序候选卡（WeKnora 语义 + 元数据打分 + 保底王），
    前端召回页据此展示 top-N 并支持手动换卡预览。"""
    from pipeline.variety import BEAT_INTENT, BEAT_CARDS, _registry_meta, retrieve_candidates
    intents = BEAT_INTENT.get(beat or "point", BEAT_INTENT["point"])
    for kw, its in QUERY_INTENT_HINTS.items():
        if kw.lower() in (query or "").lower():
            intents = list(dict.fromkeys(intents + its))
    meta = _registry_meta()

    # 1) 本地元数据打分（与 S3 检索层同公式，返回明细）
    scored: list[dict] = []
    for slug, e in meta.items():
        if slug.startswith(("TitleCard", "EndingCard")) or slug in ("KineticTitle",):
            continue
        vi = set(e.get("visual_intent", []))
        ov = vi & set(intents)
        if not ov:
            continue
        score = 0.5 * len(ov) / max(1, len(intents)) + 0.3 + 0.2
        scored.append({"slug": slug, "source": "metadata", "score": round(score, 3),
                       "matched_intents": sorted(ov), "intents": intents})
    scored.sort(key=lambda x: -x["score"])

    # 2) WeKnora 语义召回（可用时）
    semantic: list[str] = []
    try:
        from pipeline import weknora
        if query and weknora.available():
            semantic = weknora.search(f"{query}，{beat} beat，动效资产卡", top_k)
    except Exception:
        semantic = []

    # 3) 合并去重：语义命中优先，其后元数据分序，最后保底王
    out, seen = [], set()
    for slug in semantic:
        e = meta.get(slug)
        if not e or slug in seen:
            continue
        seen.add(slug)
        out.append({"slug": slug, "source": "weknora", "score": 1.0, "matched_intents": []})
    for row in scored:
        if row["slug"] in seen:
            continue
        seen.add(row["slug"])
        out.append(row)
    for slug in (BEAT_CARDS.get(beat) or BEAT_CARDS["point"]):
        if slug in seen:
            continue
        e = meta.get(slug) or {}
        seen.add(slug)
        out.append({"slug": slug, "source": "fallback", "score": 0.0, "matched_intents": []})

    for row in out:
        e = meta.get(row["slug"]) or {}
        row.update({
            "desc": e.get("desc", ""), "category": e.get("category", ""),
            "category3": e.get("category3", ""), "tier": e.get("tier", ""),
            "durationInFrames": e.get("durationInFrames", 0),
            "arities": e.get("arities", {}), "images": e.get("images", []),
            "slotDefaults": e.get("slotDefaults", {}),
        })
    return {"query": query, "beat": beat, "intents": intents,
            "weknora_available": semantic != [] or _weknora_ok(),
            "candidates": out[:max(1, top_k)]}

def _weknora_ok() -> bool:
    try:
        from pipeline import weknora
        return weknora.available()
    except Exception:
        return False

@app.get("/api/jobs")
def list_jobs() -> list[dict]:
    out = []
    if JOBS_DIR.is_dir():
        for d in sorted(JOBS_DIR.iterdir()):
            if d.is_dir() and (d / "state.json").exists():
                try:
                    out.append(_job_summary(d, with_fresh=False))
                except Exception as e:  # noqa: BLE001
                    out.append({"id": d.name, "error": str(e)})
    return out


class JobCreate(BaseModel):
    slug: str
    title: str
    story: str | None = None


@app.post("/api/jobs")
def create_job(body: JobCreate) -> dict:
    if not re.fullmatch(r"[a-z0-9\-]{2,40}", body.slug):
        raise HTTPException(400, "slug 仅限小写字母/数字/连字符")
    story_path = None
    if body.story:
        story_path = JOBS_DIR / f"_story-{body.slug}.md"
        story_path.parent.mkdir(exist_ok=True)
        story_path.write_text(body.story, encoding="utf-8")
    cmd = [str(VENV_PY), str(PIPELINE_CLI), "init", str(JOBS_DIR), body.slug, body.title]
    if story_path:
        cmd += ["--story", str(story_path)]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    if r.returncode != 0:
        raise HTTPException(500, f"init 失败:\n{r.stdout}\n{r.stderr}")
    # s0 不落闸门，直接补 done 指纹
    created = None
    for d in sorted(JOBS_DIR.iterdir(), reverse=True):
        if d.is_dir() and body.slug in d.name and (d / "state.json").exists():
            created = d
            break
    if created is None:
        raise HTTPException(500, f"init 未产出 job 目录:\n{r.stdout}\n{r.stderr}")
    st.set_stage(created, "s0", "done")
    st.record_completion(created, "s0")
    return _job_summary(created)


@app.get("/api/job/{job_id}")
def job_summary(job_id: str) -> dict:
    return _job_summary(_job_dir(job_id))


@app.get("/api/job/{job_id}/snapshot")
def job_snapshot(job_id: str) -> dict:
    """前端启动用的全家桶：状态 + 各产物内容（缺失的项为 null）。"""
    job = _job_dir(job_id)
    out: dict = {"summary": _job_summary(job), "artifacts": {}}
    for name, (rel, _schema, _edit) in ARTIFACTS.items():
        p = job / rel
        if not p.exists():
            out["artifacts"][name] = None
        elif name in ("story", "table_md", "ablation", "align_review"):
            out["artifacts"][name] = p.read_text(encoding="utf-8", errors="replace")
        else:
            try:
                out["artifacts"][name] = json.loads(p.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                out["artifacts"][name] = {"__error__": str(e)}
    # 卡片注册表 + sfx + 主题一次带全，避免多次请求
    out["meta"] = meta()
    return out


@app.get("/api/meta")
def meta() -> dict:
    registry_p = ROOT / "render-engine" / "src" / "cards" / "registry.json"
    cards = json.loads(registry_p.read_text(encoding="utf-8")) if registry_p.exists() else {}
    sfx_dir = ROOT / "render-engine" / "public" / "sfx"
    sfx = sorted({p.stem.removeprefix("pk-") for p in sfx_dir.glob("*.mp3")}) if sfx_dir.is_dir() else []
    themes = [{"id": k, **v} for k, v in THEME_MAP.items()]
    return {
        "cards": cards,
        "shot_components": SHOT_COMPONENTS,
        "overlays": OVERLAYS,
        "presentations": PRESENTATIONS,
        "beats": BEATS,
        "visual_hints": VISUAL_HINTS,
        "view_angles": VIEW_ANGLES,
        "b_types": B_TYPES,
        "transitions": TRANSITIONS,
        "sfx": sfx,
        "themes": themes,
    }


@app.get("/api/external-file")
def external_file(root: str = Query(...), path: str = Query(...)) -> FileResponse:
    """外部吸收库的参考图（只读、白名单根目录、防穿越）。"""
    base = EXTERNAL_ROOTS.get(root)
    if not base:
        raise HTTPException(404, f"unknown root: {root}")
    p = (base / path).resolve()
    if not p.is_relative_to(base.resolve()) or not p.is_file():
        raise HTTPException(404, f"not found: {path}")
    return FileResponse(p)


@app.get("/api/project-file/{path:path}")
def project_file(path: str) -> FileResponse:
    """项目级共享资产（assets/ip 姿态池等），区别于 job 内文件。"""
    base = (ROOT / "assets").resolve()
    p = (base / path).resolve()
    if not p.is_relative_to(base) or not p.is_file():
        raise HTTPException(404, f"not found: {path}")
    return FileResponse(p)


# ---------------- 蒸馏（外部资产吸收） ----------------

@app.get("/api/distill/sources")
def distill_sources() -> list[dict]:
    """可蒸馏的外部项目清单（白名单登记）。"""
    out = []
    for name, spec in DISTILL_SOURCES.items():
        root = Path(spec["root"])
        out.append({"name": name, "desc": spec["desc"], "root": spec["root"], "exists": root.exists(),
                    "patterns": spec["patterns"]})
    return out


@app.get("/api/distill/scan")
def distill_scan(source: str = Query(...), q: str = Query("")) -> dict:
    """扫描蒸馏源：按 patterns 枚举候选文件（文件名/路径过滤 q）。"""
    spec = DISTILL_SOURCES.get(source)
    if not spec:
        raise HTTPException(404, f"unknown source: {source}")
    root = Path(spec["root"])
    if not root.exists():
        return {"available": False, "items": [], "note": f"源不存在: {spec['root']}"}
    items = []
    seen = set()
    for pat in spec["patterns"]:
        for p in root.glob(pat["glob"]):
            if not p.is_file() or p in seen:
                continue
            seen.add(p)
            rel = str(p.relative_to(root))
            if q and q.lower() not in rel.lower():
                continue
            stat = p.stat()
            items.append({"kind": pat["kind"], "kind_desc": pat["desc"], "path": rel,
                          "size": stat.st_size, "mtime": int(stat.st_mtime)})
    items.sort(key=lambda x: (x["kind"], x["path"]))
    return {"available": True, "source": source, "root": spec["root"], "count": len(items), "items": items[:400]}


class AbsorbBody(BaseModel):
    source: str
    paths: list[str]
    kind: str | None = None
    as_: str = "reference"  # reference（存参考区）| card_backlog（进移植队列登记）
    note: str | None = None


@app.post("/api/distill/absorb")
def distill_absorb(body: AbsorbBody) -> dict:
    """吸收选中文件：
    - tsx 卡/特效 → 复制进 render-engine/src/cards/_distill/（移植 codemod 的素材区）并登记 backlog
    - 方法论 md → 追加登记进 docs/cards-knowledge.json 的 backlog 段（不覆盖既有索引）
    - 其他 → assets/distill/<source>/ 存档
    全程文件操作，无 LLM。"""
    spec = DISTILL_SOURCES.get(body.source)
    if not spec:
        raise HTTPException(404, f"unknown source: {body.source}")
    root = Path(spec["root"])
    imported, skipped = [], []
    dest_base = ROOT / "assets" / "distill" / body.source
    dest_base.mkdir(parents=True, exist_ok=True)
    backlog_p = ROOT / "docs" / "distill-backlog.json"
    backlog = json.loads(backlog_p.read_text(encoding="utf-8")) if backlog_p.exists() else {"version": 1, "items": []}
    for rel in body.paths:
        src = (root / rel).resolve()
        if not src.is_relative_to(root.resolve()) or not src.is_file():
            skipped.append({"path": rel, "reason": "非法路径"})
            continue
        dest = dest_base / Path(rel).name
        n = 1
        while dest.exists():
            dest = dest.with_name(f"{dest.stem}_{n}{dest.suffix}")
            n += 1
        dest.write_bytes(src.read_bytes())
        entry = {"source": body.source, "path": rel, "kind": body.kind or "file",
                 "as": body.as_, "note": body.note or "", "local": str(dest.relative_to(ROOT)),
                 "ts": int(time.time())}
        backlog["items"].append(entry)
        imported.append(entry)
    backlog_p.write_text(json.dumps(backlog, ensure_ascii=False, indent=1), "utf-8")
    return {"ok": True, "imported": len(imported), "skipped": skipped,
            "entries": imported, "backlog": str(backlog_p.relative_to(ROOT))}


@app.get("/api/distill/backlog")
def distill_backlog() -> dict:
    p = ROOT / "docs" / "distill-backlog.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"version": 1, "items": []}


@app.get("/api/inventory")
def inventory() -> dict:
    """全项目资产盘点：每个资产类别的清单与计数（前端资产库的数据源）。"""
    # 1) 渲染动效
    registry_p = ROOT / "render-engine" / "src" / "cards" / "registry.json"
    cards = json.loads(registry_p.read_text(encoding="utf-8")) if registry_p.exists() else {}
    injectable = [c for c in cards.values() if c.get("tier") == "injectable"]

    # 2) 音效（按家族分类：core / camera / impact / text / transition / ui …）
    sfx_dir = ROOT / "render-engine" / "public" / "sfx"
    sfx: list[dict] = []
    seen: set[str] = set()
    for p in sorted(sfx_dir.glob("*.mp3")) if sfx_dir.is_dir() else []:
        stem = p.stem
        if stem.startswith("pk-"):
            rest = stem[3:]
            family = rest.split("-")[0] if rest.split("-")[0] not in seen else rest.split("-")[0]
        else:
            rest, family = stem, "core"
        if rest in seen:
            continue
        seen.add(rest)
        sfx.append({"name": rest, "file": p.name, "family": family})

    # 3) 画风库（image_prompt adapter 的风格清单）
    image_styles: list[dict] = []
    hd_md = EXTERNAL_ROOTS["handdrawn"] / "STYLES.md"
    if hd_md.exists():
        rows = re.findall(r"^## ([\d.]+)[ ]+(.+?)$", hd_md.read_text(encoding="utf-8"), re.M)
        image_styles.append({
            "adapter": "hand-drawn-styles", "kind": "模板型 prompt 配方", "count": len(rows),
            "items": [{"num": n, "name": t, "desc": ""} for n, t in rows],
        })
    hr_md = EXTERNAL_ROOTS["handraw"] / "styles_200_reorganized.md"
    if hr_md.exists():
        rows = re.findall(r"^\|\s*(\d+)\s*·\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|",
                          hr_md.read_text(encoding="utf-8"), re.M)
        image_styles.append({
            "adapter": "handraw-style-216", "kind": "描述型画风（每条含编号参考图）", "count": len(rows),
            "items": [{"num": n, "name": gen, "desc": d,
                       "ref": f"images/individual/{n.zfill(3)}.png"} for n, _o, gen, d in rows],
        })
    reg_json = json.loads((ROOT / "pipeline" / "adapters" / "registry.json").read_text(encoding="utf-8"))
    prompt_packs = [{"name": k, "desc": v.get("description", ""), "available": v.get("available")}
                    for k, v in reg_json.items()
                    if k in ("vox-collage", "zine-poster")]
    renderers = [{"name": k, "desc": v.get("description", ""), "available": v.get("available")}
                 for k, v in reg_json.items()
                 if k in ("archify", "whiteboard-animator")]

    # 4) shotcraft 方法论卡
    ck_p = ROOT / "docs" / "cards-knowledge.json"
    shotcraft = {"count": 0, "categories": {}, "cards": []}
    if ck_p.exists():
        ck = json.loads(ck_p.read_text(encoding="utf-8"))
        cats: dict[str, int] = {}
        for c in ck.get("cards", []):
            cats[c.get("category", "?")] = cats.get(c.get("category", "?"), 0) + 1
        shotcraft = {"count": ck.get("count", len(ck.get("cards", []))), "categories": cats, "cards": ck.get("cards", [])}

    # 5) IP 姿态池
    ip_dir = ROOT / "assets" / "ip"
    poses = [p.name for p in sorted(ip_dir.glob("*.jpg"))] if ip_dir.is_dir() else []
    ref_count = len(list((ip_dir / "ref").iterdir())) if (ip_dir / "ref").is_dir() else 0
    ph_dir = ROOT / "assets" / "ip-placeholder"
    placeholder = [p.name for p in sorted(ph_dir.glob("*.jpg"))] if ph_dir.is_dir() else []

    return {
        "motion": {
            "cards": {"count": len(cards), "injectable": len(injectable), "raw": len(cards) - len(injectable)},
            "shot_components": {"count": len(SHOT_COMPONENTS), "items": SHOT_COMPONENTS},
            "overlays": {"count": len(OVERLAYS), "items": OVERLAYS},
            "presentations": {"count": len(PRESENTATIONS), "items": PRESENTATIONS},
        },
        "sfx": {"count": len(sfx), "items": sfx,
                "families": sorted({s["family"] for s in sfx})},
        "themes": {"count": len(THEME_MAP), "items": list(THEME_MAP.keys())},
        "image_styles": image_styles,
        "prompt_packs": prompt_packs,
        "renderers": renderers,
        "shotcraft": shotcraft,
        "ip_assets": {"poses": poses, "pose_count": len(poses), "ref_count": ref_count, "placeholder": placeholder},
        "fonts": {"note": "无内嵌字体文件；font_stack 为声明式（渲染端用系统字体）"},
    }



# ---------------- 素材视频搜索（MoneyPrinterTurbo 吸收：Pexels/Pixabay） ----------------
@app.get("/api/stock-search")
def stock_search(job_id: str = Query(""), query: str = Query(""), shot_id: str = Query("")) -> dict:
    """用 stock-footage adapter 搜素材视频片段。有 query 用 query；否则按 shot 派生关键词。
    无 API key 时返回 keywords 任务单（人工去素材站搜）。"""
    from pipeline.adapters import registry
    from pipeline.adapters import stock_footage as sf
    from pipeline import llm
    ads = [a for a in registry.discover().values() if a.name == "stock-footage"]
    if not ads:
        raise HTTPException(500, "stock-footage adapter 未注册")
    ad = ads[0]
    ok, msg = ad.available()
    shot: dict = {}
    if job_id and shot_id:
        sbp = _job_dir(job_id) / "storyboard.json"
        if sbp.exists():
            sb = json.loads(sbp.read_text(encoding="utf-8"))
            shot = next((x for x in sb.get("shots", []) if x.get("id") == shot_id), {})
    if query:
        out = ad.produce({**shot, "vo": query, "intent": "", "visual": ""}, keywords=[query])
    else:
        if not shot:
            raise HTTPException(400, "需要 query 或 (job_id + shot_id)")
        try:
            chain = llm
        except Exception:  # noqa: BLE001
            chain = None
        out = ad.produce(shot, llm_chain=None)
    clips = []
    for c in out.get("clips", []):
        clips.append({"url": c.get("url") or c.get("link"), "width": c.get("width"),
                      "height": c.get("height"), "duration": c.get("duration"),
                      "preview": c.get("preview"), "term": " ".join(out.get("keywords", []))})
    return {"available": ok, "provider": out.get("provider", ""), "keywords": out.get("keywords", []),
            "note": "" if ok else msg, "clips": clips[:12]}

class StockApplyBody(BaseModel):
    shot_id: str
    url: str
    provider: str = "pexels"
    duration: float | None = None

@app.post("/api/job/{job_id}/stock-apply")
def stock_apply(job_id: str, body: StockApplyBody) -> dict:
    """下载选中素材片段到 job 内并登记 manifest.broll_videos（S5 该镜升级 RealFootage）。"""
    import sys as _sys
    if str(ROOT) not in _sys.path:
        _sys.path.insert(0, str(ROOT))
    from scripts.s4c_stock_footage import download as stock_download
    job = _job_dir(job_id)
    dst = job / "assets" / "broll_videos" / f"{body.shot_id}.mp4"
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        if not stock_download(body.url, dst):
            raise HTTPException(502, "素材下载失败（链接失效或超限）")
    mp = job / "assets" / "manifest.json"
    manifest = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}
    manifest.setdefault("broll_videos", {})[body.shot_id] = {
        "path": dst.relative_to(job).as_posix(), "provider": f"stock/{body.provider}",
        "duration": body.duration, "keywords": [body.provider],
    }
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), "utf-8")
    return {"ok": True, "shot_id": body.shot_id}


# ---------------- 生图任务单（按镜头，可改可重跑） + 蒸馏脚手架 ----------------
@app.get("/api/job/{job_id}/file")
def job_file(job_id: str, path: str = Query(...)) -> FileResponse:
    """job 目录内文件只读服务（素材预览等），防穿越。"""
    base = _job_dir(job_id).resolve()
    p = (base / path).resolve()
    if not p.is_relative_to(base) or not p.is_file():
        raise HTTPException(404, f"not found: {path}")
    return FileResponse(p)


@app.get("/api/job/{job_id}/image-briefs")
def image_briefs(job_id: str) -> dict:
    """S4B 任务单 + S4E 产物状态按镜合并：前端素材页的「生图任务单」数据源。"""
    job = _job_dir(job_id)
    bp = job / "assets" / "image_briefs.json"
    rp = job / "assets" / "local_images_report.json"
    briefs = json.loads(bp.read_text(encoding="utf-8")).get("briefs", []) if bp.exists() else []
    report = json.loads(rp.read_text(encoding="utf-8")).get("images", {}) if rp.exists() else {}
    sb = json.loads((job / "storyboard.json").read_text(encoding="utf-8")) if (job / "storyboard.json").exists() else {}
    vo_by_id = {x["id"]: x.get("vo", "") for x in sb.get("shots", [])}
    out = []
    for b in briefs:
        sid = b["shot_id"]
        rep = report.get(sid, {})
        png = job / b.get("target_path", f"assets/broll/{sid}.png")
        status = rep.get("status") or ("done" if png.exists() else "pending")
        out.append({
            "shot_id": sid, "adapter": b.get("adapter", ""), "style": b.get("style", ""),
            "prompt": b.get("prompt", ""), "negative": b.get("negative", ""), "seed": b.get("seed"),
            "reference_image": b.get("reference_image", ""), "target_path": b.get("target_path", ""),
            "png": f"/api/job/{job_id}/file?path={b.get('target_path', 'assets/broll/' + sid + '.png')}" if png.exists() else "",
            "video": (job / rep["video"]).exists() if rep.get("video") else False,
            "status": status, "error": rep.get("error", ""), "vo": vo_by_id.get(sid, ""),
            "semantic": b.get("semantic", {}), "slots": b.get("slots", {}),
        })
    return {"briefs": out}

@app.get("/api/image-options")
def image_options() -> dict:
    """生图结构化槽位的可选项（画风预设/动作/表情档位）——素材页下拉数据源。"""
    from pipeline.adapters import ip_character as ic
    return {
        "styles": [{"id": k, "label": v} for k, v in ic.STYLE_PRESETS.items()],
        "actions": [{"id": a, "label": zh} for a, zh in ic.INTENT_ACTION.items()],
        "expressions": [{"id": k, "label": v} for k, v in ic.EXPRESSION_OPTIONS],
    }


class BriefUpdate(BaseModel):
    prompt: str | None = None      # 兼容旧字段（不推荐用）
    negative: str | None = None
    slots: dict | None = None      # 结构化槽位：style/action/expression/scene

@app.put("/api/job/{job_id}/image-brief/{shot_id}")
def image_brief_update(job_id: str, shot_id: str, body: BriefUpdate) -> dict:
    """修改某镜生图槽位（结构化）→ 服务端重建 prompt，删旧图 → 回 pending。"""
    job = _job_dir(job_id)
    bp = job / "assets" / "image_briefs.json"
    if not bp.exists():
        raise HTTPException(404, "image_briefs.json 不存在（先跑 s4b）")
    doc = json.loads(bp.read_text(encoding="utf-8"))
    hit = next((b for b in doc.get("briefs", []) if b["shot_id"] == shot_id), None)
    if not hit:
        raise HTTPException(404, f"无 {shot_id} 的任务单")
    from pipeline.adapters import ip_character as ic
    if body.slots is not None:
        old = hit.get("slots") or {}
        sl = {**old, **body.slots}
        style_key = sl.get("style") if sl.get("style") in ic.STYLE_PRESETS else "ink-girl-standard"
        expression = ic.resolve_expression({}, sl.get("expression") or "auto")
        hit["prompt"] = ic.build_prompt(style_key, sl.get("action") or ic.FALLBACK_ACTION[0],
                                        expression, sl.get("scene") or "", sl.get("intent") or "")
        hit["style"] = style_key
        hit["slots"] = sl
    if body.prompt is not None:
        if not body.prompt.strip():
            raise HTTPException(400, "prompt 不能为空（请用槽位编辑，服务端会重建 prompt）")
        hit["prompt"] = body.prompt
    if body.negative is not None:
        hit["negative"] = body.negative
    if not (hit.get("prompt") or "").strip():
        raise HTTPException(400, "重建后的 prompt 为空，已拒绝保存")
    hit["seed"] = None  # 改词换 seed，避免旧 seed 锁死构图
    bp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), "utf-8")
    png = job / hit.get("target_path", f"assets/broll/{shot_id}.png")
    png.unlink(missing_ok=True)
    rp = job / "assets" / "local_images_report.json"
    if rp.exists():
        rep = json.loads(rp.read_text(encoding="utf-8"))
        rep.get("images", {}).pop(shot_id, None)
        rp.write_text(json.dumps(rep, ensure_ascii=False, indent=1), "utf-8")
    return {"ok": True, "shot_id": shot_id, "status": "pending"}

@app.post("/api/job/{job_id}/image-regen")
def image_regen(job_id: str, body: dict) -> dict:
    """重跑某镜生图（s4e --only <shot> --force）；shot_id 省略 = 跑全部缺图。"""
    shot_id = (body or {}).get("shot_id") or ""
    cmd = [str(ROOT / ".venv" / "bin" / "python"), "scripts/s4e_local_images.py", str(_job_dir(job_id)), "--force"]
    if shot_id:
        cmd += ["--only", shot_id]
    run_id = _start_run(job_id, f"生图 {shot_id or '全部缺图'}", cmd)
    return {"run_id": run_id}

class ScaffoldBody(BaseModel):
    slug: str
    category: str = "effects"
    template: str | None = None      # 模板模式：text|serif|mono|steps|title
    from_tsx: str | None = None      # 收编模式：外部 tsx 绝对路径
    lines: int = 2

@app.post("/api/distill/scaffold")
def distill_scaffold(body: ScaffoldBody) -> dict:
    """蒸馏脚手架：为「PPT/教程里的动效」生成一张带注入槽位的卡骨架（gen_card.py 包装）。
    模板模式 → 直接产出可用的 injectable 卡；收编模式 → 收编外部自包含 tsx 再铺槽。"""
    cmd = [str(ROOT / ".venv" / "bin" / "python"), "scripts/gen_card.py",
           "--slug", body.slug, "--category", body.category, "--lines", str(body.lines)]
    if body.from_tsx:
        cmd += ["--from-tsx", body.from_tsx]
        if body.template:
            cmd += ["--component", body.template]
    elif body.template:
        cmd += ["--template", body.template]
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise HTTPException(500, f"scaffold 失败:\n{r.stdout[-400:]}\n{r.stderr[-400:]}")
    return {"ok": True, "log": (r.stdout + r.stderr)[-800:]}

# ---------------- 产物读写 ----------------
@app.get("/api/job/{job_id}/artifact/{name}")
def get_artifact(job_id: str, name: str) -> object:
    if name not in ARTIFACTS:
        raise HTTPException(404, f"unknown artifact {name}")
    job = _job_dir(job_id)
    rel, _schema, _edit = ARTIFACTS[name]
    p = job / rel
    if not p.exists():
        raise HTTPException(404, f"{rel} 不存在")
    if name in ("story", "table_md", "ablation", "align_review"):
        return PlainTextResponse(p.read_text(encoding="utf-8", errors="replace"))
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"解析 {rel} 失败: {e}") from e


class ArtifactBody(BaseModel):
    content: object


@app.put("/api/job/{job_id}/artifact/{name}")
def put_artifact(job_id: str, name: str, body: ArtifactBody) -> dict:
    if name not in ARTIFACTS:
        raise HTTPException(404, f"unknown artifact {name}")
    rel, schema, editable = ARTIFACTS[name]
    if not editable:
        raise HTTPException(403, f"{rel} 只读（由阶段脚本产出）")
    job = _job_dir(job_id)
    p = job / rel
    text = body.content if isinstance(body.content, str) else json.dumps(body.content, ensure_ascii=False, indent=2)
    # schema 校验（md/自由格式跳过）
    if schema:
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(text + ("" if text.endswith("\n") else "\n"), encoding="utf-8")
        errors = validate_file(schema, tmp)
        if errors:
            tmp.unlink(missing_ok=True)
            raise HTTPException(422, {"message": f"schema 校验未通过（{schema}）", "errors": errors[:20]})
        tmp.replace(p)
    else:
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():
            bak = p.with_suffix(p.suffix + ".bak")
            bak.write_text(p.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
        p.write_text(text + ("" if text.endswith("\n") else "\n"), encoding="utf-8")
    return {"ok": True, "path": str(p.relative_to(job))}


# ---------------- 执行 ----------------
class RunBody(BaseModel):
    stage: str | None = None
    force: bool = False


@app.post("/api/job/{job_id}/run")
def run_stage_ep(job_id: str, body: RunBody) -> dict:
    job = _job_dir(job_id)
    if body.stage and body.stage not in st.STAGES:
        raise HTTPException(400, f"bad stage {body.stage}")
    cmd = [str(VENV_PY), str(PIPELINE_CLI), "run", str(job)]
    if body.stage:
        cmd += ["--stage", body.stage]
    if body.force:
        cmd += ["--force"]
    run_id = _start_run(job_id, f"run {body.stage or 'all'}" + (" --force" if body.force else ""), cmd)
    return {"run_id": run_id}


class GateBody(BaseModel):
    stage: str
    approve: bool


def _studio_cfg(job: Path) -> dict:
    p = job / "studio.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


@app.get("/api/job/{job_id}/route-mode")
def get_route_mode(job_id: str) -> dict:
    """S3 路由模式：auto=确定性规则（无 LLM）/ llm=大模型选卡。存 studio.json。"""
    return {"route_mode": _studio_cfg(_job_dir(job_id)).get("route_mode", "llm")}


class GenCardBody(BaseModel):
    slug: str
    template: str = "text"
    lines: int = 2
    category: str = "effects"


@app.post("/api/cards/generate")
def cards_generate_ep(body: GenCardBody) -> dict:
    """一键生成资产卡：gen_card.py 模板模式（文字槽位齐备，改文字即用）。"""
    cmd = [str(VENV_PY), str(ROOT / "scripts/gen_card.py"),
           "--slug", body.slug, "--template", body.template,
           "--lines", str(body.lines), "--category", body.category]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    if r.returncode != 0:
        raise HTTPException(500, f"生成失败:\n{r.stdout[-300:]}\n{r.stderr[-300:]}")
    return {"ok": True, "slug": body.slug, "stdout": r.stdout[-400:]}


@app.post("/api/job/{job_id}/produce")
def produce_ep(job_id: str) -> dict:
    """一键成片：s1→s6 全自动 + 闸门自动放行 → out/video-final.mp4（90% 初稿）。
    路由模式沿用编排页选的 route_mode（auto/llm）。"""
    job = _job_dir(job_id)
    cmd = [str(VENV_PY), str(ROOT / "studio/server/produce.py"), str(job)]
    return {"run_id": _start_run(job_id, "一键成片 s1→s6", cmd)}


@app.post("/api/job/{job_id}/upload-layer-media")
async def upload_layer_media(job_id: str, request: Request, filename: str = Query(...)) -> dict:
    """图层素材上传：写入 render-engine/public/uploads/<job>/，返回可被 staticFile
    直接消费的相对路径（预览与 CLI 渲染同一来源）。"""
    job = _job_dir(job_id)
    safe = re.sub(r"[^0-9A-Za-z._\-]", "_", filename) or "media.bin"
    dest_dir = ROOT / "render-engine" / "public" / "uploads" / job_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{int(time.time())}_{safe}"
    body = await request.body()
    if not body:
        raise HTTPException(400, "空文件")
    dest.write_bytes(body)
    return {"ok": True, "path": f"uploads/{job_id}/{dest.name}"}


class RouteModeBody(BaseModel):
    mode: str


@app.put("/api/job/{job_id}/route-mode")
def set_route_mode(job_id: str, body: RouteModeBody) -> dict:
    if body.mode not in ("auto", "llm"):
        raise HTTPException(400, "mode 只支持 auto|llm")
    job = _job_dir(job_id)
    cfg = _studio_cfg(job)
    cfg["route_mode"] = body.mode
    (job / "studio.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), "utf-8")
    return {"ok": True, "route_mode": body.mode,
            "note": "下次 run s3 生效（auto=本地确定性规则，同文案同画面；llm=大模型在白名单池内选）"}


@app.post("/api/job/{job_id}/gate")
def gate_ep(job_id: str, body: GateBody) -> dict:
    job = _job_dir(job_id)
    if body.stage not in st.GATES:
        raise HTTPException(400, f"闸门只有 s3/s5，收到 {body.stage}")
    st.set_stage(job, body.stage, "done" if body.approve else "failed",
                 "gate approved (studio)" if body.approve else "gate rejected (studio)")
    return _job_summary(job)


class ToolBody(BaseModel):
    tool: str
    only: str | None = None
    force: bool = False
    dry_run: bool = False
    no_video: bool = False
    extra: list[str] = []


@app.post("/api/job/{job_id}/tool")
def tool_ep(job_id: str, body: ToolBody) -> dict:
    if body.tool not in TOOLS:
        raise HTTPException(404, f"unknown tool {body.tool}")
    job = _job_dir(job_id)
    spec = TOOLS[body.tool]
    cmd = [str(VENV_PY), str(ROOT / spec["script"]), str(job)]
    if body.only:
        cmd += ["--only", body.only]
    if body.force:
        cmd += ["--force"]
    if body.dry_run:
        cmd += ["--dry-run"]
    if body.no_video:
        cmd += ["--no-video"]
    cmd += body.extra
    run_id = _start_run(job_id, f"tool {body.tool}" + (f" {body.only}" if body.only else ""), cmd)
    return {"run_id": run_id}


class RenderBody(BaseModel):
    shot_id: str
    frame: int = 0


def _write_storyboard(job: Path, sb: dict) -> None:
    """带 .bak 备份 + schema 校验的 storyboard 落盘（与 PUT artifact 同纪律）。"""
    p = job / "storyboard.json"
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(sb, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    errors = validate_file("storyboard", tmp)
    if errors:
        tmp.unlink(missing_ok=True)
        raise HTTPException(422, {"message": "storyboard 校验未通过", "errors": errors[:10]})
    bak = p.with_suffix(".json.bak")
    if p.exists():
        bak.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    tmp.replace(p)


class ApplyEffectBody(BaseModel):
    effect: str  # recipe | sfx | chart | stock | whiteboard | gen_image | capture
    shot_id: str
    recipe_ref: str | None = None
    config: dict | None = None
    overlay: list[str] | None = None
    presentation: str | None = None
    cue: dict | None = None
    chart: dict | None = None
    keywords: list[str] | None = None
    dry_run: bool = False
    adapter: str | None = None
    style: str | None = None
    url: str | None = None
    mode: str | None = None
    seconds: int | None = None


@app.post("/api/job/{job_id}/apply-effect")
def apply_effect(job_id: str, body: ApplyEffectBody) -> dict:
    """工程化换效果：改 JSON + 调对应脚本，全程确定性、不走 LLM。
    素材类效果返回 run_id（后台跑脚本），前端轮询日志后 stage-assets 刷新预览。"""
    job = _job_dir(job_id)

    def patch(mutator) -> None:
        sb = json.loads((job / "storyboard.json").read_text(encoding="utf-8"))
        shot = next((s for s in sb["shots"] if s["id"] == body.shot_id), None)
        if shot is None:
            raise HTTPException(404, f"shot {body.shot_id} 不存在")
        mutator(shot)
        _write_storyboard(job, sb)

    if body.effect == "recipe":
        def mut(s):
            if body.recipe_ref:
                s["recipe_ref"] = body.recipe_ref
            if body.config is not None:
                s["config"] = body.config
            if body.overlay is not None:
                s["overlay"] = body.overlay
            if body.presentation is not None:
                s["presentation"] = body.presentation
            if body.cue:
                s.setdefault("sfx", []).append(body.cue)
        patch(mut)
        return {"ok": True, "run_id": None, "note": "storyboard 已更新（记得保存前先对比预览）"}

    if body.effect == "sfx":
        if not body.cue:
            raise HTTPException(400, "缺少 cue")
        patch(lambda s: s.setdefault("sfx", []).append(body.cue))
        return {"ok": True, "run_id": None, "note": "已加音效 cue"}

    if body.effect == "chart":
        ch = body.chart or {}
        if not (("type" in ch and "ir" in ch) or ch.get("kind") == "workflow"):
            raise HTTPException(400, "chart 需要 {type, ir} 或 {kind:'workflow', title, steps}")
        cmd = [str(VENV_PY), str(ROOT / "studio/server/tools.py"), "chart", str(job), body.shot_id,
               json.dumps(body.chart, ensure_ascii=False)]
        return {"ok": True, "run_id": _start_run(job_id, f"chart {body.shot_id}", cmd),
                "note": "archify 渲染 PNG → S5 自动按 ScreenshotCard 消费"}

    if body.effect == "stock":
        kw = json.dumps(body.keywords, ensure_ascii=False) if body.keywords else "-"
        cmd = [str(VENV_PY), str(ROOT / "studio/server/tools.py"), "stock", str(job), body.shot_id, kw]
        if body.dry_run:
            cmd.append("dry")
        return {"ok": True, "run_id": _start_run(job_id, f"stock {body.shot_id}", cmd),
                "note": "下载后 S5 自动按 RealFootage 消费"}

    if body.effect == "whiteboard":
        cmd = [str(VENV_PY), str(ROOT / "studio/server/tools.py"), "whiteboard", str(job), body.shot_id]
        return {"ok": True, "run_id": _start_run(job_id, f"whiteboard {body.shot_id}", cmd),
                "note": "需要 assets/broll/{shot}.png 源图（可先 AI 生图或上传）"}

    if body.effect == "gen_image":
        if not body.adapter:
            raise HTTPException(400, "缺少 adapter")
        # 先同步写任务单（纯模板，毫秒级），再后台跑 ComfyUI
        import subprocess as sp
        style = body.style or "-"
        r = sp.run([str(VENV_PY), str(ROOT / "studio/server/tools.py"), "brief", str(job),
                    body.shot_id, body.adapter, style], capture_output=True, text=True, cwd=str(ROOT))
        if r.returncode != 0:
            raise HTTPException(500, f"任务单生成失败:\n{r.stdout}\n{r.stderr}")
        run_id = _start_run(job_id, f"gen_image {body.shot_id}",
                            [str(VENV_PY), str(ROOT / "scripts/s4e_local_images.py"), str(job),
                             "--only", body.shot_id, "--force"])
        return {"ok": True, "run_id": run_id, "note": "任务单已写入，ComfyUI 生图中（需 8188 端口）"}

    if body.effect == "capture":
        if not body.url:
            raise HTTPException(400, "缺少 url")
        mode = body.mode or "screenshot"
        if mode not in ("screenshot", "record"):
            raise HTTPException(400, "mode 只支持 screenshot|record")
        cmd = [str(VENV_PY), str(ROOT / "scripts/s4_capture.py"), mode, str(job), body.shot_id, body.url]
        if mode == "record" and body.seconds:
            cmd += ["--seconds", str(body.seconds)]
        return {"ok": True, "run_id": _start_run(job_id, f"capture {body.shot_id}", cmd),
                "note": "Playwright 实拍（截图→ScreenshotCard / 录屏→RealFootage）"}

    if body.effect == "diagram":
        if body.chart is None or not isinstance(body.chart.get("elements"), list):
            raise HTTPException(400, "diagram 需要 {elements: [...excalidraw 元素...]}")
        cmd = [str(VENV_PY), str(ROOT / "studio/server/tools.py"), "diagram", str(job), body.shot_id,
               json.dumps(body.chart, ensure_ascii=False)]
        return {"ok": True, "run_id": _start_run(job_id, f"diagram {body.shot_id}", cmd),
                "note": "excalidraw → PNG → S5 自动按 ScreenshotCard 消费"}

    raise HTTPException(400, f"未知效果类型: {body.effect}")


@app.post("/api/job/{job_id}/render-still")
def render_still_ep(job_id: str, body: RenderBody) -> dict:
    job = _job_dir(job_id)
    cmd = [str(VENV_PY), str(ROOT / "studio/server/tools.py"), "still", str(job), body.shot_id, str(body.frame)]
    run_id = _start_run(job_id, f"still {body.shot_id} f{body.frame}", cmd)
    return {"run_id": run_id, "out": f"{job.name}_{body.shot_id}_f{body.frame}.png"}


@app.post("/api/job/{job_id}/render-shot")
def render_shot_ep(job_id: str, body: RenderBody) -> dict:
    job = _job_dir(job_id)
    cmd = [str(VENV_PY), str(ROOT / "studio/server/tools.py"), "shot", str(job), body.shot_id]
    run_id = _start_run(job_id, f"render {body.shot_id}", cmd)
    return {"run_id": run_id}


@app.post("/api/job/{job_id}/stage-assets")
def stage_assets_ep(job_id: str) -> dict:
    """把 manifest 引用的素材拷入 render-engine/public/ 并返回改写后的 assets 映射。
    前端 Player 预览用这份映射当 JobData.assets（与 s5 渲染时完全一致）。"""
    from scripts.s5_render import stage_public_assets
    job = _job_dir(job_id)
    manifest_p = job / "assets" / "manifest.json"
    manifest = json.loads(manifest_p.read_text(encoding="utf-8")) if manifest_p.exists() else {"ip_images": {}}
    return {"assets": stage_public_assets(job, manifest)}


@app.get("/api/job/{job_id}/edl")
def edl_ep(job_id: str) -> dict:
    """导出 video-use 兼容的 EDL（剪辑决策列表）：每个 range = 一个镜头，
    overlays = 该镜图层栈按时间窗换算到输出时间轴。供外部 ffmpeg 旁路/审阅用。"""
    job = _job_dir(job_id)
    sb = json.loads((job / "storyboard.json").read_text(encoding="utf-8"))
    timing = json.loads((job / "timing.json").read_text(encoding="utf-8"))
    seg_dir = job / "render" / "segments"
    ranges = []
    offset = 0.0
    for s in sb["shots"]:
        dur_s = (s["time"]["end_ms"] - s["time"]["start_ms"]) / 1000
        seg_file = seg_dir / f"{s['id']}.mp4"
        overlays = []
        for L in s.get("layers", []):
            if L.get("enabled") is False:
                continue
            overlays.append({
                "kind": L.get("kind"), "ref": L.get("ref"),
                "start_in_output": round(offset + (L.get("in_ms") or 0) / 1000, 3),
                "duration": round(((L.get("out_ms") if L.get("out_ms") is not None else s["time"]["end_ms"] - s["time"]["start_ms"])
                                   - (L.get("in_ms") or 0)) / 1000, 3),
                "position": {"x": L.get("x", 0.5), "y": L.get("y", 0.5), "scale": L.get("scale", 1)},
            })
        ranges.append({
            "source": str(seg_file) if seg_file.exists() else f"render/segments/{s['id']}.mp4",
            "shot": s["id"], "beat": s.get("seg", {}).get("beat"),
            "start": 0.0, "end": round(dur_s, 3),
            "start_in_output": round(offset, 3),
            "vo": s.get("vo", ""),
            "overlays": overlays,
        })
        offset += dur_s
    return {
        "version": 1, "fps": (json.loads((job / "project.json").read_text(encoding="utf-8")).get("canvas") or {}).get("fps", 30),
        "total_duration_s": round(offset, 3),
        "audio": str(job / "audio" / "vo.wav"),
        "ranges": ranges,
        "notes": "video-use EDL 方言；overlays 时间窗已换算到输出时间轴。external mp4 混剪可用 tools 渲染旁路。",
    }


@app.get("/api/job/{job_id}/render-status")
def render_status_ep(job_id: str) -> dict:
    """渲染产物清单：每镜 props/segment 是否在盘 + 大小。"""
    job = _job_dir(job_id)
    seg_dir = job / "render" / "segments"
    segs = {}
    for p in sorted(seg_dir.glob("*.mp4")) if seg_dir.is_dir() else []:
        segs[p.stem] = {"path": str(p.relative_to(job)), "size": p.stat().st_size}
    props = {}
    for p in sorted((job / "render").glob("props-*.json")) if (job / "render").is_dir() else []:
        props[p.stem.removeprefix("props-")] = {"path": str(p.relative_to(job)), "size": p.stat().st_size}
    out = {}
    for name in ("video-silent.mp4", "video-final.mp4"):
        p = job / "out" / name
        if p.exists():
            out[name] = {"path": f"out/{name}", "size": p.stat().st_size}
    return {"segments": segs, "props": props, "outputs": out}


@app.get("/api/runs")
def list_runs(job_id: str | None = None) -> list[dict]:
    out = []
    for r in RUNS.values():
        if job_id and r["job"] != job_id:
            continue
        out.append({k: r[k] for k in ("id", "job", "label", "status", "started", "ended", "returncode")})
    return sorted(out, key=lambda r: r["started"], reverse=True)


@app.get("/api/run/{run_id}")
def run_detail(run_id: str, tail: int = 200) -> dict:
    r = RUNS.get(run_id)
    if not r:
        raise HTTPException(404, "no such run")
    lp = Path(r["log_path"])
    lines = lp.read_text(encoding="utf-8", errors="replace").splitlines() if lp.exists() else []
    return {**{k: r[k] for k in ("id", "job", "label", "status", "started", "ended", "returncode")},
            "log": lines[-tail:]}


@app.get("/api/preview/{filename}")
def preview_file(filename: str) -> FileResponse:
    if not re.fullmatch(r"[0-9A-Za-z._\-]+\.png", filename):
        raise HTTPException(400, "bad filename")
    p = PREVIEW_DIR / filename
    if not p.exists():
        raise HTTPException(404, "still 尚未生成")
    return FileResponse(p)


@app.get("/api/job/{job_id}/file")
def job_file(job_id: str, path: str = Query(...)) -> FileResponse:
    """按相对路径取 job 内文件（音视频/图片/任意产物），带路径穿越防护。"""
    job = _job_dir(job_id)
    p = (job / path).resolve()
    if not p.is_relative_to(job.resolve()) or not p.is_file():
        raise HTTPException(404, f"file not found: {path}")
    return FileResponse(p)


@app.post("/api/job/{job_id}/upload-asset")
async def upload_asset(job_id: str, request: Request, shot_id: str = Query(...),
                       kind: str = Query(...), filename: str = Query("asset.png")) -> dict:
    """上传并登记单个镜头素材：kind ∈ broll(图) | broll_video(视频) | screenshot(截图)。
    落盘到 job/assets/<dir>/<shot_id>.<ext> 并合并写回 manifest.json（预览经 stage-assets 生效）。"""
    job = _job_dir(job_id)
    dirs = {"broll": ("broll", ".png", "broll"), "broll_video": ("broll_videos", ".mp4", "broll_videos"),
            "screenshot": ("screenshots", ".png", "screenshots")}
    if kind not in dirs:
        raise HTTPException(400, f"kind 只支持 {list(dirs)}")
    sub, default_ext, manifest_key = dirs[kind]
    ext = Path(filename).suffix.lower() or default_ext
    body = await request.body()
    if not body:
        raise HTTPException(400, "空文件")
    dest_dir = job / "assets" / sub
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{shot_id}{ext}"
    dest.write_bytes(body)
    # 合并写回 manifest（保留其它键）
    manifest_p = job / "assets" / "manifest.json"
    manifest = json.loads(manifest_p.read_text(encoding="utf-8")) if manifest_p.exists() else {}
    if kind == "broll_video":
        manifest.setdefault("broll_videos", {})[shot_id] = {
            "path": str(dest.relative_to(job)), "provider": "upload", "duration": None, "keywords": []}
    else:
        manifest.setdefault(manifest_key, {})[shot_id] = str(dest.relative_to(job))
    manifest_p.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "path": str(dest.relative_to(job))}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8321)
