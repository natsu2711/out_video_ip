# OUTVIDEO-IP 项目完整文档

> 本地自动化视频生产工作流 · 版本 2026-09-09
> 输入故事脚本 → 输出成片 + QA 报告，零外部 API 默认（除本地工具），全程可离线出片。
> 操作命令速查见 `docs/OPERATIONS.md`；本文档是完整的项目说明书。

---

## 1. 项目定位与设计哲学

**做什么**：把一篇故事/解说文稿，自动变成一条有配音、字幕、编排、动效、QA 报告的成片视频。

**四条设计铁律**（全部来自实测踩坑）：

1. **单一时间真相源**：所有时间坐标只从 `timing.json` 派生（S2 对齐产物），任何组件不得自造时间。
2. **白名单 + 确定性轮换**：每个设计决策（配卡/叠层/呈现语法/氛围色）都是"白名单内按索引轮换"，禁止无约束即兴——LLM 产出也要过白名单校验。同输入必同输出，可复算可回归。
3. **不稳定就加一层**：LLM 链式降级（强模型→免费 API→本地 ollama→规则兜底）；单组失败只降级该组，不拖垮全片。
4. **答案做成断言**：preflight 渲前断言、lint 节奏铁律、QA 机器验收——文档里写的规范不如做成机器闸。

---

## 2. 系统架构总览

```
story.md（故事文稿）
   ↓ S0  初始化                project.json    画幅/音色/主题/IP/画布
   ↓ S1  脚本结构化            script.json     segments + beat 标注 + 数字转汉字
   ↓ S2  TTS + 字级对齐        timing.json     ★唯一时间真相源（字级 ms）
   ↓ ──── 人工闸门①：编排审阅 ────
   ↓ S3  视觉编排              storyboard.json 分组/配卡/叠层/呈现语法/SFX
   ↓ S4  素材生产              manifest.json   IP姿态池/生图任务/实拍/白板动画/素材视频
   ↓ S5  Remotion 逐镜渲染     render/segments/*.mp4 → concat → video-silent.mp4
   ↓ ──── 人工闸门②：60s 样片 ────
   ↓ S6  混音 + QA             video-final.mp4 + qa/report.json（+playwright 9 规则）
   ↓ S7* 消融实验（可选）      docs/ablation.md 特征开关 × 确定性指标
```

S3 内部又是四层（每层可单独替换/重跑）：

```
L1 分组层（纯规则）：语句段落 → 3~8s 镜头组
L2 配卡层（LLM 逐组小任务，失败单组降级规则配卡）
L3 装配层（纯规则）：A/B 策略、视角轮换、首尾镜、转场、叠层
L4 验收层（schema + lint，违规 → 确定性一次收敛重排 rebalance）
```

---

## 3. 目录结构

