#!/usr/bin/env python3
"""absorb.py —— 通用吸收工具：新 skill/开源项目接入本管线的标准入口。

流程（playbook 详见 docs/absorption.md）：
  1) scan    侦察项目 → 判断资产形态 → 推荐 adapter 类型
  2) scaffold 生成 adapter 骨架（含 provenance + 契约清单）
  3) 实现 produce()（通常只需填一个函数）
  4) verify  契约自检 + 注册表落盘
  5) 进闸    adapter 的产出接进对应环节（image_prompt→S4B，recipe→S3）

用法:
  absorb.py scan <project_dir>          # 侦察
  absorb.py scaffold <capability> <name> <source_project>  # 生成骨架
  absorb.py verify [adapter_name]       # 自检全部/单个
  absorb.py list                        # 注册表现状
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.adapters import registry  # noqa: E402

SKELETON = '''"""{name} 吸收：{desc}
来源：{source}（{method} 吸收）
由 absorb.py scaffold 生成——填 produce() 后跑 absorb.py verify {name}。"""
from __future__ import annotations

from pathlib import Path

from ..base import {base_cls}

SRC = Path("{source}")


class {cls}({base_cls}):
    name = "{name}"
    source_project = str(SRC)
    absorb_method = "{method}"
    description = "{desc}"

    def available(self) -> tuple[bool, str]:
        if not SRC.exists():
            return False, f"源不存在: {{SRC}}"
        return True, "待实现校验"

    def styles(self) -> list[str]:
        return ["default"]

    def produce(self, shot: dict, style: str | None = None) -> dict:
        raise NotImplementedError("填这里：把 shot 内容映射成 prompt")

    def self_check(self) -> list[str]:
        ok, msg = self.available()
        return [msg] if not ok else ["跑一次 produce 并断言关键字段"]


ADAPTER = {cls}()
'''


def detect_kind(project: Path) -> str:
    """侦察项目资产形态。"""
    has = lambda *names: any(list(project.rglob(n)) for n in names)  # noqa: E731
    tsx_cards = list(project.rglob("*.tsx"))
    if tsx_cards and len(tsx_cards) >= 5:
        return f"remotion_tsx_cards（{len(tsx_cards)} 个 tsx）→ 建议走 import_cards.py 式 codemod 移植为配方卡"
    if has("STYLES.md") or list(project.rglob("SKILL.md")):
        md_with_code = 0
        for f in list(project.rglob("*.md"))[:40]:
            if "```" in f.read_text(encoding="utf-8", errors="ignore"):
                md_with_code += 1
        if md_with_code:
            return f"prompt_pack（{md_with_code} 个含代码块/模板的 md）→ 建议 image_prompt/recipe_knowledge adapter"
    if list(project.rglob("*.py")) and list(project.rglob("*.py")).__len__() > 3:
        return "python_pipeline（含多个 py）→ 建议封装为外部调用 adapter（api 吸收，不 vendor）"
    return "unknown → 人工判断"


def cmd_scan(args) -> None:
    project = Path(args.project_dir).resolve()
    if not project.exists():
        sys.exit(f"目录不存在: {project}")
    print(f"[scan] {project}")
    print(f"  形态判断: {detect_kind(project)}")
    subs = [d.name for d in project.iterdir() if d.is_dir() and not d.name.startswith(".")][:10]
    print(f"  顶层目录: {subs}")


def cmd_scaffold(args) -> None:
    capability, name, source = args.capability, args.name, args.source
    base_cls = {"image_prompt": "ImagePromptAdapter",
                "recipe_knowledge": "RecipeKnowledgeAdapter",
                "script_structure": "ScriptStructureAdapter",
                "chart_render": "ChartRenderAdapter"}.get(capability)
    if not base_cls:
        sys.exit(f"未知 capability: {capability}（可选: image_prompt/recipe_knowledge/script_structure/chart_render）")
    cls = "".join(w.capitalize() for w in name.replace("-", "_").split("_"))
    method = "prompt_pack" if capability in ("image_prompt", "recipe_knowledge") else "api"
    out = ROOT / "pipeline" / "adapters" / f"{name.replace('-', '_')}.py"
    out.write_text(SKELETON.format(name=name, desc=args.desc, source=source,
                                   method=method, base_cls=base_cls, cls=cls), "utf-8")
    print(f"[scaffold] 骨架 → {out}")
    print(f"下一步: 实现 produce() 与 self_check()，然后 absorb.py verify {name}")


def cmd_verify(args) -> None:
    adapters = registry.all_adapters()
    if args.adapter_name:
        adapters = [a for a in adapters if a.name == args.adapter_name]
        if not adapters:
            sys.exit(f"未找到 adapter: {args.adapter_name}（已注册: {[a.name for a in registry.all_adapters()]}）")
    status = {}
    fail = False
    for a in adapters:
        ok, msg = a.available()
        errs = a.self_check() if ok else [msg]
        passed = ok and not errs
        status[a.name] = "pass" if passed else "fail"
        print(f"  [{'✓' if passed else '✗'}] {a.name} ({a.capability}) {msg}" + (f" 自检:{errs}" if errs else ""))
        fail |= not passed
    registry.save_provenance(extra_status=status)
    print(f"[verify] {'ALL PASS' if not fail else 'FAILED'} → {registry.REG_FILE}")
    sys.exit(1 if fail else 0)


def cmd_list(args) -> None:
    for a in registry.all_adapters():
        ok, msg = a.available()
        print(f"{a.name:<24} {a.capability:<18} {a.absorb_method:<12} {'✓' if ok else '✗'} {msg}")


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("scan")
    p.add_argument("project_dir")

    p = sub.add_parser("scaffold")
    p.add_argument("capability")
    p.add_argument("name")
    p.add_argument("source")
    p.add_argument("--desc", default="")

    p = sub.add_parser("verify")
    p.add_argument("adapter_name", nargs="?")

    p = sub.add_parser("list")
    args = ap.parse_args()
    {"scan": cmd_scan, "scaffold": cmd_scaffold,
     "verify": cmd_verify, "list": cmd_list}[args.cmd](args)


if __name__ == "__main__":
    main()
