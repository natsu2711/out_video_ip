"""archify 吸收（api 吸收：外部 Node CLI，检测到才路由，不 vendor 代码）。
来源：/Users/bainazi/Documents/outtt/other/2other_pic/archify
能力：typed JSON IR → 确定性架构图/流程图/时序图 HTML →（配合 .venv playwright 截图）→ PNG
     → assets/broll/{shot}.png → S5 B-roll 消费。适合科技/架构/流程讲解镜头。
依赖：node + 本项目路径（absorb_method=api，源目录即可用，无需安装）。
IR 生成：由 LLM 任务单产出（visual_hint=graphic 且 intent 含架构/流程/时序语义时建议路由）。"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from .base import ChartRenderAdapter

SRC = Path("/Users/bainazi/Documents/outtt/other/2other_pic/archify/archify")
TYPES = ("architecture", "workflow", "sequence", "dataflow", "lifecycle")


class ArchifyAdapter(ChartRenderAdapter):
    name = "archify"
    source_project = str(SRC.parent)
    absorb_method = "api"
    description = "架构/流程/时序/数据流/生命周期图渲染（JSON IR → HTML → PNG，确定性布局）"

    def available(self) -> tuple[bool, str]:
        cli = SRC / "bin" / "archify.mjs"
        if not cli.exists():
            return False, f"CLI 不存在: {cli}"
        if not shutil.which("node"):
            return False, "node 不在 PATH"
        return True, f"node + {cli.name}"

    def produce(self, spec: dict, out: Path) -> Path:
        """spec: {"type": "architecture|workflow|...", "ir": {...}} → out.png（playwright 截图）"""
        dtype = spec.get("type", "architecture")
        if dtype not in TYPES:
            raise ValueError(f"archify 类型须为 {TYPES}，得到 {dtype}")
        workdir = out.parent
        workdir.mkdir(parents=True, exist_ok=True)
        ir_path = workdir / f"{out.stem}.archify.json"
        ir_path.write_text(json.dumps(spec["ir"], ensure_ascii=False, indent=1), "utf-8")
        html_path = workdir / f"{out.stem}.archify.html"
        subprocess.run(
            ["node", str(SRC / "bin" / "archify.mjs"), "render", dtype, str(ir_path), str(html_path)],
            check=True, capture_output=True, timeout=120,
        )
        if not html_path.exists():
            raise RuntimeError(f"archify 未产出 HTML: {html_path}")
        # HTML → PNG（复用 s6_qa_playwright 同栈）
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1920, "height": 1080})
            page.goto(html_path.as_uri())
            page.wait_for_timeout(1500)  # 等有限动效落定
            page.screenshot(path=str(out), full_page=False)
            browser.close()
        if not out.exists() or out.stat().st_size < 10_000:
            raise RuntimeError(f"截图无效: {out}")
        return out

    def self_check(self) -> list[str]:
        ok, msg = self.available()
        return [] if ok else [msg]


ADAPTER = ArchifyAdapter()