```
out_video-ip/
├── schemas/                  # 5 个 JSON 契约（jsonschema Draft7）
│   ├── project.schema.json / script.schema.json / timing.schema.json
│   ├── storyboard.schema.json / assets.schema.json
├── pipeline/                 # 核心库
│   ├── state.py              # 状态机（阶段只进不退，产物校验通过才推进）
│   ├── validate.py           # schema 校验器（阶段入口先校验后执行）
│   ├── llm.py                # LLM 供应商链（小任务化/schema收窄/链式降级）
│   ├── variety.py            # 白名单 + 确定性轮换（BEAT_CARDS/呈现语法/氛围色）
│   ├── lint.py               # storyboard 质量闸（节奏铁律 + 反单调 + 字数闸）
│   ├── fallback.py           # 规则兜底生成器（无模型也出片：关键词配卡/保底轮换）
│   ├── theme_tokens.py       # 46 套主题色预设
│   └── adapters/             # 适配器系统（见 §8）
├── scripts/                  # 阶段执行脚本（CLI）
│   ├── pipeline.py           # 主控：init / run / gate / status
│   ├── s0_init.py            # 初始化 job 目录 + project.json
│   ├── s1_script.py          # 脚本结构化（beat 打标 + 数字转汉字铁律）
│   ├── s2_tts.py             # index-tts 本地配音（整段合成）
│   ├── s2_align.py           # 字级对齐（whisper/FireRedASR2）+ 三项校验
│   ├── s3_storyboard.py      # 四层编排（分组/配卡/装配/验收）
│   ├── s3_check.py           # 节奏自检（连续同类/A-B 配比/时长/motion 锚点）
│   ├── s3_table.py           # 编排表渲染（闸门①审阅用 md）
│   ├── s4_manifest.py        # 素材清单（IP 主图/逐镜场景/姿态池；合并式重跑）
│   ├── s4b_image_briefs.py   # 生图任务单（image_prompt 适配器确定性轮换）
│   ├── s4c_stock_footage.py  # Pexels/Pixabay 素材视频（有 key 全自动/无 key 出任务单）
│   ├── s4d_whiteboard.py     # 白板手绘动画生产（whiteboard-animator 链）
│   ├── s4_capture.py         # 网页实拍（playwright 截图/滚动录屏）
│   ├── s5_render.py          # Remotion 逐镜渲染 + ffmpeg concat
│   ├── s6_mix.py             # VO 混音 + sidechain BGM 闪避 + 响度归一
│   ├── s6_qa.py / s6_qa_playwright.py  # QA（静止帧检测 + 真实渲染 9 规则）
│   ├── s6_sfx_check.py       # 音效锚点/间距检查
│   ├── ablation.py           # 消融实验（特征开关 × 确定性指标）
│   ├── preflight.py          # 渲前断言（任一 FAIL 挡渲染）
│   ├── card_lint.py          # 移植卡体检（存在/注册/接线/时长）
│   ├── import_cards.py       # talkcraft 卡 codemod 移植（生成 registry.json）
│   ├── apply_theme.py        # 主题应用（project.json → palette）
│   └── absorb.py             # 吸收手册 CLI（scan/scaffold/verify）
├── prompts/                  # Agent 执行规则沉淀（s1/s3 prompt）
├── render-engine/            # Remotion 渲染引擎（见 §7）
├── assets/
│   ├── ip/                   # 本人 IP（短发T恤女孩）姿态池（见 §9）
│   └── ip-placeholder/       # 占位 IP（豆芽小人，IP 图缺失时回退）
├── jobs/<日期-slug>/         # 每个 job 一个目录（全部产物落盘于此）
│   ├── project.json / script.json / timing.json / storyboard.json / state.json
│   ├── story.md / audio/vo.wav / assets/manifest.json
│   ├── render/segments/*.mp4 / out/video-final.mp4
│   ├── qa/report.json / docs/（编排表+消融报告）
├── docs/                     # 本文档 + OPERATIONS.md + absorption.md + contracts.md 等
└── .venv/                    # Python 虚拟环境（注意：已搬家，用 python -m pip）
```

---

## 4. 数据契约（5 个 JSON Schema）

阶段入口先校验后执行，校验不过不推进（`pipeline/validate.py`）。

| 契约 | 生产者 | 核心字段 | 消费者 |
|---|---|---|---|
| **project.json** | S0 | `canvas{width,height,fps,ratio}` / `voice{provider,ref_audio,speed}` / `style{theme, a_roll{style_lock,view_angles}, b_roll{palette,font_stack}}` | 全部阶段 |
| **script.json** | S1 | `segments[]{id, text, beat(hook/point/step/case/contrast/quote/cta), visual_hint(scene/real/graphic)}`；meta 记录数字转汉字 | S2/S3 |
| **timing.json** | S2 | `segments[]{id, start_ms, end_ms, text, words[{text,start_ms,end_ms}]}`，字级 ms 时间戳 | S3/S5/S6 ★唯一时间真相源 |
| **storyboard.json** | S3 | `shots[]{id, time{start_ms,end_ms,seg_ids}, vo, roll(A/B), b_type, view_angle, intent, visual, motion[](含锚词), recipe_ref, config{TEXT,CONFIG}, overlay[], presentation, sfx[], assets_needed}` | S4/S5/S6 |
| **manifest.json** | S4 | `ip_images.three_view` / `ip_scenes{镜号:图}` / **`ip_poses{姿态:图}`** / `broll_videos{镜号:{path,provider}}` / `screenshots{}` / bgm / sfx | S5 |

关键流转机制：

- **镜头级重渲染**：S5 逐镜渲独立 mp4，改一镜只重渲一镜；ffmpeg concat 拼接
- **B-roll 自动升级链**：manifest.broll_videos 有素材的 B-roll 镜头 → 渲染时自动切 RealFootage 配方（Ken Burns 慢推覆盖）
- **C-roll 纪律**：叠层与主体正交；任何镜 ≤2 层、A-roll ≤1 层；配方变更自动重算叠层（单一来源 `assign_overlay`）

---

## 5. 状态机与人工闸门

`pipeline/state.py`：阶段 `s0→s6` 只进不退；每阶段产物存在且校验通过才算 done。

状态：`pending → running → done / blocked(闸门) / failed`

