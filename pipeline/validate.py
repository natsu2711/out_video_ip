"""schema 校验器：阶段入口先校验后执行，校验不过不推进。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft7Validator

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "schemas"

_validators: dict[str, Draft7Validator] = {}


def _get(name: str) -> Draft7Validator:
    if name not in _validators:
        schema = json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))
        _validators[name] = Draft7Validator(schema)
    return _validators[name]


def validate_file(name: str, path: str | Path) -> list[str]:
    """校验 json 文件，返回错误列表（空 = 通过）。"""
    p = Path(path)
    if not p.exists():
        return [f"file not found: {p}"]
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"invalid json: {e}"]
    return [f"{'/'.join(map(str, e.path))}: {e.message}" for e in _get(name).iter_errors(data)]


def require(name: str, path: str | Path) -> None:
    """校验失败直接退出（fail-fast）。"""
    errors = validate_file(name, path)
    if errors:
        print(f"[validate] FAIL {name}: {path}", file=sys.stderr)
        for e in errors[:10]:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)
    print(f"[validate] OK {name}: {path}")
