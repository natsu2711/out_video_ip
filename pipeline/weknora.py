"""WeKnora 本地检索基础设施客户端（spec §12：一期集成，不可用时静默降级）。

约定：KB 名 asset-cards，每张卡 ingest 一份元数据文档（slug/intent/category3/
槽位/描述/使用建议）。走 WeKnora 真实 HTTP API（docker compose 默认 8080）：
  POST /api/v1/auth/login                                → JWT
  GET  /api/v1/knowledge-bases                           → 列 KB（存在即复用）
  POST /api/v1/knowledge-bases                           → 建 KB
  POST /api/v1/knowledge-bases/{id}/knowledge/manual     → 录入卡文档（title=slug）
  POST /api/v1/knowledge-bases/{id}/hybrid-search        → 混合检索
账号：环境变量 WEKNORA_USER/WEKNORA_PASS（默认 outvideo@local.dev / Outvideo#2026，
由 scripts/weknora_setup.py 首次注册）。不可用 → available=False，调用方回退纯本地检索。
"""
from __future__ import annotations

import json
import re
import os
import urllib.error
import urllib.request

KB_NAME = "asset-cards"
HTTP_BASE = os.environ.get("WEKNORA_URL", "http://127.0.0.1:8080")
USER = os.environ.get("WEKNORA_USER", "outvideo@local.dev")
PASS = os.environ.get("WEKNORA_PASS", "Outvideo#2026")

_token: str | None = None
_kb_id: str | None = None
_available: bool | None = None


def _req(method: str, path: str, body: dict | None = None, auth: bool = True,
         timeout: int = 30) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{HTTP_BASE}{path}", data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    if auth and _token:
        req.add_header("Authorization", f"Bearer {_token}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        return resp.status, (json.loads(raw) if raw else {})


def _login() -> bool:
    global _token, _available
    try:
        st, data = _req("POST", "/api/v1/auth/login",
                        {"email": USER, "password": PASS}, auth=False, timeout=10)
        tok = data.get("token") or (data.get("data") or {}).get("token")
        if st == 200 and tok:
            _token = tok
            _available = True
            return True
    except Exception:
        pass
    _available = False
    return False


def available() -> bool:
    """探测 WeKnora 可用性（health + 登录，结果缓存；不抛异常）。"""
    global _available
    if _available:
        return True
    try:
        with urllib.request.urlopen(f"{HTTP_BASE}/health", timeout=3) as resp:
            if resp.status != 200:
                _available = False
                return False
    except Exception:
        _available = False
        return False
    return _login()


def kb_id() -> str | None:
    """KB asset-cards 的 id，不存在则创建。"""
    global _kb_id
    if _kb_id:
        return _kb_id
    if not _token and not _login():
        return None
    try:
        _, data = _req("GET", "/api/v1/knowledge-bases")
        for kb in data.get("data") or []:
            if isinstance(kb, dict) and kb.get("name") == KB_NAME:
                _kb_id = kb["id"]
                return _kb_id
        _, created = _req("POST", "/api/v1/knowledge-bases",
                          {"name": KB_NAME, "description": "out_video-ip 资产卡元数据检索库"})
        _kb_id = (created.get("data") or {}).get("id")
        return _kb_id
    except Exception:
        return None


def card_doc(card: dict) -> str:
    """一张卡 → 一份 ingest 文档（确定性文本，检索与注入共用同一事实源）。"""
    slots = card.get("arities") or {}
    slot_lines = "；".join(f"{k}×{v}" for k, v in slots.items()) or "无（纯 CONFIG 图）"
    images = card.get("images") or []
    img_lines = "；".join(images) or "无"
    return (
        f"资产卡 {card.get('slug', '')}\n"
        f"类别 category={card.get('category', '')} / {card.get('category3', '')}；"
        f"视觉意图 visual_intent={json.dumps(card.get('visual_intent', []), ensure_ascii=False)}；"
        f"能量 energy={card.get('energy', '')}；时长 {card.get('duration_sec', '')}s；tier={card.get('tier', '')}\n"
        f"内容槽位：{slot_lines}\n图片槽：{img_lines}\n"
        f"描述：{card.get('desc', '')}\n"
        f"使用建议：当叙事 beat 需要 {card.get('category3', '')} 类表达且意图命中 "
        f"{json.dumps(card.get('visual_intent', []), ensure_ascii=False)} 时优先选用；"
        f"文字经 TEXT 槽注入、图片经图片槽注入，禁止改 tsx。"
    )


def ingest(cards: list[dict]) -> int:
    """把全部卡文档 ingest 进 KB asset-cards，返回成功条数。不可用 → 0。"""
    if not available():
        return 0
    kbid = kb_id()
    if not kbid:
        return 0
    ok = 0
    for card in cards:
        slug = card.get("slug", "")
        if not slug:
            continue
        try:
            st, _ = _req("POST", f"/api/v1/knowledge-bases/{kbid}/knowledge/manual",
                         {"title": slug, "content": card_doc(card), "status": "publish"})
            ok += st == 200
        except urllib.error.HTTPError:
            continue
        except Exception:
            continue
    return ok


def search(query: str, top_k: int = 5) -> list[str]:
    """语义检索卡 slug 列表；不可用/失败 → []（调用方回退本地检索）。"""
    if not available():
        return []
    kbid = kb_id()
    if not kbid:
        return []
    try:
        _, data = _req("POST", f"/api/v1/knowledge-bases/{kbid}/hybrid-search",
                       {"query_text": query}, timeout=20)
        out = []
        for item in data.get("data") or []:
            if not isinstance(item, dict):
                continue
            # manual 文档的标题在正文首行「资产卡 <slug>」，hybrid-search 响应只带 content
            title = str((item.get("knowledge") or {}).get("title")
                        or item.get("title") or item.get("content") or "").strip()
            m = re.search(r"资产卡\s+(\S+)", title)
            if m:
                title = m.group(1)
            title = title.splitlines()[0].strip() if title else ""
            if title:
                out.append(title)
        return out[:top_k]
    except Exception:
        return []
