# OUTVIDEO-IP 完整操作规范（Operations Spec）

> 版本：2026-09-09 · 本地自动化视频生产工作流
> 输入故事脚本 → 输出成片 + QA 报告。零外部 API 默认（index-tts/ComfyUI/whiteboard-animator 全本地；Pexels/生图 API 可选增强）。

---

## 1. 系统总览

```
story.md（故事文稿）
   ↓ S0  初始化                project.json（画幅/音色/主题/IP 配置）
   ↓ S1  脚本结构化            script.json（segments + beat 标注 + 数字转汉字）
   ↓ S2  本地 TTS + 字级对齐   timing.json（唯一时间真相源，字级 ms 时间戳）
   ↓ ─── 闸门① 编排审阅 ───
   ↓ S3  视觉编排              storyboard.json（镜头分组/配卡/叠层/呈现语法）
   ↓ S4  素材生产              manifest.json（IP 图/姿态池/生图任务/实拍/白板动画）
   ↓ S5  Remotion 渲染         render/segments/*.mp4 → video-silent.mp4
   ↓ ─── 闸门② 60s 样片 ───
   ↓ S6  混音 + QA             video-final.mp4 + qa/report.json
   ↓ S7* 消融实验（可选）      docs/ablation.md
```

四层 S3 架构：分组（规则）→ 配卡（LLM 可选/规则兜底）→ 装配（规则）→ 验收（schema+lint，违规确定性重排）。
**设计铁律**：单一时间真相源（timing.json）、白名单+确定性轮换、渲前断言、离线优先。

---

## 2. 应用层操作手册（用户命令）

所有命令在项目根目录执行；`<job>` 指 `jobs/<日期-slug>` 目录。Python 一律用 `.venv/bin/python`。

### 2.1 一条片的完整生命周期

```bash
# ① 新建（写好 story.md 放任意位置）
.venv/bin/python scripts/pipeline.py init jobs my-slug "视频标题" --story story.md

# ② 自动推进到最近闸门（S0→S2：初始化+脚本结构化+TTS+对齐）
.venv/bin/python scripts/pipeline.py run jobs/<job>

# ③ 人工闸门①：看编排表 → 放行
.venv/bin/python scripts/s3_table.py jobs/<job>        # 生成 docs/storyboard-table.md 供审阅
.venv/bin/python scripts/pipeline.py gate s3 --approve jobs/<job>

# ④ 继续推进（S3→S6：编排→素材→渲染→混音 QA）
.venv/bin/python scripts/pipeline.py run jobs/<job>

# ⑤ 人工闸门②：看 out/video-final.mp4（60s 样片）→ 满意即交付
.venv/bin/python scripts/pipeline.py status jobs/<job>  # 随时查状态
```

### 2.2 素材增强（全部可选，按需单独跑）

```bash
# 生图任务单：B-roll 镜头 × 画风适配器确定性轮换 → assets/image_briefs.json
.venv/bin/python scripts/s4b_image_briefs.py jobs/<job>

# 本地生图闭环：任务单 → ComfyUI FLUX Klein PNG → ffmpeg MP4 → manifest
# 默认 127.0.0.1:8188；--limit 1 先验一张，全量跑省略 limit。
# 脚本会删除要求“画标题/大字/手写短句”的句子；字幕仍由 S5 渲染，避免模型画出假汉字。
.venv/bin/python scripts/s4e_local_images.py jobs/<job>

# 真实素材视频：有 PEXELS/PIXABAY key 全自动下载；无 key 出搜索任务单
.venv/bin/python scripts/s4c_stock_footage.py jobs/<job>

# 白板手绘动画：assets/broll/ 有源图的镜头 → 手绘逐字书写动画（CPU 本地）
.venv/bin/python scripts/s4d_whiteboard.py jobs/<job>

# 网页实拍：截图/滚动录屏 → 真图证据镜头（资讯/教程类）
.venv/bin/python scripts/s4_capture.py jobs/<job> <url>

# 主题色：project.json 改 theme 字段后应用（46 套可选，见 2.4）
.venv/bin/python scripts/apply_theme.py jobs/<job>
```

### 2.3 IP 形象（短发 T 恤女孩）

```
assets/ip/
├── ip*.jpg / *.png   # 姿态池：任意数量，A-roll 按出场序轮换 + 呼吸微动
├── idle/point/confident/shock.png  # （可选）规范姿态名 → 优先语义轮换
└── ref/              # 参考图（生图用，不进状态机）
```

- 放好图后对每个 job 执行 `.venv/bin/python scripts/s4_manifest.py jobs/<job>`（合并式，不清已有素材登记）
- 无图也不阻塞：自动降级 flip-book 单图模式

