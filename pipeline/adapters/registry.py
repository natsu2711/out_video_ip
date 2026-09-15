"""adapter 注册表：自动发现 adapters/ 下的实现，按能力检索。
provenance 落盘 adapters/registry.json（谁来自哪个项目、什么吸收方式、验证状态）。"""
from __future__ import annotations

import importlib
import json
import pkgutil
from pathlib import Path

from .base import Adapter

_REGISTRY: dict[str, Adapter] = {}
_DISCOVERED = False

REG_FILE = Path(__file__).parent / "registry.json"


def discover() -> dict[str, Adapter]:
    """扫描 adapters 包下所有模块，收集 Adapter 子类实例（模块级 ADAPTER 变量）。"""
    global _DISCOVERED
    if _DISCOVERED:
        return _REGISTRY
    import pipeline.adapters as pkg
    for m in pkgutil.iter_modules(pkg.__path__):
        if m.name.startswith("_") or m.name in ("base", "registry"):
            continue
        try:
            mod = importlib.import_module(f"pipeline.adapters.{m.name}")
            for attr in ("ADAPTER", "ADAPTERS"):
                obj = getattr(mod, attr, None)
                for a in (obj if isinstance(obj, list) else ([obj] if obj else [])):
                    if isinstance(a, Adapter):
                        _REGISTRY[a.name] = a
        except Exception as e:  # noqa: BLE001 单个 adapter 坏不拖垮注册表
            print(f"[adapters] 跳过损坏模块 {m.name}: {e}")
    _DISCOVERED = True
    return _REGISTRY


def by_capability(capability: str) -> list[Adapter]:
    return [a for a in discover().values() if a.capability == capability and a.available()[0]]


def all_adapters() -> list[Adapter]:
    return list(discover().values())


def save_provenance(extra_status: dict[str, str] | None = None) -> None:
    data = {}
    for a in discover().values():
        p = a.provenance()
        ok, msg = a.available()
        p["available"] = ok
        p["available_msg"] = msg
        if extra_status and a.name in extra_status:
            p["verify_status"] = extra_status[a.name]
        data[a.name] = p
    REG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
