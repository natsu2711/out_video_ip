#!/usr/bin/env python3
"""一键生成资产卡。

两种模式：
  1) 模板模式：--slug <slug> --template <text|serif|mono|steps|title> --lines N --category <cat>
     → 按内置 PPT 风格模板生成 card-<slug>.tsx（内容注入点齐备，tier=injectable，
       改文字即用，自动进 registry）
  2) 收编模式：--from-tsx <外部.tsx> --slug <slug> [--component <导出名>]
     → 把外部自包含 tsx 组件复制为卡（组件读不读 __INJ__ 由来源决定，
       读 → tier=injectable；不读 → tier=raw，可在编排手动用，不进自动路由）

生成后自动登记 registry.json（含 category，shotcraft 词表）。
分类（shotcraft 词表）：opening / typography / ui-entrance / camera / data /
interaction / transition / rhythm / effects / outro

用法:
  python scripts/gen_card.py --slug my-title --template title --category opening --lines 2
  python scripts/gen_card.py --from-tsx /path/X.tsx --slug x --category data
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "render-engine" / "src" / "cards"
REG = CARDS / "registry.json"

CATEGORIES = ["opening", "typography", "ui-entrance", "camera", "data",
              "interaction", "transition", "rhythm", "effects", "outro"]

HEADER = """// [outvideo] card-{slug} —— 由 scripts/gen_card.py 一键生成（模板: {template}）。
// 内容注入点：globalThis.__OUTVIDEO_CARD__ = {{ TEXT: [...] }}（改文字即用，动效不动）
import React from "react";
import {{ AbsoluteFill, interpolate, Easing, useCurrentFrame }} from "remotion";

const __INJ__: any = (globalThis as any).__OUTVIDEO_CARD__ ?? {{}};
export const meta = {{ width: 960, height: 540, fps: 30, durationInFrames: {dur} }};

const ease = Easing.bezier(0.22, 1, 0.36, 1);
"""

ACCENTS = {
    "text":   {"bg": "#F8F7F4", "ink": "#212529", "ac": "#1971C2", "font": "'PingFang SC','Microsoft YaHei',sans-serif"},
    "serif":  {"bg": "#F7F4EC", "ink": "#26221C", "ac": "#B08D57", "font": "'Songti SC','STSong','Noto Serif SC',serif"},
    "mono":   {"bg": "#0D1117", "ink": "#E6EDF3", "ac": "#7EE787", "font": "'SF Mono','Menlo',monospace"},
    "steps":  {"bg": "#F8F7F4", "ink": "#212529", "ac": "#D6336C", "font": "'PingFang SC','Microsoft YaHei',sans-serif"},
    "title":  {"bg": "#F8F7F4", "ink": "#212529", "ac": "#1971C2", "font": "'PingFang SC','Microsoft YaHei',sans-serif"},
}


def body_text(accent: dict, lines: int) -> str:
    arr = ", ".join(f'"{i + 1}. 文字槽位 {i + 1}"' for i in range(lines))
    body = """
const LINES: string[] = (__INJ__.TEXT as string[])?.length
  ? (__INJ__.TEXT as string[]).slice(0, __LINES__)
  : [__ARR__];

export default function Card() {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: "__BG__", fontFamily: "__FONT__" }}>
      {LINES.map((t, i) => {
        const p = interpolate(f, [4 + i * 8, 14 + i * 8], [0, 1],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
        if (p <= 0) return null;
        return (
          <div key={i} style={{
            position: "absolute", left: 80, right: 80, top: 90 + i * 110,
            opacity: p, transform: `translateY(${(1 - p) * 26}px)`,
            background: "#FFFFFF", border: "1px solid rgba(33,37,41,0.12)", borderRadius: 12,
            padding: "18px 26px", fontSize: 34, fontWeight: 800, color: "__INK__",
            boxShadow: `0 ${10 * p}px ${26 * p}px rgba(33,37,41,${0.10 * p})`,
          }}>
            <span style={{ color: "__AC__", marginRight: 14, fontSize: 26 }}>■</span>{t}
          </div>
        );
      })}
    </AbsoluteFill>
  );
}
"""
    return (body.replace("__LINES__", str(lines)).replace("__ARR__", arr)
                .replace("__BG__", accent["bg"]).replace("__INK__", accent["ink"])
                .replace("__AC__", accent["ac"]).replace("__FONT__", accent["font"]))


def body_serif(lines: int) -> str:
    if lines > 2:
        return body_text(ACCENTS["serif"], lines)
    body = """
