"""吸收框架基类：外部项目/ skill 的能力抽象成四类 adapter（环节多解法的"解法"实体）。

能力类型（capability）：
  image_prompt     生图提示词（画风配方/模板库）→ 产出单条 prompt 文本
  recipe_knowledge 配方知识库（镜头卡方法论/动效词汇）→ 产出结构化索引
  script_structure 文稿结构化（S1 解法）        → 产出 script.json segments
  chart_render     图表渲染（S4 解法，外部二进制如 manim）→ 产出视频/图片资产

每个 adapter 必须声明：
  name             唯一名
  capability       上述四类之一
  source_project   来源项目绝对路径或 URL（provenance，可溯源）
  absorb_method    吸收方式：vendor(代码移植) / codemod(改造移植) / prompt_pack(提示词配方) / api(外部调用)

契约：
  available() -> (bool, str)   依赖是否就绪（源目录在/二进制在/数据可解析）
  produce(...)                 按 capability 的约定产出（见各子类 docstring）
  self_check() -> list[str]    契约自检（absorb.py verify 调用，空 = 过）
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class Adapter(ABC):
    name: str = ""
    capability: str = ""
    source_project: str = ""
    absorb_method: str = ""
    description: str = ""

    @abstractmethod
    def available(self) -> tuple[bool, str]:
        """依赖就绪检查（源存在/二进制可用）。"""

    @abstractmethod
    def self_check(self) -> list[str]:
        """契约自检，返回错误清单（空 = 通过）。"""

    def provenance(self) -> dict:
        return {
            "name": self.name,
            "capability": self.capability,
            "source_project": self.source_project,
            "absorb_method": self.absorb_method,
            "description": self.description,
        }


class ImagePromptAdapter(Adapter):
    """image_prompt 契约：
    produce(shot: dict, style: str | None) -> dict
      {"prompt": str, "style": str, "aspect": "16:9", "notes": str}
    shot 字段：{id, vo, intent, visual, motion, view_angle}"""

    capability = "image_prompt"

    @abstractmethod
    def produce(self, shot: dict, style: str | None = None) -> dict: ...

    @abstractmethod
    def styles(self) -> list[str]:
        """可用画风/模板名列表。"""


class RecipeKnowledgeAdapter(Adapter):
    """recipe_knowledge 契约：
    produce() -> {"cards": [{"slug", "category", "title", "essence"}], "count": int}"""

    capability = "recipe_knowledge"

    @abstractmethod
    def produce(self) -> dict: ...


class ScriptStructureAdapter(Adapter):
    """script_structure 契约：
    produce(text: str) -> {"segments": [{"id", "text", "beat?", "visual_hint?"}]}"""

    capability = "script_structure"

    @abstractmethod
    def produce(self, text: str) -> dict: ...


class ChartRenderAdapter(Adapter):
    """chart_render 契约：
    available() 检测外部渲染器；produce(spec: dict, out: Path) -> Path（视频/图片资产）"""

    capability = "chart_render"

    @abstractmethod
    def produce(self, spec: dict, out: Path): ...


class VideoRenderAdapter(Adapter):
    """video_render 契约：外部视频渲染器（如 whiteboard-animator）。
    available() 检测外部 CLI；produce(spec: dict, out: Path) -> Path
    spec: {"image": Path, "duration_s": float, "audio"?: Path} → 视频资产（进 manifest.broll_videos）"""

    capability = "video_render"

    @abstractmethod
    def produce(self, spec: dict, out: Path): ...
