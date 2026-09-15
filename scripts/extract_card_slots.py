#!/usr/bin/env python3
"""抽取每张移植卡的内容槽位默认值 → registry.json 的 slotDefaults。

背景：卡的内容注入点形如 `__INJ__.ROWS ?? ([{cls:"a", text:"先做减法"}, ...])`，
槽位值形状因卡而异（字符串数组 / 对象数组）。泛化内容注入时必须保留原形状
（此前把纯字符串灌进 ROWS 对象槽 → 卡渲染空白，实测踩坑）。

本脚本对每张 injectable 卡的每个 arities 槽位：
  1. 从 card-<slug>.tsx 源码定位 `__INJ__.<KEY> ?? (` / `?? [` 的字面量
  2. 用 node 求值该 JS 字面量（纯数据，无依赖）
  3. 取前 4 项存入 registry[slug].slotDefaults[KEY]

幂等可重跑；求值失败的槽位跳过（注入退化为字符串直灌）。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CARDS_DIR = ROOT / "render-engine" / "src" / "cards"
REG_PATH = CARDS_DIR / "registry.json"
NODE = Path("/Users/bainazi/.local/bin/node")


PAIR = {"(": ")", "[": "]", "{": "}"}


def brace_block(src: str, start: int) -> tuple[int, int]:
    open_ch = src[start]
    close_ch = PAIR[open_ch]
    depth, i, in_str, esc = 0, start, None, False
    while i < len(src):
        c = src[i]
        if esc:
            esc = False
        elif in_str:
            if c == "\\":
                esc = True
            elif c == in_str:
                in_str = None
        elif c in "\"'`":
            in_str = c
        elif c in PAIR:
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth == 0 and c == close_ch:
                return start, i
        i += 1
    return start, len(src) - 1


def extract_literal(src: str, key: str) -> str | None:
    m = re.search(rf"__INJ__\.{key}\s*\?\?\s*", src)
    if not m:
        return None
    i = m.end()
    while i < len(src) and src[i] in " \n\t":
        i += 1
    if i >= len(src) or src[i] not in "([{":
        return None
    s, e = brace_block(src, i)
    lit = src[s:e + 1]
    # 剥掉纯括号壳：(( [..] )) → [..]（brace_block 对 `(` 记录的是配对括号）
    while lit[0] == "(" and lit[-1] == ")":
        inner = lit[1:-1].strip()
        if inner.startswith(("[", "{")) or "(" in inner:
            lit = inner if inner[0] in "([{" else lit
            if lit[0] == "(":
                break
        else:
            break
    return lit


def eval_js_literal(literal: str):
    r = subprocess.run(
        [str(NODE), "-e", f"console.log(JSON.stringify(( {literal} )))"],
        capture_output=True, text=True, timeout=20,
    )
    if r.returncode != 0:
        raise ValueError(r.stderr.strip().splitlines()[-1][:120] if r.stderr else "eval failed")
    return json.loads(r.stdout)


def extract_per_index(src: str, key: str) -> list | None:
    """逐元素注入模式：__INJ__.TEXT?.[0] ?? "默认" —— 按下标收集回退值。
    兼容 cast 写法 ((__INJ__.TEXT as string[])?.[0] ?? "默认")。"""
    hits = re.findall(rf"__INJ__\.{key}\s*(?:as string\[\])?\s*\)?\s*\??\.\s*\[\s*(\d+)\s*\]\s*\?\?\s*(\"[^\"]*\"|'[^']*'|`[^`]*`)", src)
    if not hits:
        return None
    out: dict[int, str] = {}
    for idx_s, lit in hits:
        idx = int(idx_s)
        if lit.startswith('"'):
            val = json.loads(lit)
        elif lit.startswith("'"):
            val = lit[1:-1].replace('\\"', '"')
        else:
            val = lit[1:-1]
        out[idx] = val
    if not out:
        return None
    return [out[i] for i in sorted(out)]


def main() -> None:
    reg = json.loads(REG_PATH.read_text(encoding="utf-8"))
    ok = fail = 0
    for slug, entry in reg.items():
        if entry.get("tier") != "injectable":
            continue
        f = CARDS_DIR / f"card-{slug}.tsx"
        if not f.exists():
            continue
        src = f.read_text(encoding="utf-8")
        defaults: dict[str, list] = {}
        for key, n in (entry.get("arities") or {}).items():
            if not isinstance(n, int) or n <= 0:
                continue
            lit = extract_literal(src, key)
            if lit is None:
                # 逐元素模式（TEXT 卡主流写法）
                per_idx = extract_per_index(src, key)
                if per_idx:
                    defaults[key] = per_idx[:4]
                    ok += 1
                else:
                    fail += 1
                    print(f"  [skip] {slug}.{key}: 未找到 __INJ__ 字面量")
                continue
            try:
                val = eval_js_literal(lit)
                if isinstance(val, list) and val:
                    defaults[key] = val[:4]
                    ok += 1
                else:
                    fail += 1
                    print(f"  [skip] {slug}.{key}: 字面量不是非空数组")
            except Exception as e:  # noqa: BLE001
                fail += 1
                print(f"  [skip] {slug}.{key}: {e}")
        if defaults:
            entry["slotDefaults"] = defaults
    REG_PATH.write_text(json.dumps(reg, ensure_ascii=False, indent=1), "utf-8")
    print(f"[card-slots] 槽位默认值抽取：成功 {ok} 个，失败/跳过 {fail} 个 → {REG_PATH.name}")


if __name__ == "__main__":
    main()