const MAIN: string = (__INJ__.TEXT as string[])?.[0] ?? "慢就是快";
const SUB: string = (__INJ__.TEXT as string[])?.[1] ?? "";

export default function Card() {
  const f = useCurrentFrame();
  const p = interpolate(f, [4, 20], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  const q = interpolate(f, [18, 30], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  return (
    <AbsoluteFill style={{ background: "#F7F4EC" }}>
      <div style={{ position: "absolute", left: 90, top: 80, bottom: 80, width: 1,
                    background: "linear-gradient(#B08D57, transparent)", opacity: p }} />
      <div style={{ position: "absolute", left: 150, top: 170, right: 90,
                    fontFamily: "'Songti SC','STSong',serif", fontSize: 78, fontWeight: 700,
                    color: "#26221C", letterSpacing: "0.06em",
                    opacity: p, transform: `translateY(${(1 - p) * 20}px)` }}>
        {MAIN}
      </div>
      {SUB && (
        <div style={{ position: "absolute", left: 152, top: 400, fontFamily: "'Songti SC',serif",
                      fontSize: 24, color: "#8A7A5C", letterSpacing: 4, opacity: q }}>{SUB}</div>
      )}
    </AbsoluteFill>
  );
}
"""
    return body


def body_steps(accent: dict, lines: int) -> str:
    lines = max(2, min(4, lines))
    arr = ", ".join(f'"{i + 1}. 步骤 {i + 1}"' for i in range(lines))
    tops = {2: 170, 3: 120, 4: 100}
    body = """
const STEPS: string[] = (__INJ__.STEPS as string[])?.length
  ? (__INJ__.STEPS as string[]).slice(0, __LINES__)
  : [__ARR__];

export default function Card() {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: "__BG__" }}>
      {STEPS.map((t, i) => {
        const p = interpolate(f, [4 + i * 4.2, 15 + i * 4.2], [0, 1],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
        if (p <= 0) return null;
        return (
          <div key={i} style={{
            position: "absolute", left: 64, right: 64, top: 70 + i * __TOP__, height: 96, opacity: p,
            transform: `translateY(${(1 - p) * 30}px)`,
            background: "#FFFFFF", border: "1px solid rgba(33,37,41,0.12)", borderRadius: 14,
            display: "flex", alignItems: "center", gap: 16, padding: "0 26px",
            boxShadow: `0 ${10 * p}px ${26 * p}px rgba(33,37,41,${0.10 * p})`,
          }}>
            <div style={{ width: 48, height: 48, borderRadius: 10, background: "__AC__",
                          color: "#fff", display: "flex", alignItems: "center", justifyContent: "center",
                          fontSize: 22, fontWeight: 900, transform: `scale(${0.6 + 0.4 * p})` }}>
              {i + 1}
            </div>
            <div style={{ fontSize: 30, fontWeight: 800, color: "__INK__" }}>{t}</div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
}
"""
    return (body.replace("__LINES__", str(lines)).replace("__ARR__", arr)
                .replace("__TOP__", str(tops.get(lines, 120)))
                .replace("__BG__", accent["bg"]).replace("__INK__", accent["ink"])
                .replace("__AC__", accent["ac"]))


def body_title(accent: dict) -> str:
    body = """
const TITLE: string = (__INJ__.TEXT as string[])?.[0] ?? "章节标题";
const PHASE: string = (__INJ__.TEXT as string[])?.[1] ?? "阶段 01";

export default function Card() {
  const f = useCurrentFrame();
  const pillP = interpolate(f, [4, 14], [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.34, 1.56, 0.64, 1) });
  const titleP = interpolate(f, [14, 28], [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  return (
    <AbsoluteFill style={{ background: "__BG__" }}>
      <div style={{ position: "absolute", left: 110, top: 150, opacity: Math.min(1, pillP * 1.3),
                    transform: `scale(${0.6 + 0.4 * pillP})`, transformOrigin: "left center",
                    background: "#fff", border: "2px solid __AC__", borderRadius: 999,
                    padding: "10px 26px", display: "inline-flex", alignItems: "center", gap: 10 }}>
        <span style={{ width: 10, height: 10, borderRadius: "50%", background: "__AC__" }} />
        <span style={{ fontSize: 24, fontWeight: 800, color: "__AC__", letterSpacing: 3 }}>{PHASE}</span>
      </div>
      <div style={{ position: "absolute", left: 110, top: 240, right: 110, opacity: titleP,
                    transform: `translateY(${(1 - titleP) * 24}px)`,
                    fontSize: 84, fontWeight: 900, color: "__INK__", letterSpacing: "0.04em" }}>
        {TITLE}
      </div>
      <div style={{ position: "absolute", left: 110, bottom: 96, width: 500, height: 8,
                    background: "#E9ECEF", borderRadius: 4 }}>
        <div style={{ width: "62%", height: "100%", background: "__AC__", borderRadius: 4 }} />
      </div>
    </AbsoluteFill>
  );
}
"""
    return (body.replace("__BG__", accent["bg"]).replace("__INK__", accent["ink"])
                .replace("__AC__", accent["ac"]))


def build_body(template: str, lines: int) -> str:
    accent = ACCENTS.get(template, ACCENTS["text"])
    if template == "serif":
        return body_serif(lines)
    if template == "steps":
        return body_steps(accent, lines)
    if template == "title":
        return body_title(accent)
    return body_text(accent, lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--template", default="text", choices=["text", "serif", "mono", "steps", "title"])
    ap.add_argument("--lines", type=int, default=2)
    ap.add_argument("--category", default="effects", choices=CATEGORIES)
    ap.add_argument("--from-tsx", default=None, help="收编模式：外部自包含 tsx 路径")
    ap.add_argument("--component", default=None, help="收编模式的导出名（默认 Card）")
    ap.add_argument("--dur", type=int, default=110)
    args = ap.parse_args()

    slug = args.slug.strip()
    if not re.fullmatch(r"[a-z0-9\-]+", slug):
        raise SystemExit(f"slug 只限小写字母/数字/连字符: {slug}")
    card_file = CARDS / f"card-{slug}.tsx"
    if card_file.exists():
        raise SystemExit(f"已存在: {card_file.name}（换 slug 或先删除）")

    if args.from_tsx:
        ext = Path(args.from_tsx).resolve()
        if not ext.exists():
            raise SystemExit(f"来源不存在: {ext}")
        comp = args.component or "Card"
        src = ext.read_text(encoding="utf-8")
        exported = f"export const {args.component}" in src or f"export function {args.component}" in src \
            or f"export default" in src
        # 自包含检查：只依赖 remotion/react 才能直接收编为 injectable
        ext_imports = [l for l in src.splitlines() if l.strip().startswith("import")]
        foreign = [l for l in ext_imports if not re.search(r"from ['\"](react|remotion)['\"]", l)]
        header = (f"// [outvideo] card-{slug} —— 由 gen_card.py 收编自 {ext.name}。\n"
                  f"// 动效原样保留；内容注入点需按原组件的常量名手工补 __INJ__ 接线。\n")
        body = src
        # 统一加 default 导出（若无）
        if "export default" not in body:
            body += f"\n\nexport default {args.component};\n"
        has_inj = "__INJ__" in src
        tier = ("injectable" if has_inj else "raw") if not foreign else "raw"
        content = header + body
        arities: dict = {}
        note = ("收编自外部 tsx；" + ("检测到内容注入点 ✓" if has_inj else "未检测到 __INJ__ 接线 → raw 手动档") +
                ("；含外部依赖 → raw" if foreign else ""))
    else:
        content = HEADER.format(slug=slug, template=args.template, dur=args.dur) + \
            build_body(args.template, args.lines)
        tier = "injectable"
        arities = {"TEXT": max(1, args.lines)}
        exported = True
        note = "模板生成"

    card_file.write_text(content, encoding="utf-8")

    reg = json.loads(REG.read_text(encoding="utf-8"))
    reg[slug] = {
        "slug": slug,
        "component": (args.component or "Card") if args.from_tsx else "Card",
        "tier": tier,
        "contentKeys": dict(arities) if arities else {},
        "arities": arities,
        "durationInFrames": args.dur,
        "category": args.category,
        "desc": f"{note}（{args.category}）",
        "sourceFile": f"{slug}.tsx",
    }
    REG.write_text(json.dumps(reg, ensure_ascii=False, indent=1), "utf-8")
    print(f"[gen-card] ✓ card-{slug}.tsx 已生成并登记（tier={tier}, category={args.category}）")
    print(f"[gen-card] 可用：编排右侧「资产卡」页签搜索 {slug}；自动路由需再加进 pipeline/variety.py 的 BEAT_CARDS 池")


if __name__ == "__main__":
    main()
