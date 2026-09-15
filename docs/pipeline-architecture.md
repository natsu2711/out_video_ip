# 管线全景：业务逻辑链路 / 数据结构 / 依赖

> 一句话：**文稿进 → 七个环节流水 → 成片出**。每个环节有 JSON Schema 契约、
> 机器验收闸、多种实现（模型可降级）、单环可重跑（--force）。

## 业务逻辑链路

```
【输入】你提供：文稿.md（唯一必填输入）+ 可选：项目名/标题
   │
   ▼
S0 初始化 (s0_init.py)
   │  建 job 目录、project.json（画布/音色/配色 token）、state.json 状态机
   ▼
S1 脚本结构化 (s1_script.py)
   │  分句 + 节拍标注 + 数字转汉字          【解法: LLM链 → 规则兜底】
   ▼                                    【闸: script.schema.json】
S2 配音 + 字级时间戳 (s2_tts.py → s2_align.py)
   │  index-tts 本地合成 + CPU 字级对齐     【解法: FireRed ASR / faster-whisper】
   ▼                                    【闸: timing.schema + 对齐质检(match<0.9 标红)】
S3 分镜 (s3_storyboard.py → card_lint → s3_check → s3_table)
   │  分组 → 配卡 → 装配 → 验收重排        【解法: LLM逐镜配卡+移植卡 / 纯规则】
   │                                    【闸: schema + 反单调lint + card_lint + 节奏铁律】
   │                                    【闸⏸人工: 审阅 docs/storyboard-table.md】
   ▼
S4 资产 (s4_manifest.py → s4b_image_briefs.py)
   │  IP形象登记 + 图像任务单              【解法: adapter 注册表（画风配方包）】
   ▼
S5 渲染 (s5_render.py，Remotion)
   │  17 镜逐镜渲染 → concat               【确定性：零随机数，每镜独立进程】
   │  全局 Ken Burns 相机 + 微光漂移 + 卡拉OK字幕 + 漂移微光
   ▼                                    【闸⏸人工: 预览样片】
S6 混音 + 机器验收 (s6_mix.py → s6_qa.py)
   │  显式流映射混 VO（+可选BGM闪避）       【7条机器闸，任一失败 exit 1】
   ▼
【输出】out/video-final.mp4 + qa/report.json + contact-grid.jpg（人工目检）
```

推进方式：`scripts/pipeline.py run jobs/<job>`（状态机只进不退，产物校验通过才推进）；
单环重跑：`pipeline.py run <job> --stage s3 --force`。

## 每环输入输出数据结构

### S1 → script.json（schemas/script.schema.json）
```json
{"version": "1.0", "job_id": "...", "source": "story.md",
 "meta": {"hook": "开场钩子", "closing": "收尾", "char_count": 412, "est_duration_sec": 91.5},
 "segments": [{"id": "seg001", "text": "口播句（数字一律汉字）",
               "beat": "hook|point|step|case|contrast|cta",
               "visual_hint": "scene|graphic|quote|real"}]}
```

### S2 → audio/vo.wav + timing.json（schemas/timing.schema.json）
```json
{"version": "1.0", "audio": "audio/vo.wav", "duration_ms": 103492, "backend": "firered",
 "segments": [{"id": "t000", "start_ms": 0, "end_ms": 7200, "text": "句子", "match": 1.0, "ok": true,
               "words": [{"text": "大", "start_ms": 0, "end_ms": 380}]}],
 "invariants": {"ends_within_ms": 40}}
```

### S3 → storyboard.json（schemas/storyboard.schema.json）
```json
{"version": "1.0", "job_id": "...",
 "shots": [{"id": "S001",
   "time": {"start_ms": 0, "end_ms": 7200, "seg_ids": ["t000"]},
   "vo": "这镜的口播原文",
   "roll": "A|B",                       // A=IP形象出镜, B=图文卡
   "b_type": "text|graphic|real",
   "view_angle": "host|protagonist|pov|supporting",
   "intent": "≤20字意图", "visual": "≤40字画面描述",
   "motion": ["画面节拍1", "节拍2"],      // 每镜≥1（反死板闸）
   "transition_in": "cut|push-through|whip-pan",
   "recipe_ref": "TitleCard|QuoteCard|ARollScene|StepsCard|TransformCard|ListGrid|EndingCard|card:<talkcraft卡名>",
   "assets_needed": [], "status": "pending"}],
 "rhythm_check": {"a_b_ratio": [5, 13]}}
```
配方注册表：自研 7 配方（render-engine/src/shots/）+ 移植卡 79 张
（render-engine/src/cards/registry.json，63 张可自动灌文案，card_lint 闸守门）。

