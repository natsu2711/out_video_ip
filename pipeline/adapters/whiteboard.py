"""whiteboard-animator 吸收（api 吸收：外部 CLI，检测到安装才路由，不 vendor 代码）。
来源：/Users/bainazi/Documents/outtt/other/1other_video/whiteboard-animator
能力：白板风格图 → 手绘动画视频（逐字书写/描边/笔刷填色），CPU 本地，零 API。
安装：.venv/bin/pip install whiteboard-animator
链路：s4b 生图任务单 → assets/broll/{shot}.png → 本 adapter 产出 mp4
     → manifest.broll_videos → S5 RealFootage 自动消费（s4d_whiteboard.py 驱动）。"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from .base import VideoRenderAdapter

SRC = "/Users/bainazi/Documents/outtt/other/1other_video/whiteboard-animator"


def _exe() -> str:
    return shutil.which("whiteboard-animate") or str(Path(sys.executable).parent / "whiteboard-animate")


class WhiteboardAdapter(VideoRenderAdapter):
    name = "whiteboard-animator"
    source_project = SRC
    absorb_method = "api"
    description = "白板图→手绘动画视频：逐字书写/描边/笔刷填色（外部 CLI whiteboard-animate，CPU 本地）"

    def available(self) -> tuple[bool, str]:
        if Path(_exe()).exists():
            return True, _exe()
        return False, "未安装（.venv/bin/pip install whiteboard-animator）"

    def produce(self, spec: dict, out: Path) -> Path:
        img = Path(spec["image"])
        if not img.exists():
            raise FileNotFoundError(f"源图不存在: {img}")
        dur = max(2.0, float(spec.get("duration_s", 6.0)))
        out.parent.mkdir(parents=True, exist_ok=True)
        cmd = [str(Path(_exe())), str(img), "--duration", f"{dur:.1f}", "-o", str(out), "--quality", "medium"]
        if spec.get("audio"):
            cmd += ["--audio", str(spec["audio"])]
        subprocess.run(cmd, check=True, capture_output=True, timeout=900)
        if not out.exists() or out.stat().st_size < 10_000:
            raise RuntimeError(f"whiteboard-animate 无有效输出: {out}")
        return out

    def self_check(self) -> list[str]:
        ok, msg = self.available()
        return [] if ok else [msg]


ADAPTER = WhiteboardAdapter()
