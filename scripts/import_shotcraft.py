#!/usr/bin/env python3
"""批量移植 video-shotcraft/demos 的镜头食谱卡（157 张）到本项目。

移植规则（保留原动效，接上我们的内容注入）：
  1. 一次性拷贝 demos/_fixtures/{Motion,Fixtures}.tsx → cards/_sc/（相对路径不破）
  2. 每张 demo 主 tsx → cards/card-sc-<名>.tsx，import 路径改到 ./_sc/Motion
  3. 内容接线：扫描卡内字符串常量（数字上限/标题词等）无法通用推断——因此
     统一在组件外壳层注入：把卡源码里首个 `export const <X>: React.FC` 包装为
     default 导出，并在文件头加 __INJ__ 注释说明接线点；
     tier 判定：源码含 __INJ__ → injectable；否则 raw（可在编排手动用/后续逐张接线）
  4. duration：优先取源码 `export const *_DURATION = N`（帧），否则默认 110
  5. category = demo 所在目录名（就是 shotcraft 原分类）

用法:
  python scripts/import_shotcraft.py --all            # 全量（约 150+ 张）
  python scripts/import_shotcraft.py --cat data       # 只移植一个分类
  python scripts/import_shotcraft.py --dry            # 只看清单不动手
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = Path("/Users/bainazi/Documents/outtt/other/1other_video/video-shotcraft/demos")
CARDS = ROOT / "render-engine" / "src" / "cards"
REG = CARDS / "registry.json"

# shotcraft 目录 → 我们的三类
CAT3 = {
    "data": "narrative", "typography": "narrative", "opening": "narrative",
    "outro": "narrative", "rhythm": "narrative",
    "camera": "visual", "transition": "visual", "effects": "visual",
    "interaction": "visual", "ui-entrance": "visual",
}


def slug_of(demo_dir: str) -> str:
    return "sc-" + demo_dir.lower().replace("_", "-")


def find_main_tsx(demo: Path) -> Path | None:
    """demo 目录的主组件：与目录名最接近的 tsx，其次最大的非 Fixtures tsx。"""
    cands = [p for p in demo.glob("*.tsx") if p.name not in ("Fixtures.tsx", "Motion.tsx")]
    if not cands:
        return None
    stem = demo.name.replace("-", "").lower()
    for p in cands:
        if p.stem.replace("-", "").lower() == stem:
            return p
    return max(cands, key=lambda p: p.stat().st_size)


def extract_duration(src: str) -> int:
    m = re.search(r"export const \w*DURATION\w*\s*=\s*(\d+)", src)
    if m:
        return int(m.group(1))
    m = re.search(r"durationInFrames[^\d]{0,10}(\d{2,4})", src)
    return int(m.group(1)) if m else 110


def port(demo: Path, dry: bool = False) -> dict | None:
    main = find_main_tsx(demo)
    if not main:
        return None
    slug = slug_of(demo.name)
    src = main.read_text(encoding="utf-8")
    src2 = src.replace("../../_fixtures/", "./_sc/")
    has_inj = "__INJ__" in src2
    dur = extract_duration(src2)
    # default 导出补齐
    comp_m = re.search(r"export const (\w+): React\.FC", src2)
    comp = comp_m.group(1) if comp_m else None
    if comp and "export default" not in src2:
        src2 += f"\n\nexport default {comp};\n"
    if dry:
        return {"slug": slug, "comp": comp, "dur": dur, "tier": "injectable" if has_inj else "raw",
                "category3": CAT3.get(demo.parent.name, "visual"), "file": main.name}
    out = CARDS / f"card-{slug}.tsx"
    out.write_text(
        f"// [outvideo] card-{slug} —— 移植自 video-shotcraft/demos/{demo.parent.name}/{demo.name}\n"
        f"// 原动效保留；内容接线：{'已含 __INJ__' if has_inj else 'raw 档（可在编排手动用，后续逐张接 __INJ__）'}\n"
        + src2, encoding="utf-8")
    return {"slug": slug, "comp": comp or "Card", "dur": dur,
            "tier": "injectable" if has_inj else "raw",
            "category3": CAT3.get(demo.parent.name, "visual"),
            "sc_category": demo.parent.name, "desc": demo.name}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--cat", default=None)
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    dry = args.dry

    # fixtures 一次性拷贝
    fx = CARDS / "_sc"
    if not dry:
        fx.mkdir(exist_ok=True)
        for f in ("Motion.tsx", "Fixtures.tsx"):
            s = SRC / "_fixtures" / f
            if s.exists() and not (fx / f).exists():
                shutil.copy(s, fx / f)

    cats = [args.cat] if args.cat else [d.name for d in SRC.iterdir()
                                        if d.is_dir() and not d.name.startswith("_")]
    reg = json.loads(REG.read_text(encoding="utf-8"))
    done, skipped = [], []
    for cat in cats:
        for demo in sorted((SRC / cat).iterdir()):
            if not demo.is_dir() or demo.name.startswith("_"):
                continue
            slug = slug_of(demo.name)
            if slug in reg:
                skipped.append(slug)
                continue
            info = port(demo, args.dry)
            if not info:
                skipped.append(slug + "(无tsx)")
                continue
            done.append(info)
            if not args.dry:
                reg[slug] = {
                    "slug": slug, "component": info["comp"], "tier": info["tier"],
                    "contentKeys": {}, "arities": {},
                    "durationInFrames": info["dur"],
                    "category3": info["category3"],
                    "category": f"sc:{info.get('sc_category', cat)}",
                    "desc": f"shotcraft {info.get('sc_category', cat)} · {demo.name}",
                    "sourceFile": f"{slug}.tsx",
                }
    if not args.dry:
        REG.write_text(json.dumps(reg, ensure_ascii=False, indent=1), "utf-8")

    inj = sum(1 for i in done if i["tier"] == "injectable")
    print(f"[sc-import] 清单 {len(done)} 张（injectable {inj} / raw {len(done) - inj}），已存在跳过 {len(skipped)}")
    if args.dry:
        for i in done[:20]:
            print(f"  {i['slug']:44s} {i['tier']:11s} {i['dur']}f")
        print("  …（--dry 只预览）")


if __name__ == "__main__":
    main()
