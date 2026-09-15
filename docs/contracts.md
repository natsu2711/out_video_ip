# 管线数据契约（每层 schema 与替换指引）

> 设计原则拆自 video-talkcraft / video-shotcraft 的稳定性范式：
> **环节化 + 每环有 schema 契约 + 不稳定就加一层 + 模型可降级**。
> 任何一层只要产出满足契约的 JSON，就可被替换（更强模型 / 免费模型 / 纯规则）。

## 总览

```
文稿 story.md
  └→ S1 s1_script.py      → script.json    （分句+标注；LLM 可选，规则兜底）
       └→ S2 s2_tts.py + s2_align.py → audio/vo.wav + timing.json（本机 CPU，零模型依赖）
            └→ S3 s3_storyboard.py → storyboard.json（四层：分组→配卡→装配→验收重排）
                 └→ S4 s4_manifest.py → assets/manifest.json
                      └→ S5 s5_render.py → render/segments/*.mp4 → out/video-silent.mp4（Remotion，确定性）
                           └→ S6 s6_mix.py + s6_qa.py → out/video-final.mp4 + qa/report.json（7 条机器闸）
```

主控：`scripts/pipeline.py run <job> [--stage sX] [--force]`（状态机：产物校验通过才推进，只进不退）

## 模型降级链（便宜/免费/本地照样出片）

`pipeline/llm.py`，环境变量 `PIPELINE_LLM_CHAIN`，"->" 分隔，逐级降级：

```bash
# 强模型（GLM 示例）→ 免费/本地 ollama → 纯规则兜底
export PIPELINE_LLM_CHAIN="openai:https://open.bigmodel.cn/api/paas/v4|glm-4.7|ZHIPU_KEY -> ollama:qwen3.5:9b-q4_K_M -> none"
# 只有本地：直接用默认链（同下行）
export PIPELINE_LLM_CHAIN="ollama:qwen3.5:q4_K_M -> none"
```

弱模型稳定的三道保险（都在 llm.py 里）：
1. **小任务化**：S3 逐镜头调用，每次只选 1 个配方+写 3 条节拍——输出小，8B 模型也稳
2. **修复循环**：输出过不了 schema/业务校验 → 错误清单+原文喂回去修（≤2 轮）
3. **单点降级**：某一镜 LLM 失败只降级那一镜（规则配卡），不拖垮全片；全链挂走 `pipeline/fallback.py` 纯规则

实测（qwen3.5:9b 本地，2026-09-03）：S3 全片 17 镜 ~2 分钟，15/17 镜模型配卡成功、
schema+反单调 lint 全过、下游渲染直接消费。`PIPELINE_LLM_CHAIN=none` 纯规则路径同样全过（确定性）。

## 各层契约

### script.json（S1 产出，schemas/script.schema.json）
```json
{"version, job_id, source",
 "meta": {"hook", "closing", "char_count", "est_duration_sec"},
 "segments": [{"id": "seg001", "text": "口播句（数字一律汉字！）",
               "beat": "hook|point|step|case|contrast|cta",
               "visual_hint": "scene|graphic|quote|real"}]}
```
**替换**：任何分句/标注器，产出此结构即可。数字转汉字是铁律
（S2 时间戳按文本逐字锚定，「197747」无法与读音对位）。

### timing.json（S2 产出，schemas/timing.schema.json）
`segments[]: {id, start_ms, end_ms, text, match, ok, words[]}`——CPU 字级对齐。
**替换**：任何对齐工具（FireRed ASR / faster-whisper）产出此结构即可（talkcraft 同款做法）。

### storyboard.json（S3 产出，schemas/storyboard.schema.json）
```json
{"shots": [{"id": "S001", "time": {"start_ms, end_ms, seg_ids"}, "vo",
            "roll": "A|B", "b_type": "text|graphic|real", "view_angle": "host|protagonist|pov|supporting",
            "intent": "≤20字", "visual": "≤40字", "motion": ["节拍", "..."],
            "transition_in", "recipe_ref": "短名", "assets_needed", "status"}],
 "rhythm_check": {"a_b_ratio": [A数, B数]}}
```
`recipe_ref` 短名 enum：TitleCard / QuoteCard / ARollScene / StepsCard / TransformCard / ListGrid / EndingCard
（渲染端解析为 `local:shots/<名>`；新增配方 = 写 tsx + 注册 + 填 enum 三步）。