### S4 → assets/manifest.json + assets/image_briefs.json
```json
// manifest.json（S5 渲染直接消费）
{"ip_images": {"three_view": "public/ip/ip-three-view.png"}, "bgm": null}
// image_briefs.json（S4B 产出，喂生图模型的人工/自动任务单）
{"version": "1.0", "briefs": [{"shot_id": "S002", "adapter": "ian-xiaohei",
  "style": "xiaohei-default", "aspect": "16:9", "prompt": "完整生图prompt",
  "target_path": "assets/broll/S002.png", "notes": "溯源"}]}
```
图生成后放 target_path → 重跑 S4 登记 → S5 消费。**不生成图管线也完整**（B-roll 走文字卡/移植卡）。

### S5 → render/segments/S00X.mp4 → out/video-silent.mp4
无声成片（H.264 1080×1920@30，时长 = timing.duration_ms ±800ms 闸）。

### S6 → out/video-final.mp4 + qa/report.json
```json
{"video": "...", "duration_s": 103.5,
 "rules": [{"rule": "R1-freeze", "pass": true, "value": 3.43, "expect": "总冻结≤5s"},
           {"rule": "R2-audio-mean", "pass": true, "value": -17.4, "expect": ">-35dB"},
           "...共7条"],
 "freeze_seconds": 3.43, "passed": true, "contact_sheet": "qa/contact-grid.jpg"}
```
7 条闸：冻结段≤5s / 全片响度>-35dB / max>-15dB / 每30s窗口响度 / 时长偏差<800ms /
A-roll图存在(亮像素≥3%) / 字幕存在(字幕带≥0.15%)。

### 状态机 → state.json
`{"stages": {"s0": {"status": "done|running|blocked|failed|pending", "ts", "note"}}, ...}`
人工闸门：s3（审阅编排表）、s5（审阅样片）——`pipeline.py gate s3 --approve <job>`。

## 依赖清单

| 依赖 | 用在 | 缺失时 |
|---|---|---|
| Python .venv（jsonschema/numpy/Pillow） | 全部管线 | 必需 |
| index-tts（外部 venv + 音色参考 examples/voice_02.wav） | S2 配音 | 必需（本地免费）；换 TTS = 换 s2_tts 实现 |
| FireRed ASR 模型（~767MB，~/.cache）或 faster-whisper（460MB 自动下） | S2 对齐 | 二选一，本地 CPU |
| Node 20 + render-engine/node_modules（Remotion 4）+ Headless Chrome | S5 | 必需（确定性渲染） |
| Ollama + qwen3.5:9b-q4_K_M（本地免费） | S1/S3 的 LLM 解法 | 可选：链自动降级到规则兜底，管线不阻塞 |
| 高质量模型 API（GLM/DeepSeek 等，OpenAI 兼容） | S1/S3 提质 | 可选：PIPELINE_LLM_CHAIN 第一级；token 用完改环境变量即切 |
| 吸收源项目（hand-drawn-styles / ian-xiaohei / video-shotcraft / video-talkcraft） | S3 配方卡 / S4B 画风 | 可选：adapter available()=false 自动跳过 |
| 生图模型（GPT-Image-2 / ComfyUI） | S4B 任务单的消费方 | 可选：不生图走文字卡路径 |

## 模型降级链（一环境变量切换）

```bash
export PIPELINE_LLM_CHAIN="openai:https://open.bigmodel.cn/api/paas/v4|glm-4.7|ZHIPU_KEY -> ollama:qwen3.5:9b-q4_K_M -> none"
```
逐级自动降级；输出一律过 schema+业务校验+错误喂回修复（≤2轮）；全部失败走纯规则（实测全链通过）。

## 质量下限由谁保证（与模型强弱解耦）

1. 每环 schema 校验（坏数据不推进）
2. S3 反单调 lint + card_lint + 节奏铁律（违规确定性重排，不赌模型）
3. S6 七条机器闸（静音/冻结/空图/字幕丢失流不出去）
4. 确定性渲染 + 状态机（同输入同产物，单环可复算重跑）

## 三轴正交分镜模型（A/B/C-roll 分层组合，2026-09-03 定稿）

```
主体层（谁占画面·讲什么）      呈现层（怎么出现·动效语法）      氛围层（C-roll·环境）
├─ A-roll: IP/主持人          ├─ slam_in   砸入(带回弹)      ├─ particles  粒子
│   叙事主体                  ├─ wipe_mask 蒙版擦除          ├─ light_sweep 扫光
├─ B-roll: 图文卡/移植卡/     ├─ rise_fade 上升浮现          ├─ grain      颗粒
│   真实素材(自动升级)        └─ blur_focus 虚实聚焦          ├─ vignette   暗角
└─ 相机: 推拉方向可每镜覆盖                                   └─ tint_warm/cool 色调
        （缺省奇偶镜轮换）
```
三轴自由组合 = 画面节奏。纪律（机器闸）：呈现 ≤1 种/镜；C-roll ≤2 层；A-roll ≤1 层；
配方变更时呈现+叠层由 assign_presentation/assign_overlay 单一来源同步重算（防层残留）。
B-roll 真实素材：S4C 搜索下载（stock-footage adapter）→ manifest 登记 → RealFootage 自动升级。
