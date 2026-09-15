#!/usr/bin/env python3
"""S4C：文案→匹配素材视频（吸收自 MoneyPrinterTurbo 的核心单点能力）。

对候选 B-roll 镜头搜索免费素材（Pexels/Pixabay），下载到 assets/broll_videos/，
登记进 manifest（broll_videos）→ S5 渲染时 B-roll 自动升级为真实素材（RealFootage 配方）。

降级梯度：
  有 API key → 搜索+下载，全自动
  无 key     → 产出关键词任务单（assets/stock_keywords.json），人工去素材站搜

用法: s4c_stock_footage.py <job_dir> [--max N] [--dry-run]
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.adapters import registry  # noqa: E402
from pipeline.adapters import stock_footage as sf  # noqa: E402
from pipeline import llm  # noqa: E402


def try_llm_chain():
    try:
        llm.complete("ping", temperature=0)
        return llm
    except llm.LLMChainError:
        return None


def download(url: str, out: Path, max_mb: int = 40) -> bool:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(out, "wb") as f:
        n = 0
        while chunk := r.read(1 << 16):
            n += len(chunk)
            if n > max_mb << 20:
                f.close()
                out.unlink(missing_ok=True)
                return False
            f.write(chunk)
    return out.exists() and out.stat().st_size > 100_000


def main() -> None:
    job = Path(sys.argv[1]).resolve()
    dry = "--dry-run" in sys.argv
    max_n = 6
    if "--max" in sys.argv:
        max_n = int(sys.argv[sys.argv.index("--max") + 1])

    sb = json.loads((job / "storyboard.json").read_text(encoding="utf-8"))
    manifest_path = job / "assets" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest.setdefault("broll_videos", {})

    adapters = registry.by_capability("stock_footage")
    adapter = adapters[0] if adapters else sf.StockFootageAdapter()
    ok, msg = adapter.available()
    chain = try_llm_chain() if ok else None

    # 候选：B-roll 里未启用真实素材的（排首末镜；已有图/broll 的跳过）
    candidates = [s for s in sb["shots"]
                  if s["roll"] == "B" and s["recipe_ref"] not in ("TitleCard", "EndingCard")
                  and s["id"] not in manifest.get("broll_videos", {})]
    chosen = candidates[:max_n]
    print(f"[s4c] 候选 {len(candidates)} 镜，处理 {len(chosen)}（{'dry-run' if dry else '下载'}）")

    if not ok:
        # 降级：关键词任务单
        briefs = []
        for s in chosen:
            terms = sf.derive_keywords(s, chain)
            briefs.append({"shot_id": s["id"], "keywords": terms,
                           "search_url": "https://www.pexels.com/search/videos/" + "%20".join(terms[:2]) + "/"})
        out = job / "assets" / "stock_keywords.json"
        out.write_text(json.dumps({"version": "1.0", "mode": "manual",
                                   "note": "配 PEXELS_API_KEY 后重跑即全自动", "briefs": briefs},
                                  ensure_ascii=False, indent=1), "utf-8")
        print(f"[s4c] ⚠ {msg} → 关键词任务单 {out}")
        return

    got = 0
    for s in chosen:
        res = adapter.produce(s, llm_chain=chain, min_duration=max(4, (s["time"]["end_ms"] - s["time"]["start_ms"]) // 1000 - 1))
        if not res["clips"]:
            print(f"[s4c] {s['id']}: 无结果 {res['keywords']}")
            continue
        clip = res["clips"][0]
        out_path = job / "assets" / "broll_videos" / f"{s['id']}.mp4"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if dry:
            print(f"[s4c] {s['id']}: [dry] {clip['provider']} {clip['url'][:60]}")
            continue
        if download(clip["url"], out_path):
            manifest["broll_videos"][s["id"]] = {
                "path": f"assets/broll_videos/{s['id']}.mp4",
                "provider": clip["provider"], "duration": clip["duration"],
                "keywords": res["keywords"]}
            got += 1
            print(f"[s4c] ✓ {s['id']}: {clip['provider']} {clip['duration']}s ← {res['keywords']}")
        else:
            print(f"[s4c] ✗ {s['id']}: 下载失败")

    if not dry and got:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), "utf-8")
        print(f"[s4c] ✔ manifest 更新：{got} 镜升级真实素材（S5 渲染时自动用 RealFootage）")


if __name__ == "__main__":
    main()