### 2.4 主题（46 套）

`project.json` → `"theme": "<slug>"` → `apply_theme.py`。
自研 10 套（ink-classic/indigo-porcelain/ikb/lemon…）+ html-ppt-skill 吸收 36 套
（tokyo-night/dracula/nord/gruvbox-dark/xiaohongshu-white/cyberpunk-neon/japanese-minimal…）。
查全部：`.venv/bin/python -c "from pipeline.theme_tokens import THEME_MAP; print(list(THEME_MAP))"`

### 2.5 消融实验

```bash
.venv/bin/python scripts/ablation.py jobs/<job>
# 输出 docs/ablation.md：baseline vs 特征开关变体的确定性指标对比
```

| 变体 | 回答的问题 |
|---|---|
| `no_handwritten` | 手写系卡对配方多样性的贡献（撤掉后多样性降多少） |
| `no_overlay` | C-roll 氛围层的覆盖面（叠层镜数差） |
| `no_image_adapters` | 生图成本全省时的代价（任务数/画风来源归零） |
| `only_legacy_adapter` | 只用 1 个画风源 vs 4 个（画风来源 1 vs 4） |

指标：镜头数 / 配方多样性 / 最大配方占比 / 生图任务 / 画风来源 / 叠层镜 / lint 错误。全部确定性可复算，无需渲染。新 job 跑完 S3 即可消融（不必等成片）。
`生图任务`按 S4B 的真实口径统计所有 `roll=B`；报告底部另列当前 manifest 里可消费的 B-roll 视频数。

### 2.6 未来接新 skill（吸收手册）

```bash
.venv/bin/python scripts/absorb.py scan <项目目录>    # 侦察资产形态
.venv/bin/python scripts/absorb.py scaffold <capability> <名字> <源路径>
# 实现 produce() + self_check() 两个函数 → absorb.py verify → 自动进闸
```

---

## 3. 业务数据流转

### 3.1 五大数据契约（schemas/，schema 校验强制）

| 契约 | 生产者 | 核心字段 | 消费者 |
|---|---|---|---|
| `project.json` | S0 | canvas/voice/theme/style/ip | 全部阶段 |
| `script.json` | S1 | segments[]{id,text,beat,visual_hint} | S2/S3 |
| `timing.json` | S2 | segments[]{start_ms,end_ms,words[]} | S3/S5/S6（唯一时间真相源） |
| `storyboard.json` | S3 | shots[]{time,vo,roll,recipe_ref,config,overlay,presentation,sfx} | S4/S5/S6 |
| `manifest.json` | S4 | ip_images/ip_scenes/**ip_poses**/broll_videos/screenshots/bgm/sfx | S5 |

关键机制：
- **镜头级重渲染**：S5 按 shot 逐镜渲 mp4 → ffmpeg concat；改一镜只重渲一镜
- **B-roll 自动升级链**：manifest.broll_videos 有素材的镜头 → RealFootage 配方（Ken Burns 覆盖）
- **C-roll 叠层纪律**：任何镜 ≤2 层，A-roll ≤1 层（IP 镜头干净）；配方变更自动重算叠层

### 3.2 适配器注册表（pipeline/adapters/，7 个器官，provenance 落盘）

| 适配器 | 能力 | 来源 | 进哪 |
|---|---|---|---|
| hand-drawn-styles | image_prompt | 手绘 19 画风（模板型） | S4B 任务单 |
| handraw-style-216 | image_prompt | 手绘 216 画风（描述型+参考图） | S4B |
| vox-collage | image_prompt | Vox 纸片拼贴 5 段式 | S4B |
| zine-poster | image_prompt | 诗性留白海报（70-90% 留白纪律） | S4B |
| shotcraft-cards | recipe_knowledge | 152 张镜头方法论 | S3 词汇 |
| whiteboard-animator | video_render | 白板图→手绘动画（CPU） | S4D → broll_videos |
| archify | chart_render | 架构/流程图 JSON IR → HTML → playwright 截 PNG | S4B 通道（tech 类镜头） |
| （外部）playwright / stock-footage | screen_capture / stock_footage | 网页实拍 / Pexels·Pixabay | s4_capture / s4c |

能力接口（base.py）：`image_prompt` / `recipe_knowledge` / `script_structure` / `chart_render` / `video_render`。
新适配器实现 `available()+produce()+self_check()` 即自动被发现注册。

### 3.3 机器闸清单（任一 FAIL 挡渲染）

