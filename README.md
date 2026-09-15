# out_video-ip · 文字稿 → 自动分镜 → 动态卡渲染 → 成片验收

本地优先的全自动「讲知识短视频」生产流水线：输入一篇 `story.md`，输出一支**配音、字幕、分镜、动效、混音、QA 全部自动完成**的成片（MP4）。全程确定性：同一份输入跑两遍，产物逐字节一致。

```
story.md ─▶ S1 脚本结构化 ─▶ S2 配音+字级对齐 ─▶【锁定 timing.json】
        ─▶ S3 视觉编排 ─▶ S4 素材 ─▶ S5 Remotion 渲染 ─▶ S6 混音+QA ─▶ video-final.mp4
```

配套 **Studio 可视化操作台**（FastAPI + Vite），九个页面覆盖流水线推进、编排改稿、资产卡库、召回调试、素材管理、渲染与验收。

---

## 一、核心设计：S2 的时间轴是唯一事实

整个系统真正的主轴是：

> **S1 决定「我说什么」，S2 决定「我什么时候说」，S2 之后时间轴锁定，S3 只能在已确定的语音时间轴上做视觉编排，S5 渲染绝对服从它。**

| 阶段 | 输入 | 输出 | 职责边界 |
| --- | --- | --- | --- |
| S0 初始化 | story.md | `project.json` + job 目录 | 元信息登记 |
| S1 脚本 | story.md | `script.json`（段落/句/字幕三级结构） | 语义分段，**不决定镜头时长** |
| S2 配音对齐 | script.json | `audio/vo.wav` + `timing.json`（字级时间） | 本地 TTS + Whisper 字级对齐；**产出不可修改的时间预算** |
| S3 视觉编排 | script + timing + 资产卡库 + 检索层 | `storyboard.json` | Shot 只能在 `Shot.start ≥ timing.start ∧ Shot.end ≤ timing.end` 内切分；一个 beat 区间可拆多镜，但不可越界 |
| S4 素材 | storyboard 的 `assets_needed` | `assets/manifest.json` | 只解决「已有→复用；没有→生成/采集」，**不重新编排镜头** |
| S5 渲染 | timing + storyboard + manifest + 251 张卡 | `render/segments/*.mp4` → 合并 | Remotion 逐镜渲染，语音时间轴 = Master Timeline |
| S6 混音验收 | 无声片 + vo.wav + BGM + SFX | `out/video-final.mp4` + QA 报告 | sidechaincompress 闪避、响度归一、静止帧/密度检测 |

### S3 的语义链（不把「文字/图片/B-roll」当平级分类）

```
文案 → Beat（这句话在叙事上做什么）
     → Visual Intent（观众必须看到什么关系）
     → Shot（时间轴内切几个镜头）
     → Visual Type（二选一）
         ├─ dynamic_card   动态卡：本身就是完整 5 秒镜头，内部文字/图片/数字全是可注入槽位
         └─ material       素材：still_image / b_roll，靠统一镜头语言（push-in / pan / Ken Burns）成镜
     → Asset Plan（只有 material 才向 S4 要素材；动态卡镜头不需要生图）
     → Storyboard
```

- **Beat**（叙事功能）：statement / problem / change / comparison / cause_effect / process / example / evidence / explanation / conclusion，一句话可多标签。
- **Visual Intent**（视觉关系，有限枚举）：comparison / before_after / contrast / data / trend / timeline / process / cause_effect / relationship / hierarchy / focus / example / scene / character / concept。
- **A/B 节奏**：A-roll（IP 讲述镜头）与 B-roll（动态卡/素材镜头）按 `rebalance()` 确定性铺点（首 A 固定第 4 镜、段间距 [3,4] 均分、连续同 roll ≤3、首镜 TitleCard 末镜 EndingCard），`scripts/s3_check.py` + `pipeline/lint.py` 全量校验。

---

## 二、动态卡体系（render-engine/）

**一张资产卡 = 动效骨架（锁死）+ 内容槽位（全部可注入）。** 251 张卡中 **231 张 injectable**（文字/图片槽全部可外部替换），其余 20 张为转场/纯特效卡（无内容语义，豁免）。

### 卡槽契约

每个卡文件头部注入：

```ts
const __INJ__: any = (globalThis as any).__OUTVIDEO_CARD__ ?? {};
```

