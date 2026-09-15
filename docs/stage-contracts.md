# Stage 契约适配壳映射表（第一张工单）

> 路线：**契约先行，包装现有实现**。每个 Stage 包上 `validate_input → execute → validate_output` 壳，
> 内部实现一行不动；壳子必须满足"可独立运行、可独立替换、只暴露 Contract"。
> 本表 = 每个壳的验收标准。影子编译器判负时，壳子对卡片管线同样保值。

## 统一 Stage 返回结构（全部壳的输出协议）

```json
{
  "stage": "S3",
  "status": "ok | warning | failed",
  "input_fingerprint": "sha256:16",
  "output_fingerprint": "sha256:16",
  "warnings": [],
  "errors": [{"code": "...", "severity": "warning|error", "recoverable": true, "fallback": "..."}],
  "data": {}
}
```

## 依赖指纹（已落地 ✅ 2026-09-09）

- `pipeline/state.py`: `record_completion()`（done 时记录产物+输入 SHA-256:16）、`stage_fresh()`（fresh/stale 判定）
- `scripts/pipeline.py`: run 前查上游 stale → 拒绝并指出变更文件（`--force` 豁免）；status 输出 freshness 表
- **有意的偏差**：不做 stale 下游自动删除（破坏性操作），改为拒绝+指路
- 待补：`git_commit`、模型指纹（见 S1 行）

## S0 Project

| 项 | 现状 | 契约 |
|---|---|---|
| 现有入口 | `s0_init.py:main()` | `build_project(story_path, config_path) -> Project` |
| 输入 | story.md + CLI 参数 | story.md + project.yaml（未来） |
| 输出 | project.json | project.json（不变） |
| validate | require("project") | 不变 |
| 缺口 | 无 fingerprint（run_stage 已代记） | 壳内补 input_fingerprint |
| 禁止事项 | — | 不产镜头/卡片/素材 |

## S1 Semantic Parser（未来 Semantic IR 宿主）

| 项 | 现状 | 契约 |
|---|---|---|
| 现有入口 | `s1_script.py:main()`（llm_segments/rule_segments） | `parse_semantics(project, source_text) -> SemanticDocument` |
| 输出 | script.json | script.json（= **narration 层**，朗读文本+protected_tokens）+ 未来 `semantic_ir.json`（影子字段） |
| validate | require("script") | 不变 |
| 已有 | ✅ 数字豁免 protected_tokens（2026-09-09） | protected token 清单随契约下传 S2 |
| 缺口 | **模型指纹**：llm.py 记录 model_name+quantization+ggup 文件名+sha256 前 16 位（轻量化，不做全量 weights hash） | semantic_ir 字段禁出现任何视觉实现词（card/layout/font/color/animation/camera） |
| 关键边界 | — | script.json 是"朗读层"，semantic_ir 是"理解层"，二者都由 S1 产但不混字段 |

## S2 Timing

| 项 | 现状 | 契约 |
|---|---|---|
| 现有入口 | `s2_align.py:run_align/convert/check` | `build_timing(script, audio_path) -> TimingDocument` |
| 输出 | timing.json | + 每段 `align_confidence(high/medium/low)`、`align_score` ✅ 已落地 |
| 已有 | ✅ protected token 碎片合并（merge_protected）✅ `audio/align-review.csv` 人工复核入口 | 受保护 token 跨度>2s → 强降 low |
| 下游消费 | KaraokeLine 三级降级 ✅（high 逐字/medium 词块/low 整句） | 下游**不得重算时间**（含 S5/S6/S3 锚点） |
| 错误契约 | 现为 fail-fast exit 1 | 迁移为 `{code: ALIGNMENT_LOW_CONFIDENCE, severity: warning, recoverable: true, fallback: sentence_mode}` |

## S3 Visual Planner（未来 Visual IR 宿主）