| 闸门 | 产物 | 人工动作 |
|---|---|---|
| 闸门① s3 | `docs/storyboard-table.md` 编排表 | 审阅配卡/节奏后 `pipeline.py gate s3 --approve` |
| 闸门② s5 | 60s 样片 | 看样片后 `pipeline.py gate s5 --approve` |

---

## 6. 阶段详解

### S0 初始化（s0_init.py）
建 job 目录 + project.json：画布 1920×1080@30fps、index-tts 音色引用、主题（默认 ink-classic）、A-roll 风格锁。

### S1 脚本结构化（s1_script.py + prompts/s1_script_structure.md）
文稿 → segments：beat 打标（hook/point/step/case/contrast/quote/cta）+ visual_hint。
**数字汉字铁律**：所有阿拉伯数字转汉字（对齐逐字锚定需要），LLM 可选、规则兜底。

### S2 配音 + 对齐（s2_tts.py / s2_align.py）
index-tts 本地整段合成 → faster-whisper 字级对齐 → 三项校验（时长偏差/字数一致/锚词存在）。
产出 `audio/vo.wav` + `timing.json`。对齐失败的段落退回 S1。

### S3 视觉编排（s3_storyboard.py / s3_check.py / s3_table.py）
- **分组**：语句 → 3~8s 镜头组（确定性）
- **配卡**：逐组 LLM 小任务（prompt 内嵌 beat 白名单卡菜单），失败降级 `fallback.pick_recipe`（关键词命中 → 保底轮换）
- **装配**：A-roll 固定格点（间距≥2）、首镜 TitleCard、末镜 EndingCard、视角轮换（host/protagonist/pov）、呈现语法轮换（slam_in/wipe_mask/blur_focus/rise_fade）、氛围色相邻不同、C-roll 叠层分配
- **验收**：schema + lint（见 §10），违规 → `rebalance` 确定性一次收敛重排
- **beat→候选卡白名单**（variety.py，含手写系卡）：

  | beat | 候选卡 |
  |---|---|
  | hook | impact-open-title / slab-punch-title / number-slab-pop / tracking-in / **typewriter-reveal** / KineticTitle |
  | point | number-counter / bar-chart-growth / converging-arrows / metric-with-sparkline / chart-grow / **hand-drawn-ellipse** / **scribble-annotation** |
  | step | **highlighter-sweep** / chart-grow / numbered-step-stack / step-timeline-vertical |
  | case | number-slab-pop / quote-bracket-pull / number-counter / line-chart-story-draw |
  | contrast | strike-and-replace / type-contrast-emphasis / impact-open-title / slab-punch-title |
  | quote | quote-card / quote-bracket-pull / focus-dim-spotlight / **ink-underline** |
  | cta | subscribe-cta / douyin-follow-card / x-follow-card |