| 槽位类型 | 写法 | 注入来源 |
| --- | --- | --- |
| 文字槽 | `((__INJ__.TEXT as string[])?.[0] ?? "默认文案")` / 整组替换 `__INJ__.TEXT?.length ? __INJ__.TEXT : [默认…]` | registry `arities: {TEXT: n}` + `slotDefaults` |
| 图片槽 | `staticFile(String((__INJ__.CONFIG as any)?.image_1 ?? '原路径'))` | registry `images: ['image_1'…]` |
| 对象槽 | `__INJ__.SLOTS: {text?, image?}[]`（wireframe 面板可图文混排） | shot.config 直填 |
| 参数槽 | `const CONFIG = { 默认值…, ...(__INJ__.CONFIG ?? {}) }` | shot.config.CONFIG 整体透传 |

注入链路：`buildCardContent()`（render-engine/src/cards/content.ts）按 registry arities 逐槽对齐，形状感知（字符串数组槽 vs 对象数组槽不混灌），shot.config 人工内容优先、自动派生兜底（从口播确定性抽取关键词）。

### 卡的来源与蒸馏（任何人/任何素材都能进这套体系）

`scripts/wire_sc_cards.py` 是确定性 codemod，规则 A–H 自动给移植卡铺槽：

| 规则 | 覆盖 |
| --- | --- |
| A | 顶层字符串数组常量 → TEXT 组槽 |
| B | `_sc_assets` 图片 import → CONFIG.image_N |
| C | TitleBlock text= 属性 / 对象数组 text: 字段 → 按下标 TEXT |
| D | JSX 文字节点 `>文字<` → TEXT |
| E | 顶层/组件内字符串常量（含 `.split()` 形态）→ TEXT |
| F | JSX 内联 `{'文字'}` → TEXT |
| G | CONFIG spread 顺序修正（保证注入可覆盖默认值） |
| H | `staticFile('….png')` 字面量 → CONFIG.image_N |

蒸馏流水线（资产库页面「蒸馏」区或 `/api/distill/*`）：

> **手写蒸馏路径**（针对 PPT/教程里"如何做动效"这类内容）：`POST /api/distill/scaffold`
> `{slug, template: text|serif|mono|steps|title, category, lines}` 一键生成带注入槽位的卡骨架
> （或 `from_tsx` 收编外部自包含 tsx），你只需要在骨架里写动效；随后 `wire_sc_cards.py` 规则 A–H 自动埋槽。
> CLI 等价命令：`python scripts/gen_card.py --slug my-card --template text --category effects`。

```
任意外部项目（tsx 卡 / 方法论 md / PPT / 视频特效）
  → /api/distill/scan   白名单源 glob 扫描候选
  → /api/distill/absorb 文件吸收（tsx → _distill 素材区 + backlog 登记）
  → 移植 codemod（import_shotcraft 范式：单卡重移植、路径替换、补 default export）
  → wire_sc_cards.py 规则 A–H 铺槽
  → extract_card_slots.py 抽取槽位默认值 → registry.json
  → esbuild 全量编译预检 + 卡 lint（连续同 roll/时长/首末镜约束）
```

**质量护栏**：每次改动必须过 `for f in src/cards/card-*.tsx; do esbuild …; done` 全绿 + `extract_card_slots.py` 刷新 + 卡快照（CardSnapshot）。

---

## 三、检索与 RAG（S3 选卡大脑）

S3 为每个 beat 选卡走三级路由（全部确定性，可复现）：

1. **元数据打分**（pipeline/variety.py）：Hard Filter（tier/时长/近 2 镜去重/全片 cap）→ 打分 `0.5×intent匹配 + 0.3×category3 + 0.2×新鲜度 − 0.25×近期已用`；全低于阈值 → 空。
2. **关键词配方回退**（pipeline/fallback.py）：BEAT_CARDS 白名单轮换。
3. **WeKnora 语义兜底**（pipeline/weknora.py）：本地 WeKnora（docker compose + Ollama embedding）把 247 张卡 ingest 成知识库（KB `asset-cards`），hybrid-search 语义召回候选，intent 相交过滤后并入。**WeKnora 不可用时自动降级，纯本地照样出片。**

### 召回调试界面（Studio ·「召回调试」页）

