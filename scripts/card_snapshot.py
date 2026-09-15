#!/usr/bin/env python3
"""卡片视觉回归快照：每张 injectable 卡用固定 fixture 内容渲一帧 → tests/snapshots/<slug>.png。
--check：与存量快照像素 diff（PIL，>2% 差异告警并存 diff 图）——改崩卡立刻现形。
全量 63 张约 10 分钟（每张一次 Remotion still）；日常改卡后用 --only 抽测。

用法:
  card_snapshot.py --only number-counter,quote-card   # 建快照
  card_snapshot.py --check --only number-counter      # 回归比对
  card_snapshot.py --all                              # 全量（慢）
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAP_DIR = ROOT / "tests" / "snapshots"
REG = json.loads((ROOT / "render-engine" / "src" / "cards" / "registry.json").read_text("utf-8"))
FIXTURE_TEXT = ["观点核心词", "论据一二三", "支撑说明文字", "补充要点占位", "数据要点演示", "结尾示例文案"]
FIXTURE_STEPS = ["第一步准备", "第二步执行", "第三步验证", "第四步交付", "第五步复盘"]
DIFF_THRESHOLD = 0.02  # 像素差 >2% 告警（忽略 <16/255 的压缩噪声）


def render_card(slug: str, out_png: Path) -> None:
    entry = REG[slug]
    ar = entry.get("arities", {})
    props: dict = {"slug": slug}
    if ar.get("TEXT"):
        props["TEXT"] = FIXTURE_TEXT[: ar["TEXT"]]
    if ar.get("STEPS"):
        props["STEPS"] = FIXTURE_STEPS[: ar["STEPS"]]
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(props, f, ensure_ascii=False)
        props_file = f.name
    out_png.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["npx", "remotion", "still", "src/index.ts", "CardSnapshot", str(out_png),
         "--props", props_file, "--frame=30", "--log=error"],
        cwd=str(ROOT / "render-engine"), check=True, timeout=180,
    )


def diff_ratio(a: Path, b: Path) -> float:
    from PIL import Image, ImageChops
    ia, ib = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    if ia.size != ib.size:
        ib = ib.resize(ia.size)
    hist = ImageChops.difference(ia, ib).convert("L").histogram()
    return sum(hist[16:]) / max(1, sum(hist))


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true")
    g.add_argument("--only", help="逗号分隔 slug 列表")
    ap.add_argument("--check", action="store_true", help="回归比对（渲新帧 vs 存量快照）")
    args = ap.parse_args()

    slugs = sorted(s for s, e in REG.items() if e.get("tier") == "injectable")
    if args.only:
        want = {s.strip() for s in args.only.split(",")}
        bad = want - set(slugs)
        if bad:
            print(f"[snapshot] ⚠ 非 injectable 或不存在: {bad}")
        slugs = sorted(want & set(slugs))

    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    fails = []
    with tempfile.TemporaryDirectory() as td:
        for slug in slugs:
            tmp_png = Path(td) / f"{slug}.png"
            try:
                render_card(slug, tmp_png)
            except Exception as e:  # noqa: BLE001
                fails.append(f"{slug}: 渲染失败 {e}")
                continue
            snap = SNAP_DIR / f"{slug}.png"
            if args.check:
                if not snap.exists():
                    print(f"[snapshot] {slug}: 无存量快照（跳过比对，可去掉 --check 先建基线）")
                    continue
                ratio = diff_ratio(snap, tmp_png)
                mark = "OK" if ratio <= DIFF_THRESHOLD else "FAIL"
                print(f"[snapshot] {slug}: diff {ratio:.1%} {mark}")
                if ratio > DIFF_THRESHOLD:
                    diff_img = SNAP_DIR / f"{slug}.diff.png"
                    diff_img.write_bytes(tmp_png.read_bytes())
                    fails.append(f"{slug}: 像素差 {ratio:.1%}（新帧存 {diff_img.name}）")
            else:
                snap.write_bytes(tmp_png.read_bytes())
                print(f"[snapshot] {slug}: 基线已存")

    if fails:
        print(f"[snapshot] ✗ {len(fails)} 项失败:")
        for f in fails:
            print("  -", f)
        sys.exit(1)
    print(f"[snapshot] ✔ {len(slugs)} 张卡{'比对通过' if args.check else '快照完成'}")


if __name__ == "__main__":
    main()