### S4 素材生产
- `s4_manifest.py`：IP 主图/逐镜场景图/**姿态池**（assets/ip/ 扫描）→ manifest.json（**合并式重跑，不清已有登记**）
- `s4b_image_briefs.py`：B-roll × image_prompt 适配器确定性轮换 → 生图 prompt 任务单（图存 `assets/broll/<镜号>.png` 即被 S5 消费）
- `s4c_stock_footage.py`：Pexels/Pixabay 素材视频（关键词派生：LLM 翻译具象化→规则兜底；无 key 出人工任务单）
- `s4d_whiteboard.py`：有源图的镜头 → whiteboard-animator 手绘逐字动画 mp4 → broll_videos
- `s4_capture.py`：playwright 网页实拍（截图/滚动录屏）→ 真图证据镜头

### S5 渲染（s5_render.py）
逐镜调 Remotion CLI（props 传完整 JobData）→ `render/segments/SXXX.mp4` → ffmpeg concat → `out/video-silent.mp4`。
全局机制：Ken Burns 连续相机曲线（匀速线性，防 freezedetect 误判）+ Idle 呼吸微动 + Presentation 呈现语法。

### S6 混音 + QA（s6_mix.py / s6_qa.py）
VO 混入 + BGM sidechain 闪避 + loudnorm 响度归一 → `out/video-final.mp4`。
QA：静止帧检测 + playwright 真实渲染 9 规则 + SFX 锚点检查 → `qa/report.json`。

### S7* 消融实验（ablation.py）
特征开关变体 × 确定性指标（配方多样性/生图任务/画风来源/叠层镜/lint 错误），产物 `docs/ablation.md`。详见 OPERATIONS.md §2.5。

---

## 7. 渲染引擎（render-engine/，Remotion 4.0.216）

```
src/
├── index.ts                  # registerRoot 入口 + calculateMetadata 动态时长
├── compositions/
│   └── ShotComposition.tsx   # 镜头根组件：叠层/OVERLAY_MAP/RealFootage 升级/相机曲线/Karaoke 字幕
├── shots/                    # 16 个自研镜头组件
│   ├── TitleCard/EndingCard/KineticTitle（结构卡）
│   ├── ARollScene（v3：角色姿态状态机，见 §9）
│   ├── QuoteCard/CompareCard/StepsCard/ListGrid/TransformCard/ScreenshotCard
│   └── ImageLedCover/PipelineSteps/CompareCardEnhanced/KPI_Tower/MatrixHero/MapCard
├── cards/                    # 79 张 talkcraft 移植卡（63 张可自动灌内容）
│   ├── registry.json         # 档位/内容键/arities/时长（import_cards.py codemod 生成）
│   ├── CardHost.tsx          # 卡宿主：960×540 卡适配画布 + setCardContent 注入 + 播完 Freeze
│   └── content.ts            # 内容构建器：引号词→数字→意图→句块 逐级补位，TEXT 对齐 arities，单条≤16字截断
├── overlays/index.tsx        # C-roll 叠层：particles/light_sweep/grain/vignette/tint_warm/tint_cool/snow/embers（remotion-bits 物理粒子）
├── captions/KaraokeLine.tsx  # 卡拉OK 字幕（字级高亮，锚 timing.words）
├── systems/                  # CameraRig / Presentation / Idle
└── lib/loader.ts             # JobData 派生（msToFrames 等，禁 fs）
```

- **卡注入协议**：`globalThis.__OUTVIDEO_CARD__ = {CONFIG?, TEXT?, ROWS?}`，CardHost 保证注入发生在卡模块求值前
- **卡档位**：`injectable`（可自动灌文案，进 S3 轮换）/ `raw`（内容硬编码，不进轮换，手动专用）

---

## 8. 适配器系统（pipeline/adapters/）

**核心抽象**：环节多解法 → adapter 注册表 → 机器闸验收。别人项目的核心功能一旦吸收，就永久成为本项目的器官。

### 能力接口（base.py）

| capability | 产出 | 接进哪 |
|---|---|---|
| `image_prompt` | 生图 prompt 任务 | S4B |
| `recipe_knowledge` | 配方知识索引 | S3 配卡词汇 |
| `script_structure` | script.json segments | S1 |
| `chart_render` | 图表渲染资产（外部二进制） | S4 |
| `video_render` | 视频渲染资产（外部 CLI） | S4D → broll_videos |
| `screen_capture` / `stock_footage` | 网页实拍 / 素材视频 | s4_capture / s4c |

### 已注册适配器（provenance 落盘 adapters/registry.json）

| 适配器 | 能力 | 来源项目 | 吸收方式 |
|---|---|---|---|
| hand-drawn-styles | image_prompt | hand-drawn-styles（19 画风模板） | prompt_pack |
| handraw-style-216 | image_prompt | handraw-style（216 画风描述+参考图） | prompt_pack |
| vox-collage | image_prompt | vox-director（拼贴 5 段式） | prompt_pack |
| zine-poster | image_prompt | gc-minimal-zine-poster（留白海报） | prompt_pack |
| shotcraft-cards | recipe_knowledge | video-shotcraft（152 方法论卡） | prompt_pack |
| whiteboard-animator | video_render | whiteboard-animator（白板手绘动画） | api |
| archify | chart_render | archify（架构/流程图 IR→HTML→PNG） | api |
| playwright-capture | screen_capture | playwright.dev | api |
| stock-footage | stock_footage | MoneyPrinterTurbo（搜索协议） | api |

新适配器 = 实现 `available() + produce() + self_check()` 三个函数放进 adapters/ 目录，自动被发现注册。流程：`absorb.py scan → scaffold → 实现 → verify`。

**已评估不吸收清单**（理由存档于 docs/absorption.md）：整管线同构产品（MoneyPrinterTurbo 等）、PPT 产物类（dads-powerpoint/PPTist）、垂直片型模板、S7 分发类（届时接）。

---

## 9. IP 角色系统（短发 T 恤女孩）

```
assets/ip/
├── ip*.jpg …        # 姿态池：任意数量图片，A-roll 按出场序轮换
├── idle/point/confident/shock/question.png  # （可选）规范姿态名 → 语义优先轮换
└── ref/             # 生图参考图（不进状态机）
```

- **ARollScene v3**：manifest.ip_poses 有图 → 剪纸角色（姿态轮换 + 呼吸 ±1.5% + 镜像弹跳 + multiply 融纸底）；无图 → 降级 flip-book 单图模式
- s4_manifest 合并式扫描（.DS_Store/ref/ 自动排除）；本人 IP 优先于 ip-placeholder 占位
- 待接入：能量弧（beat 语义驱动姿态，如 contrast→shock），当前按镜头序轮换

---

## 10. 质量闸与 QA（机器闸清单）

| 闸 | 位置 | 拦什么 |
|---|---|---|
| preflight | 渲前 | 音色/IP 图/音效文件/组件注册/数字汉字铁律/工具链 |
| card_lint | 卡片 | 卡文件存在/注册在册/已接线/时长 |
| lint.py | 编排 | 时长 2-18s / motion 锚词必须存在于 timing.words / 连续同类 roll≤3 / 连续同配方≤2 / 单配方全片上限 / A-roll 间隔≥2 / 首末镜固定 / **TEXT 条数=arities 且单条≤16 字** / 叠层≤2(A-roll≤1) / 时间轴连续无缝 |
| s6_sfx_check | 音效 | 锚词存在 / 相邻 SFX 间距≥300ms |
| s6_qa | 成片 | 静止帧检测（freezedetect）+ playwright 真实渲染 9 规则 + 响度 |

LLM 链（pipeline/llm.py）：`PIPELINE_LLM_CHAIN` 环境变量配置，如
`openai:https://api.xx/v1|model|KEY_ENV -> ollama:qwen3.5:9b -> none`；小任务化 + schema 收窄 + 失败喂回修复（有限轮）；全挂走规则兜底，**管线永不因模型挂掉而阻塞**。

---

## 11. 主题系统（46 套）

- 自研 10 套：ink-classic / indigo-porcelain / forest-ink / kraft-paper / dune / midnight-ink / ikb / lemon / lemon-green / safety-orange
- html-ppt-skill 吸收 36 套：tokyo-night / dracula / nord / gruvbox-dark / catppuccin-mocha / rose-pine / xiaohongshu-white / cyberpunk-neon / japanese-minimal / blueprint …
- 用法：project.json `"theme": "<slug>"` → `apply_theme.py`；查全部 `THEME_MAP`

---

## 12. 扩展指南

| 想加什么 | 怎么做 |
|---|---|
| 新镜头组件 | render-engine/src/shots/ 写 tsx → ShotComposition.SHOT_COMPONENTS 注册 |
| 新移植卡 | `import_cards.py` codemod（talkcraft 模式）→ card_lint 闸 |
| 新画风适配器 | adapters/ 写三个函数（照 zine_poster.py 抄骨架）→ `absorb.py verify` |
| 新主题 | theme_tokens.py 加 dict + THEME_MAP（或从 CSS 变量批量生成） |
| 新 beat 词汇 | variety.py BEAT_CARDS（卡必须在 registry.json 或本地 shots） |
| 接新 skill | `absorb.py scan <目录>` 起步，见 docs/absorption.md |

## 13. 已知坑（实测踩坑存档）

1. **.venv 搬家**：pip 脚本 shebang 失效 → 一律 `.venv/bin/python -m pip …`
2. **remotion-bits 未声明 culori** → 已手动 `npm install culori`
3. **webpack 缓存不可靠** → 已全局禁用（旧 bundle 曾致三轮返工）
4. **Remotion 4 入口** → `src/index.ts`（registerRoot）+ calculateMetadata 动态时长
5. **rebalance 震荡** → 逐错修复会来回跳，改"一次收敛重排"
6. **A-roll 叠层残留** → 配方变更必须同步重算叠层（assign_overlay 单一来源）
7. **Ken Burns 缓动** → 首尾速度趋零会被 freezedetect 判冻结 → 匀速线性
8. **小黑 IP 已下线**（非本人 IP）；本人 IP = 短发 T 恤女孩

## 14. 文档索引

| 文档 | 内容 |
|---|---|
| `docs/OPERATIONS.md` | **应用层操作手册 + 数据流转**（命令速查必读） |
| `docs/PROJECT.md` | 本文档（完整项目说明书） |
| `docs/absorption.md` | 吸收手册：新 skill 如何进管线 + 全部吸收记录 |
| `docs/contracts.md` | 数据契约细则 |
| `docs/shot-library.md` | 镜头组件库文档 |
| `docs/pipeline-architecture.md` | 架构演进记录 |
| `docs/fixes-20260902.md` | Remotion 4 兼容修复记录 |
