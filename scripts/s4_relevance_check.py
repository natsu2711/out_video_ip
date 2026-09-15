#!/usr/bin/env python3
"""S4 相关性排除器：只排除与镜头内容"完全不沾边"的素材（Pexels 搜歪、生图跑偏），
不做语义正确性验收（那是编排层的事）。命中低分不删图，标 relevance_flag: low → 渲染降透明度退为背景纹理。

后端：
  clip      —— CLIP 图文相似度（需 .venv 装 open_clip_torch + torch；自动探测）
  unavailable —— 未装模型时降级：产出空报告 + 待标注清单（非阻塞，绝不挡出片）

阈值校准（先标注再定阈值，不拍脑袋）：
  1) 人工挑 20 组"沾边/不沾边"图 → 写 assets/relevance-calibration.csv（path,label 0/1）
  2) `--calibrate` 跑分 sweep，选最优阈值写回 manifest 默认
用法: s4_relevance_check.py <job_dir> [--calibrate csv] [--threshold 0.20]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def clip_backend():
    try:
        import torch  # noqa: F401
        import open_clip  # noqa: F401
        return True
    except ImportError:
        return False


def score_image_clip(model, preprocess, tokenizer, image_path: Path, queries: list[str]) -> float:
    """图 vs 镜头文本 query 的最大 CLIP 相似度（归一化 0~1）。"""
    import torch
    from PIL import Image
    image = preprocess(Image.open(image_path).convert("RGB")).unsqueeze(0)
    text = tokenizer(queries)
    with torch.no_grad():
        img_f = model.encode_image(image)
        txt_f = model.encode_text(text)
        img_f /= img_f.norm(dim=-1, keepdim=True)
        txt_f /= txt_f.norm(dim=-1, keepdim=True)
        sims = (img_f @ txt_f.T).squeeze(0)
    return float(max(0.0, sims.max().item()))


def shot_queries(shot: dict) -> list[str]:
    """镜头文本侧 query：意图 + 画面描述（截断拼接）。"""
    parts = [shot.get("intent", ""), shot.get("visual", ""), shot.get("vo", "")[:40]]
    return [p for p in parts if p.strip()]


def load_model():
    import torch
    import open_clip
    model, _, preprocess = open_clip.create_model_and_transforms("ViT-B-32", pretrained="laion2b_s34b_b79k")
    tokenizer = open_clip.get_tokenizer("ViT-B-32")
    model.eval()
    return model, preprocess, tokenizer, torch


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("job_dir")
    ap.add_argument("--calibrate", help="20 组标注 CSV（path,label）跑阈值 sweep")
    ap.add_argument("--threshold", type=float, default=0.20)
    args = ap.parse_args()
    job = Path(args.job_dir).resolve()

    sb = json.loads((job / "storyboard.json").read_text(encoding="utf-8"))
    manifest_p = job / "assets" / "manifest.json"
    report = {"mode": "clip" if clip_backend() else "unavailable", "threshold": args.threshold, "flags": {}}

    if args.calibrate:
        if not clip_backend():
            print("[relevance] ✗ 校准需要 CLIP：.venv/bin/python -m pip install open_clip_torch torch", file=sys.stderr)
            sys.exit(1)
        model, preprocess, tokenizer, torch = load_model()
        rows = list(csv.DictReader(open(args.calibrate, encoding="utf-8-sig")))
        print(f"[relevance] 校准集 {len(rows)} 组，sweep 阈值…")
        scored = [(r["path"], int(r["label"]),
                   score_image_clip(model, preprocess, tokenizer, Path(r["path"]),
                                    [r.get("query", "video")])) for r in rows]
        best = (0.0, args.threshold)
        for t in [x / 100 for x in range(10, 40)]:
            tp = sum(1 for _, l, s in scored if s >= t and l == 1) + sum(1 for _, l, s in scored if s < t and l == 0)
            acc = tp / len(scored)
            if acc > best[0]:
                best = (acc, t)
        print(f"[relevance] 最优阈值 {best[1]}（准确率 {best[0]:.0%}）→ 写入 {job}/assets/relevance-threshold.json")
        (job / "assets" / "relevance-threshold.json").write_text(
            json.dumps({"threshold": best[1], "accuracy": best[0]}, ensure_ascii=False), "utf-8")
        return

    if not report["mode"] == "clip":
        # ponytail: 无 CLIP 时本环节不可判图（启发式无法看图，宁可不判也不误杀）——升级路径装模型
        out = job / "assets" / "relevance-report.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps({**report,
                                   "note": "CLIP 未安装（.venv/bin/python -m pip install open_clip_torch torch），"
                                           "先标 20 组校准集再 --calibrate"},
                                  ensure_ascii=False, indent=1), "utf-8")
        print(f"[relevance] ⚠ CLIP 未安装 → 跳过（非阻塞），报告 {out}")
        return

    model, preprocess, tokenizer, torch = load_model()
    thr_file = job / "assets" / "relevance-threshold.json"
    threshold = json.loads(thr_file.read_text())["threshold"] if thr_file.exists() else args.threshold

    n = flagged = 0
    for shot in sb["shots"]:
        img = job / "assets" / "broll" / f"{shot['id']}.png"
        if shot["roll"] != "B" or not img.exists():
            continue
        score = score_image_clip(model, preprocess, tokenizer, img, shot_queries(shot))
        n += 1
        if score < threshold:
            report["flags"][shot["id"]] = {"score": round(score, 3), "flag": "low"}
            flagged += 1
            print(f"[relevance] ⚠ {shot['id']}: score {score:.3f} < {threshold} → relevance_flag=low（渲染降为背景纹理）")
        else:
            report["flags"][shot["id"]] = {"score": round(score, 3), "flag": "ok"}
        # 分数回写 manifest（渲染端可消费 relevance_flag 降透明度）
        manifest_p = job / "assets" / "manifest.json"
        manifest = json.loads(manifest_p.read_text(encoding="utf-8")) if manifest_p.exists() else {}
        manifest.setdefault("relevance", {})[shot["id"]] = report["flags"][shot["id"]]
        manifest_p.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), "utf-8")

    out = job / "assets" / "relevance-report.json"
    report["scored"] = n
    report["flagged"] = flagged
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), "utf-8")
    print(f"[relevance] ✔ {n} 张已判，{flagged} 张标 low → {out}")


if __name__ == "__main__":
    main()