**S3 内部四层（每层可单独换）**：
| 层 | 实现 | 可替换为 |
|---|---|---|
| L1 分组 | 纯规则：3~8s 语义分组 | 任何分组器 |
| L2 配卡 | 逐镜 LLM 小任务 | 更强模型 / 纯规则（fallback.py 关键词+轮换） |
| L3 装配 | 纯规则：A/B 策略、视角轮换、首尾镜 | 策略参数可调 |
| L4 验收 | schema + lint + 确定性一次收敛重排 | 加新规则到 lint.py |

### 反单调闸（pipeline/lint.py，全确定性）
- 连续同配方 ≤2；同配方全片 ≤ ⌈n/4⌉（结构卡不计）
- A-roll 间隔 ≥2 镜（固定格点落位，间距数学保证）；连续同 roll ≤3
- 每镜 motion ≥1（talkcraft：每句都要有活的画面响应）
- 首镜必须 TitleCard、末镜必须 EndingCard
- 违规不重试 LLM，走**一次收敛重排**（rebalance：LLM 文案保留、只换配方标签）

### S6 QA 七条机器闸（scripts/s6_qa.py）
冻结段≤5s / 全片响度 / 分窗响度(30s) / 时长对齐 / A-roll 图存在 / 字幕存在 / freezedetect 口径见文档。
任一失败 exit 1，产物不出闸。

## 新文稿 → 成片（标准流程）

```bash
.venv/bin/python scripts/s0_init.py jobs <slug> "<标题>" --story <文稿.md>
.venv/bin/python scripts/pipeline.py run jobs/<slug>          # S1→S6 顺序推进，闸门自动停
# 闸门放行：pipeline.py gate s3 --approve jobs/<slug> 等
```
中途改任何一层：改完 `pipeline.py run <job> --stage s3 --force` 单环重跑，其余环不动。

## 配方卡吸收层（2026-09-03 晚新增）

79 张 video-talkcraft 动效卡已全部移植进 `render-engine/src/cards/`（card-<slug>.tsx）。

**吸收机制**（scripts/import_cards.py，三步 codemod）：
1. 内容注入点：卡内文案常量与 JSX 中文叶子文本改为 `__INJ__.X ?? 原值`——动效保留，内容换成我们的分镜文案
2. 惰性加载：webpack require.context，卡模块只在被选中时求值
3. registry.json：slug / 时长 / 内容注入键与元素数 / 接线等级

**渲染链路**：S3 配卡（LLM 优先选 + 确定性卡位注入双保险）→ card_lint 机器闸
（卡文件存在/在册/已接线/时长）→ CardHost 宿主（960×540 横版卡适配竖屏：居中 16:9 画中画 +
播完 Freeze 定格末帧）→ setCardContent 在卡模块求值前灌入分镜文案。

**接线等级**（诚实记录）：
- injectable 63 张：文案自动灌入（TEXT 注入点），立即可用
- raw 14 张：纯图形卡（gooey-morph/pencil-sketch 等无中文叶文本），动效可参考，禁止进自动分镜（card_lint L3 挡）
- ROWS/STEPS 型 6 张：内容常量结构因卡而异，暂保 demo 结构（TODO：逐卡字段映射）
- 卡时长 > 镜头时长时 Freeze 定格（card_lint 警告提示）

**多样性规则**：卡与自研配方同池参与反单调闸（连续同配方≤2、同配方≤⌈n/4⌉）；
卡位确定性注入（中段 i%6∈{0,3} 且非 A-roll 格点）保证不赌模型也有卡可用。

## 环节多解法注册表现状

| 环节 | 解法 A | 解法 B | 兜底 | 选择方式 |
|---|---|---|---|---|
| S1 分句标注 | LLM 链 | 规则分句 | — | 链自动降级 |
| S2 时间戳 | FireRed ASR | faster-whisper | — | backend 参数 |
| S3 配方 | 自研 7 配方 | 移植卡 63 张 | 规则关键词+卡位轮换 | LLM 优先卡 + 确定性卡位 |
| S4 图像 | guizang 通道 | （可插：ian-xiaohei/lieflat/baoyu） | 占位图 | manifest 路由 |
| S6 验收 | 7 条机器闸 | 人工抽帧目检 | — | exit code 卡闸 |