- 输入一句描述（如"强调数字结论的冲击卡"）+ beat → 返回 top-N 候选：来源（语义召回/元数据打分/保底王）、分数、时长、槽位清单。
- 右侧 Remotion Player 实时预览选中卡（真实注入渲染）。
- 选镜后一键「替换该镜」配方——人工校验排序、随时干预 S3 的选卡。

### 确定性与消融

- 同输入同输出：S3 两跑 storyboard 逐字 diff 一致（CI 可断言）。
- `scripts/ablation.py`：关掉某层（检索/节奏门/打分）的对比报告，验证每层的真实贡献。

---

## 四、S4 素材链（需要才生成，绝不每个镜头都生图）

| 能力 | 脚本 / adapter | 说明 |
| --- | --- | --- |
| 生图任务单 | `scripts/s4b_image_briefs.py` | 只给需要底图的 B-roll 镜生成 brief；**默认锁定 `ip-character` adapter**（自有 IP 形象为主、风格固定）；`--adapter all` 恢复多画风轮换 |
| 自有 IP 生图 | `pipeline/adapters/ip_character.py` | **黑发短发女孩·蓝色短袖T恤**（基准参考图 `assets/ip/*.png`）；水墨手绘固定风格 DNA（白纸底/墨线/淡彩/大量留白）；**情绪固定**（冷静、认真、略带好奇）；**动作轴随 visual_intent 确定性映射**（data→天平称数字块、before_after→推分界闸门、process→摇三级传动…）；中文标注一律不进生图，由 Remotion 卡槽渲染 |
| ComfyUI 出图 | `scripts/s4e_local_images.py` | 本地 ComfyUI（127.0.0.1:8188，Flux2-Klein），**喂给它的 JSON 数据规范**：`{shot_id, adapter, style, aspect, prompt(含 IP_LOCK 角色锁), negative(无文字/无水印/无渐变…), seed(确定性回写), reference_image(IP 基准图), target_path}`；PNG 自动转 Ken Burns MP4 进 manifest；同 seed 重跑同图 |
| 素材视频搜索 | `pipeline/adapters/stock_footage.py` + `scripts/s4c_stock_footage.py` | 吸收自 MoneyPrinterTurbo：Pexels/Pixabay 免费商用素材库「文案→关键词→搜索→下载」；Studio「素材」页可搜、可按镜派生关键词、可一键应用（下载登记 manifest，S5 该镜升级 RealFootage）；无 API key 自动降级为关键词任务单 |
| 白板动画 | `scripts/s4d_whiteboard.py`（whiteboard-animator CLI） | 静态图→手绘逐字书写动画 |
| 网页截图 | `scripts/s4_capture.py` + enhance_screenshot | 真实网页截图 + 增强，ScreenshotCard 消费 |
| IP 姿态池 | `assets/ip/` | A-roll 场景图（姿态/情绪库，`ip_scenes` 登记） |

S4 的铁律：**S3 说需要什么才找什么；已有就复用；动态卡镜头零素材依赖。**

---

## 五、Studio 操作台（studio/）

```bash
bash studio/start.sh
# 前端 http://localhost:5188（注意：必须用 localhost，不是 127.0.0.1）
# 后端 http://127.0.0.1:8321
```

| 页面 | 功能 |
| --- | --- |
| 流水线 | 阶段状态机推进 / 闸门放行 / 运行日志 |
| 编排 | storyboard 可视化改稿：每镜口播/roll/intent/配方/槽位文案/图层/SFX/转场，改完保存即 S5 输入 |
| 资产库 | 251 张动态卡全库浏览（分类/槽位/时长）、效果选择器（挂卡/挂图层/生图/图库/白板）、蒸馏吸收 |
| 召回调试 | RAG 三来源召回排序 + 实时卡预览 + 一键换卡 |
| 脚本 | S1 分段结果审阅 |
| 素材 | **生图任务单（按镜头）**：S3 语义派生的全部生图任务逐镜呈现，状态（待生成/已完成/失败）、成图预览、改 prompt 保存即清旧图、单镜重跑/全部生成；**素材视频搜索**（Pexels/Pixabay 按镜派生关键词、一键应用）；manifest 浏览与上传替换 |
| 渲染 | S5/S6 触发与进度 |
| 验收 | QA 报告 / 密度门 / contact sheet |

