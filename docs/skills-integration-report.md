# 生图 Skills 功能资产集成报告

## 已集成功能

### 高优先级（已完成）

| 功能资产 | 状态 | 文件 |
|---|---|---|
| **主题色预设系统**（10 套主题） | ✅ | `schemas/project.schema.json` + `pipeline/theme_tokens.py` + `scripts/apply_theme.py` |
| **校验脚本扩展**（Playwright 9 条规则） | ✅ | `scripts/s6_qa_playwright.py` + `scripts/s6_qa.py`（集成） |

### 中优先级（已完成）

| 功能资产 | 状态 | 文件 |
|---|---|---|
| **6 个版式骨架组件** | ✅ | `render-engine/src/shots/`<br/>- `ImageLedCover.tsx`（超大标题图文穿插）<br/>- `PipelineSteps.tsx`（流程步骤）<br/>- `CompareCardEnhanced.tsx`（Before/After 对比）<br/>- `KPI_Tower.tsx`（KPI 柱状塔）<br/>- `MatrixHero.tsx`（3x3 矩阵网格）<br/>- `MapCard.tsx`（地图组件，含 pin + 连线） |
| **截图美化工具** | ✅ | `scripts/enhance_screenshot.py`（调用 guizang WebP 背景素材） |

### 组件注册

所有新组件已注册到 `render-engine/src/compositions/ShotComposition.tsx` 的 `SHOT_COMPONENTS`，可在 storyboard.json 中通过 `recipe_ref` 调用：

```json
{
  "recipe_ref": "local:shots/ImageLedCover",
  "visual": "\"核心竞争力\"",
  "motion": []
}
```

## 使用示例

### 1. 主题色应用

```bash
# 为现有 job 应用主题色
python scripts/apply_theme.py jobs/2026-0902-fake-effort

# 新建 job 时指定主题（在 project.json 中修改）
"style": {"theme": "indigo-porcelain"}
```

### 2. 截图美化

```bash
# 将截图美化（默认 iKB 主题）
python scripts/enhance_screenshot.py input.png output.png --style ikb

# 支持的主题：ink-classic, indigo-porcelain, forest-ink, kraft-paper, dune, ikb, lemon, lemon-green, safety-orange, midnight-ink
```

### 3. 调用新版式组件

在 storyboard.json 中为镜头指定 `recipe_ref`：

```json
{
  "shot_id": "S001",
  "time": {"start_ms": 0, "end_ms": 3000},
  "type": "b_roll",
  "vo": "核心指标提升了 300%",
  "recipe_ref": "local:shots/KPI_Tower",
  "visual": "300%",
  "motion": ["100", "200", "300", "400"]
}
```

## 未采纳功能（按要求排除）

- ❌ 三闸门审批协议
- ❌ 双色 Ink 系统
- ❌ 认知锚点可视化
- ❌ 19 种手绘风格

## 外部技能引用路径

所有外部技能均通过**路径引用**访问，未复制文件：

| 外部技能 | 引用路径 |
|---|---|
| guizang-social-card-skill | `/Users/bainazi/Documents/outtt/2other_pic/guizang-social-card-skill/` |
| mono-color-skill | `/Users/bainazi/Documents/outtt/2other_pic/mono-color-skill/` |
| ian-xiaohei-illustrations | `/Users/bainazi/Documents/outtt/2other_pic/ian-xiaohei-illustrations/` |
| Punk-Skill | `/Users/bainazi/Documents/outtt/2other_pic/Punk-Skill/` |
| gbro-collage-broll | `/Users/bainazi/Documents/outtt/1other_video/gbro-collage-broll/` |
| hand-drawn-styles | `/Users/bainazi/Documents/outtt/1other_video/hand-drawn-styles/` |