| 闸 | 位置 | 拦什么 |
|---|---|---|
| preflight | 渲前 | 音色/IP 图/音效文件/组件注册/数字汉字铁律/工具链 |
| card_lint | 卡片 | 卡文件存在/注册在册/已接线/时长 |
| s3_check + lint | 编排 | 节奏铁律（时长 2-18s/motion 锚词存在）/连续同类≤3/同配方上限/A-roll 间隔≥2/首末镜固定/**TEXT 条数=arities 且单条≤16 字**/叠层≤2/时间轴连续 |
| s6_sfx_check | 音效 | 锚词存在/间距≥300ms |
| s6_qa（+playwright 9 规则） | 成片 | 黑场/冻结帧/响度/真实渲染测量 |

---

## 4. 已知坑与约定

- **依赖指纹闸（2026-09-09）**：阶段 done 时记录产物+输入指纹；上游变更后 rerun 下游会被拒绝并指出变更文件（`--force` 豁免）；`status` 输出 fresh/STALE 表。不做 stale 下游自动删除（拒绝+指路代替）
- **对齐置信度（2026-09-09）**：timing.json 每段 `align_confidence(high/medium/low)`；字幕自动降级（high 逐字/medium 词块/low 整句）；低中置信段出列到 `audio/align-review.csv`（人工可改后回灌）
- **数字豁免（2026-09-09）**：iPhone 15 / 120Hz / 16:9 类 token 保留原样不走汉字铁律（script.json meta.protected_tokens），对齐碎片自动合并为完整 token（跨度>2s 强降 low）

- **.venv 已从旧路径搬迁**：`pip` 脚本 shebang 失效 → 一律 `.venv/bin/python -m pip ...`
- Remotion 4.0.216 + remotion-bits 0.2.0（需手动补装其未声明的依赖 `culori`，已装）
- webpack 缓存已全局禁用（旧 bundle 曾致三轮返工）
- 渲染入口 `src/index.ts`（registerRoot）+ calculateMetadata 动态时长
- 白板动画源图放 `assets/broll/<镜号>.png`；白底图会以 multiply 融进纸底舞台
- 小黑 IP 已下线（非本人 IP）；本人 IP = 短发 T 恤女孩（assets/ip/）
- dads-powerpoint 未吸收：产物是 .pptx，与本管线（视频）产物不符，设计原则与现有 46 主题重叠

## 5. 外部工具依赖

| 工具 | 用途 | 状态 |
|---|---|---|
| index-tts（本地） | S2 配音 | 必须 |
| faster-whisper（.venv） | S2 对齐 | 必须 |
| Remotion 4.0.216 | S5 渲染 | 必须 |
| ffmpeg | 拼接/混音 | 必须 |
| ComfyUI 127.0.0.1:8188 | A-roll 场景生图 | 可选 |
| whiteboard-animator（.venv） | 白板动画 | 已装 |
| playwright + chromium（.venv） | 实拍/QA/archify 截图 | 已装 |
| node + archify | 架构图渲染 | 已备（源目录即用） |

## 2.7 质量与回归工具（2026-09-09 新增）

```bash
# 卡片视觉回归：改 cards/ 后抽测（>2% 像素差告警并存 diff 图）
.venv/bin/python scripts/card_snapshot.py --only number-counter,quote-card   # 建基线
.venv/bin/python scripts/card_snapshot.py --check --only number-counter      # 回归比对

# 跑题排除器（需 CLIP：.venv/bin/python -m pip install open_clip_torch torch）
.venv/bin/python scripts/s4_relevance_check.py jobs/<job>                    # 低分图标 relevance_flag=low
.venv/bin/python scripts/s4_relevance_check.py jobs/<job> --calibrate 标注.csv  # 20 组标注校准阈值

# 保底王降级验证：无 LLM 全链出片（降级组不走关键词配卡，编排表 ⚠️ 标记）
PIPELINE_LLM_CHAIN=none .venv/bin/python scripts/s3_storyboard.py jobs/<job>
```

## 2.8 视觉建议级 QA（2026-09-10 新增）

`s6_qa.py` 除原 7 条硬闸外，自动生成逐镜视觉指标和可读 contact sheet；
指标只给返工建议，不改变 S6 退出码。

```bash
.venv/bin/python scripts/s6_qa.py jobs/<job>
# 人工复查：镜头 + VO + 画面描述
open jobs/<job>/qa/contact-sheet.html
# 量化报告：主体/空场/柔光/杂讯/静止
cat jobs/<job>/qa/frame-metrics-report.md
```

判据、来源取舍和后续硬闸化条件见 `docs/anything2explainer-integration.md`。
