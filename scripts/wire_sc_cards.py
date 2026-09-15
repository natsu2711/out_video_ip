#!/usr/bin/env python3
"""raw sc- 卡批量自动接线：让每张卡的文字/图片都可改。

接线规则（确定性 codemod）：
  A. 文字：找组件体顶层 `const <NAME> = [ '字符串', ... ]`（纯字符串数组，最多 6 项）
     → 改写为 `const <NAME> = (__INJ__.TEXT ?? [原数组]) as string[];`
     多个数组时依次 TEXT2/TEXT3（registry arities 同步）。
  B. 图片：`import x from './_sc_assets/y.(png|jpg|webp)'`
     → 删 import，改为 `const x = staticFile(String(__INJ__.CONFIG?.image_<n> ?? '_sc_assets/y.png'));`
     并确保 staticFile 已 import。registry 记 images: ['image_1', ...]（编辑器据此渲染图片槽）。
  C. 有任一接线的卡 → tier=injectable。

幂等：已有 __INJ__.TEXT 接线的跳过文字步；已改写过的图片行（含 CONFIG?.image）跳过。
用法: python scripts/wire_sc_cards.py [--dry] [--slug sc-xxx]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "render-engine" / "src" / "cards"
REG = CARDS / "registry.json"

STR_ARRAY = re.compile(
    r"^([ \t]*)const (\w+)\s*(?::\s*string\[\])?\s*=\s*\[((?:\s*['\"`][^'\"`]*['\"`]\s*,?)+)\s*\]\s*(?:as string\[\])?\s*;",
    re.M)
IMG_IMPORT = re.compile(
    r"^import (\w+) from '\./_sc_assets/([^']+\.(?:png|jpg|jpeg|webp))';", re.M)


def wire_text(src: str, wired: dict) -> str:
    """前 3 个纯字符串数组常量 → __INJ__.TEXT/TEXT2/TEXT3。
    收集后从后往前替换（避免偏移错位——首版从前往后替换接坏多行数组的实测教训）。"""
    out, used, n = src, {}, 0
    hits = []
    for m in STR_ARRAY.finditer(src):
        if n >= 3:
            break
        name, body = m.group(2), m.group(3)
        items = re.findall(r"['\"`]([^'\"`]*)['\"`]", body)
        items = [i for i in items if i.strip()]
        if not (1 <= len(items) <= 8):
            continue
        if any(i for i in items if len(i) > 20):
            continue
        key = f'TEXT{n + 1}' if n > 0 else 'TEXT'
        if f"(__INJ__.{key}" in src:
            n += 1
            continue
        hits.append((m.start(), m.end(), name, key, body, len(items)))
        n += 1
    for start, end, name, key, body, cnt in reversed(hits):
        ind = re.match(r'[ \t]*', out[start:]).group(0)
        replacement = f"{ind}const {name} = ((__INJ__.{key} as string[])?.length ? (__INJ__.{key} as string[]) : [{body.strip()}]) as string[];"
        out = out[:start] + replacement + out[end:]
        used[key] = cnt
    wired.update(used)
    return out


STR_CONST = re.compile(
    r"^([ \t]*)const (\w+)\s*(?::\s*string)?\s*=\s*(['\"])((?:(?!\3).){2,48})\3(\.split\([^)]*\))?\s*;",
    re.M)


def _good_str(v: str) -> bool:
    if not re.search(r"[A-Za-z\u4e00-\u9fff]", v):
        return False
    if v.startswith(('#', 'http', './', '/')) or '.com' in v:
        return False
    if re.match(r"^[0-9\s.:×+%$\-px]*$", v):
        return False
    return True


def wire_str_consts(src: str, wired: dict) -> str:
    """规则 E：顶层单字符串常量（含 .split(' ') 形态）→ __INJ__.TEXTN 槽。"""
    hits = []
    n = 0
    for m in STR_CONST.finditer(src):
        if n >= 3:
            break
        ind, name, q, val, split = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5) or ''
        key = f'TEXT{n + 1}' if n > 0 else 'TEXT'
        if f"(__INJ__.{key}" in src:
            continue
        if not _good_str(val):
            continue
        hits.append((m.start(), m.end(), name, key, q, val, split))
        n += 1
    for start, end, name, key, q, val, split in reversed(hits):
        core = f"((__INJ__.{key} as string[])?.[0] ?? {q}{val}{q})"
        repl = f"{ind}const {name} = ({core}{split});" if split else f"{ind}const {name} = {core};"
        src = src[:start] + repl + src[end:]
        wired[key] = 1
    return src


JSX_LIT = re.compile(r"\{\s*(['\"])((?:(?!\1).){2,44})\1\s*\}")


def wire_jsx_literals(src: str, wired: dict) -> str:
    """规则 F：JSX 表达式子节点内联字符串 {'文字'} → TEXTN 槽（从后往前，最多 3 处）。"""
    hits = []
    n = 0
    for m in JSX_LIT.finditer(src):
        if n >= 3:
            break
        q, val = m.group(1), m.group(2)
        if '${' in val or not _good_str(val):
            continue
        key = f'TEXT{n + 1}' if n > 0 else 'TEXT'
        if f"(__INJ__.{key}" in src:
            continue
        hits.append((m.start(), m.end(), q, val, key))
        n += 1
    for start, end, q, val, key in reversed(hits):
        src = src[:start] + ('{((__INJ__.%s as string[])?.[%d] ?? %s%s%s)}'
                             % (key, 0, q, val, q)) + src[end:]
        wired[key] = 1
    return src


def wire_images(src: str, wired: dict) -> str:
    """图片 import → staticFile(CONFIG.image_N 可替换)。从后往前替换。"""
    n = 0
    hits = []
    for m in IMG_IMPORT.finditer(src):
        var, path = m.group(1), m.group(2)
        key = f'image_{n + 1}'
        hits.append((m.start(), m.end(), var, path, key))
        n += 1
    for start, end, var, path, key in reversed(hits):
        repl = f"const {var} = staticFile(String(((__INJ__.CONFIG as any)?.{key}) ?? '_sc_assets/{path}'));"
        src = src[:start] + repl + src[end:]
        wired.setdefault('images', []).append(key)
    if hits:
        m = re.search(r"import \{([^}]*)\} from 'remotion';", src)
        if m and 'staticFile' not in m.group(1):
            src = src.replace(m.group(0), f"import {{{m.group(1).rstrip()}, staticFile }} from 'remotion';", 1)
    return src


SF_IMG = re.compile(r"staticFile\((['\"])([^'\"]+\.(?:png|jpg|jpeg|webp))\1\)")


def wire_staticfile_images(src: str, wired: dict) -> str:
    """规则 H：staticFile('textures/…png') 字面量 → CONFIG.image_N 可替换。"""
    hits = []
    n = 0
    for m in SF_IMG.finditer(src):
        if n >= 3:
            break
        key = f'image_{n + 1}'
        if f"__INJ__.CONFIG as any)?.{key}" in src:
            continue
        hits.append((m.start(), m.end(), m.group(2), key))
        n += 1
    for start, end, path, key in reversed(hits):
        repl = f"staticFile(String(((__INJ__.CONFIG as any)?.{key}) ?? '{path}'))"
        src = src[:start] + repl + src[end:]
        wired.setdefault('images', []).append(key)
    return src


def wire_titleblock(src: str, wired: dict) -> str:
    """TitleBlock text="常量" → TEXT 槽（从后往前）。"""
    hits = [(m.start(), m.end(), m.group(1)) for m in
            re.finditer(r'text="([A-Za-z0-9 ,.×+%$−\-]{1,24})"(\s*size=)', src)]
    n = 0
    for start, end, lit in reversed(hits):
        key = f'TEXT{n + 1}' if n > 0 else 'TEXT'
        src = src[:start] + f'text={{((__INJ__.{key} as string[])?.[0] ?? "{lit}")}}' + src[end:]
        wired[key] = 1
        n += 1
    return src


def wire_obj_text_arrays(src: str, wired: dict) -> str:
    """对象数组内 text: '常量' → __INJ__.TEXT 按下标（从后往前，逐数组）。"""
    # 找含 text: 的顶层字符串对象数组
    pat = re.compile("const (\\w+)\\s*=\\s*\\[([^\\[\\]]*?text:[\\s\\S]*?)\\]\\s*;", re.M)
    hits = []
    for m in pat.finditer(src):
        body = m.group(2)
        ts = re.findall(r"text:\s*['\"]([^'\"]{1,24})['\"]", body)
        ts = [t for t in ts if not re.match(r'^[0-9\s.:×+%$\-]*$', t)]  # 排除纯数字/符号
        if 1 <= len(ts) <= 8:
            hits.append((m.start(), m.end(), body, ts))
    n = 0
    for start, end, body, ts in reversed(hits):
        key = f'TEXT{n + 1}' if n > 0 else 'TEXT'
        new_body = body
        idx = 0
        # 倒序替换单引号 text 字段
        for tm in reversed(list(re.finditer(r"text:\s*'([^']{1,24})'", new_body))):
            t = tm.group(1)
            if re.match(r'^[0-9\s.:×+%$\-]*$', t):
                continue
            new_body = new_body[:tm.start()] + f"text: ((__INJ__.{key} as string[])?.[{idx}] ?? '{t}')" + new_body[tm.end():]
            idx += 1
        for tm in reversed(list(re.finditer(r'text:\s*"([^"]{1,24})"', new_body))):
            t = tm.group(1)
            if re.match(r'^[0-9\s.:×+%$\-]*$', t):
                continue
            new_body = new_body[:tm.start()] + f'text: ((__INJ__.{key} as string[])?.[{idx}] ?? "{t}")' + new_body[tm.end():]
            idx += 1
        if idx:
            src = src[:start] + f"const {src[start:end].split('=')[0].strip().split()[-1]} = [" + new_body + "];" + src[end:]
            wired[key] = idx
            n += 1
    return src


def wire_jsx_text(src: str, wired: dict) -> str:
    """规则 D：JSX 字面文字节点 `>文字<` → __INJ__.TEXT 下标槽（Fixtures 线框卡的主要写死文字形态）。

    只收纯文字（无 {}、<>、换行），≤18 字符、含字母/汉字，排除纯数字/符号与 style 类内容；
    每卡最多 3 处（TEXT/TEXT2/TEXT3），收集后从后往前替换。"""
    hits = []
    for m in re.finditer(r">([^<>{}\n&|=?!;()[\]%\"'`]+)<", src):
        t = m.group(1).strip()
        if not (1 <= len(t) <= 18):
            continue
        if not re.search(r"[A-Za-z\u4e00-\u9fff]", t):
            continue
        if re.match(r'^[0-9\s.:×+%$\-#/]+$', t):
            continue
        if re.search(r'\d\s*[<>=]\s*\d|[a-z]\s*[<>=]\s*', t):
            continue
        if any(k in t.lower() for k in ('px', 'http', '.com', 'import', 'const', 'from ')):
            continue
        # `>` 前一个字符不能是空格/=/（ —— 排除 `a > 0 && b <` 类比较表达式与箭头函数；
        # JSX 文字节点的 `>` 前面紧贴标签名尾字母
        pre = src[m.start() - 1] if m.start() > 0 else ''
        if pre in (' ', '\t', '=', '(', '\n'):
            continue
        hits.append((m.start(), m.end(), m.group(1), t))
        if len(hits) >= 3:
            break
    n = 0
    for start, end, raw, t in reversed(hits):
        key = f'TEXT{n + 1}' if n > 0 else 'TEXT'
        src = src[:start] + ('>{((__INJ__.%s as string[])?.[%d] ?? "%s")}<'
                             % (key, n, t)) + src[end:]
        wired[key] = 1
        n += 1
    return src


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--slug', default=None)
    args = ap.parse_args()

    reg = json.loads(REG.read_text(encoding='utf-8'))
    wired_n = text_n = img_n = 0
    for slug, e in reg.items():
        if args.slug and slug != args.slug:
            continue
        if e.get('tier') == 'injectable' or not slug.startswith('sc-'):
            continue
        f = CARDS / f'card-{slug}.tsx'
        if not f.exists():
            continue
        src = f.read_text(encoding='utf-8')
        if 'const __INJ__' not in src:
            # 注入头
            src = src.replace(
                "import React from 'react';",
                "import React from 'react';\nconst __INJ__: any = (globalThis as any).__OUTVIDEO_CARD__ ?? {};",
                1)
            if 'const __INJ__' not in src:  # 无 React import 的兜底
                src = "const __INJ__: any = (globalThis as any).__OUTVIDEO_CARD__ ?? {};\n" + src
        wired: dict = {}
        src2 = wire_text(src, wired)
        src2 = wire_str_consts(src2, wired)
        src2 = wire_staticfile_images(src2, wired)
        src2 = wire_images(src2, wired)
        src2 = wire_titleblock(src2, wired)
        src2 = wire_obj_text_arrays(src2, wired)
        src2 = wire_jsx_text(src2, wired)
        if not wired:
            continue
        if not args.dry:
            f.write_text(src2, encoding='utf-8')
            e['tier'] = 'injectable'
            arities = {}
            for k in ('TEXT', 'TEXT2', 'TEXT3'):
                if k in wired:
                    arities[k] = wired[k]
            e['arities'] = arities
            if wired.get('images'):
                e['images'] = wired['images']
            e['desc'] = e.get('desc', slug) + '（已接线）'
        wired_n += 1
        text_n += sum(1 for k in wired if k.startswith('TEXT'))
        img_n += len(wired.get('images', []))
        if args.dry:
            print(f"  [dry] {slug}: {wired}")
    if not args.dry:
        REG.write_text(json.dumps(reg, ensure_ascii=False, indent=1), 'utf-8')
    print(f"[wire] 接线 {wired_n} 张（文字槽 {text_n}，图片槽 {img_n}）{'--dry' if args.dry else ''}")


if __name__ == '__main__':
    main()
