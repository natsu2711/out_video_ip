#!/usr/bin/env python3
"""开工体检（吸收 talkcraft preflight 理念：答案在文档里，但没人强制在正确时刻查——
所以不补文档，做成渲前必跑断言。任一 FAIL 挡住 s5 渲染，把返工消灭在渲前）。

检查项（全部源自实测翻车）：
  1. voice ref_audio 存在               （曾因路径搬家静默丢失）
  2. manifest ip_images 路径存在         （曾因引用已删除的占位图）
  3. recipe_ref 全部可解析               （曾因组件注册键拼写渲出黑屏）
  4. sfx cue 文件全部在盘                （曾因 pk- 前缀 22/50 条静默丢失）
  5. node_modules/.cache 存在 → FAIL     （曾因 webpack 旧 bundle 渲出竖屏旧组件，返工三轮）
  6. 全片零 B-roll/图片/截图素材 → WARN  （纯动效+口播 = PPT 感，talkcraft ③ 硬规）
  7. ffmpeg / node / remotion CLI 在位

用法: preflight.py <job_dir>   （s5 渲染前自动调用，也可手动跑）
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

fails: list[str] = []
warns: list[str] = []


def fail(msg: str) -> None:
    fails.append(msg)
    print(f"[preflight] ✗ {msg}")


def warn(msg: str) -> None:
    warns.append(msg)
    print(f"[preflight] ⚠ {msg}")


def ok(msg: str) -> None:
    print(f"[preflight] ✓ {msg}")


def main() -> None:
    job = Path(sys.argv[1]).resolve()
    proj = json.loads((job / "project.json").read_text(encoding="utf-8"))
    sb = json.loads((job / "storyboard.json").read_text(encoding="utf-8"))
    manifest_p = job / "assets" / "manifest.json"
    manifest = json.loads(manifest_p.read_text(encoding="utf-8")) if manifest_p.exists() else {}

    # 1. 音色参考
    ref = proj.get("voice", {}).get("ref_audio", "")
    if ref and Path(ref).exists():
        ok(f"音色参考在盘: {Path(ref).name}")
    else:
        fail(f"音色参考不存在: {ref}")

    # 1.5 口播稿数字汉字铁律（对齐逐字锚定的前置条件：阿拉伯数字无法与读音对位）
    script_p = job / "script.json"
    if script_p.exists():
        import re
        script = json.loads(script_p.read_text(encoding="utf-8"))
        bad = [seg["id"] for seg in script.get("segments", [])
               if re.search(r"[0-9]", seg.get("text", ""))]
        if bad:
            fail(f"口播稿含阿拉伯数字（须转汉字）: {bad}")
        else:
            ok("口播稿数字全部为汉字")

    # 2. IP/图片素材（主图 ip三视图/ip.jpg + 逐镜场景图 ipXX.jpg）
    ip_imgs = manifest.get("ip_images") or {}
    for view, p in ip_imgs.items():
        pp = Path(p) if Path(p).is_absolute() else ROOT / p
        if pp.exists():
            ok(f"IP 图[{view}] 在盘")
        else:
            fail(f"IP 图[{view}] 不存在: {p}")
    for shot_id, p in (manifest.get("ip_scenes") or {}).items():
        pp = Path(p) if Path(p).is_absolute() else ROOT / p
        if pp.exists():
            ok(f"场景图[{shot_id}] 在盘")
        else:
            fail(f"场景图[{shot_id}] 不存在: {p}")

    # 3. recipe_ref 可解析（卡: registry.json；本地: SHOT_COMPONENTS 注册表）
    reg = json.loads((ROOT / "render-engine" / "src" / "cards" / "registry.json").read_text(encoding="utf-8"))
    comp_src = "".join(
        p.read_text(encoding="utf-8")
        for p in (ROOT / "render-engine" / "src" / "compositions").glob("*.tsx")
    )  # 重构后 SHOT_COMPONENTS 表在 ShotRenderer.tsx，扫描全部 compositions 源码
    has_visual_asset = False
    for shot in sb["shots"]:
        ref_name = shot["recipe_ref"]
        if ref_name.startswith("card:"):
            slug = ref_name[5:]
            if slug not in reg:
                fail(f"{shot['id']}: 卡未移植 {slug}")
            else:
                ok(f"{shot['id']}: card:{slug}")
        elif ref_name in ("TitleCard", "EndingCard", "KineticTitle", "ARollScene", "ScreenshotCard") or \
                f"'local:shots/{ref_name}'" in comp_src:
            ok(f"{shot['id']}: {ref_name}")
        else:
            fail(f"{shot['id']}: recipe_ref 无法解析: {ref_name}")
        if shot.get("assets_needed") or (shot.get("roll") == "A"):
            has_visual_asset = True

    # 4. 音效 cue 文件 + 间距
    sfx_dir = ROOT / "render-engine" / "public" / "sfx"
    n_cues = 0
    abs_cues: list[tuple[str, int]] = []
    for shot in sb["shots"]:
        for cue in shot.get("sfx") or []:
            n_cues += 1
            name = cue["name"]
            if not ((sfx_dir / f"{name}.mp3").exists() or (sfx_dir / f"pk-{name}.mp3").exists()):
                fail(f"{shot['id']}: 音效不在盘: {name}")
            abs_cues.append((name, shot["time"]["start_ms"] + cue["t_ms"]))
    if n_cues:
        ok(f"音效 cue {n_cues} 条（文件全查）")
        abs_cues.sort(key=lambda c: c[1])
        for (n1, t1), (n2, t2) in zip(abs_cues, abs_cues[1:]):
            if t2 - t1 < 300:
                fail(f"音效堆叠: {n1}@{t1} 与 {n2}@{t2} 仅隔 {t2-t1}ms（<300ms 会互相打架）")

    # 5. webpack 缓存（旧 bundle 曾致三轮返工）
    cache = ROOT / "render-engine" / "node_modules" / ".cache"
    if cache.exists() and any(cache.iterdir()):
        shutil.rmtree(cache)
        print("[preflight] ✓ 清除 webpack 缓存（防旧 bundle 复发）")

    # 6. 素材丰富度
    n_visual = sum(1 for s in sb["shots"] if s.get("b_type") in ("graphic", "real") or s.get("roll") == "A")
    if not has_visual_asset and n_visual == 0:
        warn("全片无实拍/图片素材（纯动效+口播 = PPT 感）")

    # 7. 工具链
    for tool in ("ffmpeg", "node"):
        if shutil.which(tool):
            ok(f"{tool} 在位")
        else:
            fail(f"{tool} 不在 PATH")

    remotion_cli = ROOT / "render-engine" / "node_modules" / ".bin" / "remotion"
    if remotion_cli.exists():
        ok("remotion CLI 在位")
    else:
        fail("remotion CLI 未安装（render-engine/node_modules）")

    # 8. remotion 系版本一致性（rough-notation 曾拉高 paths 版本致全链渲染崩）
    pkg = ROOT / "render-engine" / "package.json"
    nm = ROOT / "render-engine" / "node_modules"
    if pkg.exists() and nm.exists():
        deps = {**json.loads(pkg.read_text(encoding="utf-8")).get("dependencies", {}),
                **json.loads(pkg.read_text(encoding="utf-8")).get("devDependencies", {})}
        versions: dict[str, str] = {}
        for name in deps:
            if name.startswith("@remotion/") or name == "remotion":
                pj = nm / name / "package.json"
                if pj.exists():
                    versions[name] = json.loads(pj.read_text(encoding="utf-8")).get("version", "?")
        distinct = set(versions.values())
        if len(distinct) > 1:
            fail(f"remotion 系版本不一致: {versions}（必须统一）")
        else:
            ok(f"remotion 系版本一致: {next(iter(distinct), '?')}")

    # 9. 复现性：LLM 链配置记录进 state（谁生成的可追溯）
    import os
    chain = os.environ.get("PIPELINE_LLM_CHAIN", "ollama:qwen3.5:9b-q4_K_M -> none(默认)")
    state_p = job / "state.json"
    if state_p.exists():
        st = json.loads(state_p.read_text(encoding="utf-8"))
        st.setdefault("meta", {})["llm_chain"] = chain
        state_p.write_text(json.dumps(st, ensure_ascii=False, indent=2), "utf-8")

    print()
    if fails:
        print(f"[preflight] FAIL：{len(fails)} 项不合格（{len(warns)} 警告）→ 修复后再渲")
        sys.exit(1)
    print(f"[preflight] PASS（{len(warns)} 警告）")


if __name__ == "__main__":
    main()