> 配音页已移除：S2 的 TTS + 对齐在流水线推进时自动完成，无需人工界面（保留后端能力，代码在 scripts/s2_*.py）。

---

## 六、快速开始

```bash
# 0) 环境
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cd render-engine && npm install && cd ..
# 外部本地工具（可选）：index-tts（TTS）、faster-whisper（对齐）、ComfyUI:8188（生图）、Ollama:11434（LLM/embedding）

# 1) 建作业（读 story.md）
.venv/bin/python scripts/pipeline.py init jobs my-video "视频标题" --story story.md

# 2) 一键推进（自动跑 S0→S2→S3，到人工闸门停下）
.venv/bin/python scripts/pipeline.py run jobs/<job_id>

# 3) 审阅编排表后放行 S3
.venv/bin/python scripts/pipeline.py gate s3 --approve jobs/<job_id>

# 4) 继续到成片
.venv/bin/python scripts/pipeline.py run jobs/<job_id>
# （跳过上游过期闸一键到底：run --push-through）

# 5) 或全程用 Studio 点按钮
bash studio/start.sh
```

### S4 素材链用法

```bash
# 生图任务单（默认 ip-character，自有 IP 女孩风格）
.venv/bin/python scripts/s4b_image_briefs.py jobs/<job_id>

# 本地 ComfyUI 出图 → 自动转 MP4 → 登记 manifest
.venv/bin/python scripts/s4e_local_images.py jobs/<job_id>

# 素材视频（Pexels/Pixabay，需 export PEXELS_API_KEY=…）
.venv/bin/python scripts/s4c_stock_footage.py jobs/<job_id>
```

### 检索基础设施（可选增强）

```bash
# WeKnora（语义召回）：另仓库 docker compose up -d，然后 ingest 247 张卡
cd /path/to/WeKnora && docker compose up -d
.venv/bin/python scripts/weknora_ingest.py     # 失败自动跳过，主流程不受影响
```

### 关键环境变量

| 变量 | 作用 | 缺省 |
| --- | --- | --- |
| `PIPELINE_LLM_CHAIN` | LLM 链，`openai:base_url\|model\|KEY_ENV -> ollama:model -> none`（多级降级） | `ollama:qwen3.5:9b-q4_K_M -> none` |
| `PEXELS_API_KEY` / `PIXABAY_API_KEY` | 素材视频搜索 | 缺则降级关键词任务单 |
| `OLLAMA_BASE` | Ollama 地址 | `http://localhost:11434` |
| `WEKNORA_URL/USER/PASS` | WeKnora 语义检索 | `127.0.0.1:8080` + 本地默认账号 |
| ComfyUI | `127.0.0.1:8188` | s4e 需本机已起 ComfyUI |

---

## 七、数据契约（schemas/，单一真相源）

```
project.json    画布/主题/IP/音色 —— 全局配置
script.json     段落 segs → 句子 sents → 字幕 caps 三级结构（S1）
timing.json     每句 {text, start, end, words:[{text,start,end}]} 字级时间（S2，锁定不可改）
storyboard.json shots[]：{id, time(⊆timing 区间), vo, roll(A/B), beat, intent, visual,
                recipe_ref(card:slug / ARollScene), config:{TEXT/STEPS/SLOTS/CONFIG},
                layers, sfx, transition_in, status}（S3）
assets.schema   manifest.json：ip_images / ip_scenes / broll_videos / screenshots / local_images（S4）
visual_ir.schema 影子编译器 IR（消融/对照）
```

job 目录：

```
jobs/<job_id>/
├── project.json script.json timing.json storyboard.json
├── audio/vo.wav  audio/bgm.mp3
├── assets/manifest.json  assets/image_briefs.json  assets/broll/*.png  assets/broll_videos/*.mp4
├── render/segments/*.mp4 → render/data.json（S5 staging）
├── out/video-final.mp4
└── qa/report.json  qa/frame_metrics.json  docs/storyboard-table.md
```

**渲染端只读这五个 JSON**（render-engine/src/lib/loader.ts），卡组件永远不直接接触流水线。

---

## 八、减方差三件套（为什么两跑逐字一致）