| 项 | 现状 | 契约 |
|---|---|---|
| 现有入口 | `s3_storyboard.py:assemble/rebalance`（四层） | `plan_visuals(semantic, timing, project) -> VisualDocument` |
| 输出 | storyboard.json | + 未来 `visual_ir.json`（影子字段：relation/entities/spatial_relation/temporal_relation/information_hierarchy/emphasis/rhythm/abstraction） |
| LLM 职责 | 现为"选卡+写画面指令" | 收窄为"只产 Visual IR"；选卡由 Compiler 接管（影子实验胜出后） |
| lint | lint.py 反单调（配方枚举比较） | 拆两层：schema 层（plan 结构）+ 原语层（bounds/collision 取代"≤16字"卡特有规则）；迁移期两套并存，非 Compiler 镜头沿用配方铁律 |
| 降级 | 关键词兜底配卡 | 改"保底王"：beat 固定保底结构 + 参数确定性变化（shot_index % N），降级记 `degraded_groups` |

## S4 Compiler + Asset Planner（拆两职）

| 项 | 现状 | 契约 |
|---|---|---|
| 现有入口 | （无 Compiler）s4_manifest/s4b/s4c/s4d | `compile_visual(visual_ir, project, theme, config) -> VisualPlan`（纯函数，禁网络/LLM/随机态） |
| Visual Plan | — | shots[]{layout, layers, typography, motion, camera, emphasis, assets_needed}；**同输入 100 次 → visual_plan.json 逐字节一致**（渲染像素一致性归 pixelmatch 容差，不承诺字节相等） |
| Asset Planner | s4 系列脚本 | `plan_assets(visual_plan, asset_library) -> manifest`；降级梯度：本地素材→本地生成→外部 API（最后） |
| 原语接口 | — | `validate(props)/compile(props)/estimate_bounds(props)/fingerprint(props)` |
| 增长规则 | 加卡 | **新信息结构→加 Compiler Rule；新视觉原语→加 Primitive；只是新组合→不许加卡** |

## S5 Render

| 项 | 现状 | 契约 |
|---|---|---|
| 现有入口 | `s5_render.py:render_one/concat_segments` | `render(visual_plan, manifest, timing, project) -> RenderResult` |
| 铁律 | — | Renderer 只执行：禁改 timing/语义结构/visual plan；单镜重渲保持（已支持） |

## S6 QA

| 项 | 现状 | 契约 |
|---|---|---|
| 现有入口 | `s6_qa.py`（+playwright 9 规则）/ `s6_sfx_check.py` | `run_qa(project, semantic, timing, visual, plan, manifest, video) -> QAReport` |
| 三层指标 | 工程正确性 ✅（schema/lint/asset/时间轴/渲染成功） | 补：内容正确性（semantic coverage/anchor coverage/visual-text relevance）+ 视觉质量（repetition/density/readability/layer collision） |
| 核心指标观 | — | **Semantic Match > Visual Novelty**：语义变化→视觉变化的相关性，而非"配方多样性熵" |

## 实施顺序（已按依赖排序）

1. ✅ #3 数字豁免（S1 扫描 + S2 合并）— 2026-09-09
2. ✅ #1 对齐置信度分级 + 字幕三级降级 — 2026-09-09
3. ✅ #4 依赖指纹（record_completion/stage_fresh/run 拒绝 stale/status 表）— 2026-09-09
4. ✅ #5 保底王降级（BEAT_FALLBACK 同族变体轮换 + degraded_groups + 编排表 ⚠️；顺带修复 rebalance 格位公式低估 bug）— 2026-09-09
5. ✅ #6 卡片视觉回归快照（card_snapshot.py + CardSnapshot 组合；PIL diff>2% 告警）— 2026-09-09
6. ✅ #2 跑题排除器骨架（s4_relevance_check.py；CLIP 后端自动探测，无模型非阻塞降级；20 组标注校准入口 --calibrate）— 2026-09-09
7. ✅ 影子编译器骨架（schemas/visual_ir.schema.json + pipeline/visual_compiler.py 纯函数 + S3 影子字段 ir/compiler_plan + ablation compiler_on 变体含确定性自检）— 2026-09-09；LLM 版 IR 产出与 8 篇盲评实验待启动
