#!/usr/bin/env python3
"""配方卡批量移植器：把 video-talkcraft 的 79 张动效配方卡吸收进本项目。

不是简单复制——每张卡做三步 codemod（吸收机制的核心）：
  1. 加内容注入点：卡内内容常量（ROWS/STEPS/...）改为 `__INJ__.X ?? 原值`，
     CardHost 在模块求值前把我们的分镜文案灌进 globalThis → 卡的原动效 + 我们的内容
  2. 原子化改名 card-<slug>.tsx（配合 webpack require.context 惰性加载）
  3. 生成 registry.json：slug / 导出名 / 时长 / 内容注入键与元素数（arity）/ 接线等级

接线等级：
  injectable = 内容常量存在注入点，可自动灌我们的文案
  raw        = 文案硬编码在 JSX 里，动效可参考但需手工接线（card_lint 会挡它进自动分镜）

用法: python scripts/import_cards.py <talkcraft_cards_dir> <render_engine_dir>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# 内容常量候选（按 79 卡统计的出现频率 + 语义）
CONTENT_CONSTANTS = ["ROWS", "STEPS", "ITEMS", "CARDS", "WORDS", "LINES", "TARGETS",
                     "MESSAGES", "NODES", "POINTS", "LIST", "TAGS", "STAGES", "ROWS_A"]
TIMING_KEY = "CONFIG"

HEADER = """// [outvideo] 本文件由 scripts/import_cards.py 从 video-talkcraft 自动移植。
// 内容注入点：globalThis.__OUTVIDEO_CARD__ = { CONFIG?, ROWS?, ... }（见 pipeline 契约 docs/contracts.md）
// 原 demo 内容为默认值；接线等级见 render-engine/src/cards/registry.json
"""


def brace_block(src: str, start: int) -> tuple[int, int]:
    """返回从 start（在 '[' 或 '{' 上）开始的平衡块 end 索引。"""
    open_ch = src[start]
    close_ch = "]" if open_ch == "[" else "}"
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
        elif c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return start, i
        i += 1
    return start, len(src) - 1


def count_items(block: str) -> int:
    """数数组/对象第一层元素个数（近似：depth-1 的 { 或行首元素）。"""
    depth = 0
    n = 0
    in_str = None
    esc = False
    for c in block:
        if esc:
            esc = False
        elif in_str:
            if c == "\\":
                esc = True
            elif c == in_str:
                in_str = None
        elif c in "\"'`":
            in_str = c
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
        elif c == "," and depth == 1:
            n += 1
    return n + 1 if n else (1 if len(block) > 2 else 0)


def codemod(src: str, slug: str) -> tuple[str, dict]:
    """三步改造，返回 (新源码, registry 条目)。"""
    info: dict = {"slug": slug, "tier": "injectable", "contentKeys": {}, "arities": {}}

    # 0. 导出名
    m = re.search(r"export default function (\w+)", src)
    if not m:
        info["tier"] = "raw"
        info["reason"] = "无 export default function"
        return src, info
    info["component"] = m.group(1)

    # 1. meta 时长
    md = re.search(r"durationInFrames:\s*(\d+)", src)
    info["durationInFrames"] = int(md.group(1)) if md else None

    # 2. 注入点声明（import 之后、第一个 const 之前）
    inj_decl = (
        "// [outvideo] 内容注入（import_cards.py 自动生成）\n"
        "const __INJ__: any = (globalThis as any).__OUTVIDEO_CARD__ ?? {};\n"
    )
    anchor = re.search(r"^(const|let|var|function|export)", src, re.M)
    src = src[:anchor.start()] + inj_decl + src[anchor.start():]

    # 3. CONFIG 注入（timing 可覆盖）
    src, n = re.subn(r"const CONFIG = \{", "const CONFIG = { ...(__INJ__.CONFIG ?? {}),", src, count=1)
    if n:
        info["contentKeys"].setdefault("CONFIG", True)

    # 4. 内容常量注入 + arity 统计
    for name in CONTENT_CONSTANTS:
        m = re.search(rf"const {name}(:\s*[\w<>\[\]{{}}| ]+)? = (\[|\{{)", src)
        if not m:
            continue
        start = m.start(2)
        _, end = brace_block(src, start)
        block = src[start:end + 1]
        if name == "CONFIG":
            continue
        arity = count_items(block)
        # const ROWS = [ → const ROWS = (__INJ__.ROWS ?? ([ ... ])
        src = (src[:start]
               + f"((__INJ__.{name} ?? (" + block + ")) as any)"
               + src[end + 1:])
        info["contentKeys"][name] = True
        info["arities"][name] = arity

    # 5. 内容注入点存在性复核：只有 CONFIG（timing）没内容常量 → raw
    if not [k for k in info["contentKeys"] if k != "CONFIG"]:
        info["tier"] = "raw"
        info["reason"] = "内容硬编码在 JSX（无内容常量，仅 timing 可注入）"
    return src, info


def jsx_text_inject(src: str) -> tuple[str, list[str]]:
    """第二层 codemod：JSX 叶子中文文本 → 注入点。
    >(中文...)< → >{(__INJ__.TEXT?.[n] ?? "原文")}<
    只碰 JSX 文本位；注释/CSS（模板字符串）/表达式 {} 均不匹配。"""
    texts: list[str] = []

    def repl(m: re.Match) -> str:
        text = m.group(1)
        if not re.search(r"[\u4e00-\u9fa5]", text):
            return m.group(0)
        # 代码特征排除：比较符/赋值/括号/语句关键字/引号/冒号——只留纯展示文案
        if re.search(r"[=;(){}\[\]\"'::]|const |return |=>|//", text):
            return m.group(0)
        idx = len(texts)
        texts.append(text.strip())
        return f">{{(__INJ__.TEXT?.[{idx}] ?? {json.dumps(text, ensure_ascii=False)})}}<"

    # 单行纯文案：禁换行/引号/花括号，防跨节点与跨属性配对（实测踩坑：多行 JSX 配对吞掉属性语法）
    src = re.sub(r">([^<>{}\n\"']*[\u4e00-\u9fa5][^<>{}\n\"']*)<", repl, src)
    return src, texts


def main() -> None:
    src_dir = Path(sys.argv[1]).resolve()
    engine = Path(sys.argv[2]).resolve()
    out_dir = engine / "src" / "cards"
    out_dir.mkdir(parents=True, exist_ok=True)

    entries = []
    for f in sorted(src_dir.glob("*.tsx")):
        slug = f.stem
        raw = f.read_text(encoding="utf-8")
        body, info = codemod(raw, slug)
        # 第二层：JSX 文案提取注入（raw 卡也变 injectable）
        body, jsx_texts = jsx_text_inject(body)
        if jsx_texts:
            info["contentKeys"]["TEXT"] = True
            info["arities"]["TEXT"] = len(jsx_texts)
            info["jsxTexts"] = jsx_texts
        if info.get("tier") == "raw" and "TEXT" in info["contentKeys"]:
            info["tier"] = "injectable"
            info.pop("reason", None)
        info["sourceFile"] = f.name
        # 中文说明：取文件头第二行注释（卡名 · 说明）
        mdesc = re.search(r"//\s*(.+?)·\s*(.+)", raw)
        info["desc"] = (mdesc.group(2).strip() if mdesc else slug)[:40]
        out = out_dir / f"card-{slug}.tsx"
        out.write_text(HEADER + body, "utf-8")
        entries.append(info)

    registry = {e["slug"]: e for e in entries}
    (out_dir / "registry.json").write_text(
        json.dumps(registry, ensure_ascii=False, indent=1), "utf-8")

    injectable = [e for e in entries if e["tier"] == "injectable"]
    raws = [e for e in entries if e["tier"] != "injectable"]
    print(f"[import-cards] 移植 {len(entries)} 张卡 → {out_dir}")
    print(f"  injectable（可自动灌内容）: {len(injectable)}")
    print(f"  raw（动效可参考，需手工接线）: {[e['slug'] for e in raws]}")


if __name__ == "__main__":
    main()