1. **渲前断言**（scripts/preflight.py）：音色/IP 图/音效文件/组件注册/数字汉字铁律/工具链，任一 FAIL 挡渲染。
2. **机器可验节拍**：motion 锚词必须存在于 timing words（s3_check），锚不存在的节拍=写意描述，退回重写。
3. **确定性铺点与选卡**：rebalance 固定锚点 + 检索层纯函数 + 轮换用镜头序号（不用随机）；seed 由 (shot_id, style) 稳定哈希。

---

## 九、项目结构

```
out_video-ip/
├── schemas/               # 6 个 JSON 契约（含 visual_ir）
├── pipeline/              # 状态机(state) + 校验(validate/lint/pace_gate)
│                          # + 检索层(variety/fallback/weknora) + 主题(theme_tokens)
│                          # + adapters/（9 个能力 adapter，见第四节）
├── scripts/               # s0~s6 阶段脚本 + pipeline.py 主控 CLI
│                          # + wire_sc_cards/extract_card_slots/ablation/preflight
├── render-engine/         # Remotion 4 引擎
│   ├── src/cards/         # 251 张动态卡 + registry.json（tier/arities/slotDefaults/images）
│   ├── src/shots|systems|captions|compositions|lib
│   └── public/            # sfx / broll / screenshots staging
├── studio/                # FastAPI(server) + Vite(web) 可视化操作台
│   └── web/src/views/     # pipeline/storyboard/library/recall/script/assets/render/qa
├── prompts/               # S1/S3 的 Agent 执行规则沉淀
├── docs/                  # PROJECT.md / OPERATIONS.md / contracts.md / card-prompts.md
├── assets/ip/             # 自有 IP 形象参考图（生图角色锁基准）
└── jobs/<job_id>/         # 作业数据
```

## 十、扩展指南

- **加一张动态卡**：`render-engine/src/cards/card-<slug>.tsx`（按第二节槽位契约写注入头）→ registry.json 登记 `{slug, tier, arities, durationInFrames, category3, desc}` → esbuild 预检 → extract_card_slots。
- **蒸馏别人的卡/视频/PPT**：Studio 资产库「蒸馏」或 `/api/distill/*` → 吸收进 `_distill/` → 按文档 render-engine/docs/card-prompts.md 三段提示词蒸馏 → wire 规则铺槽。
- **换 IP 形象**：替换 `assets/ip/*.png`（第一张为基准）→ 改 `pipeline/adapters/ip_character.py` 的 IP_LOCK 描述与动作映射。
- **加一种素材源**：继承 `pipeline/adapters/base.py` 对应能力基类，模块级导出 `ADAPTER` 即自动注册。
- **加一个生图风格**：实现 `ImagePromptAdapter`（styles() + produce()），在 s4b 用 `--adapter <name>` 指定。

## 十一、外部工具依赖（全部可降级）

| 工具 | 用途 | 缺失时 |
| --- | --- | --- |
| index-tts（本地） | S2 配音 | 不可用则流程阻断（唯一硬依赖） |
| faster-whisper（pip） | S2 字级对齐 | 同上 |
| Remotion 4 | S5 渲染 | 必需 |
| ffmpeg | 合并/混音/QA | 必需 |
| ComfyUI + Flux2-Klein（本地） | S4E 生图 | 缺则 B-roll 走图库/上传 |
| Pexels/Pixabay key | 素材视频 | 缺则关键词任务单 |
| Ollama（LLM/embedding） | S1/S3 增强、WeKnora 向量 | 缺则规则兜底 |
| WeKnora（docker） | 语义召回 | 缺则纯本地打分 |

## 十二、参考与致谢

- **video-talkcraft**：对齐脚本、运动系统、QA 模式
- **video-shotcraft**：152 张镜头配方卡（大量动态卡的来源）
- **MoneyPrinterTurbo**：素材视频搜索协议（Pexels/Pixabay 端点/参数/清晰度选择，api 吸收未 vendor 代码）
- **ian-xiaohei-illustrations**：正文配图风格 DNA 与「固定角色承担核心动作」的提示词纪律（角色已替换为自有 IP）
- **vox-director / gc-minimal-zine-poster / archify / whiteboard-animator**：拼贴海报、纸感海报、架构图渲染、白板动画 adapter

## License

仅供学习与个人创作使用；素材库（Pexels/Pixabay）遵循其各自许可条款。
