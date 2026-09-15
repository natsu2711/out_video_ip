# 吸收手册：新 skill / 开源项目如何进管线

> 回答"以后新的 skills 该如何移植"。核心抽象：**环节多解法 → adapter 注册表 → 机器闸验收**。
> 别人项目的核心功能一旦吸收，就永久成为本项目的器官，原项目可以删。

## 四种能力接口（pipeline/adapters/base.py）

| capability | 产出 | 接进哪 | 现有实现 |
|---|---|---|---|
| `image_prompt` | 生图 prompt | S4B 图像任务单 | hand-drawn-styles(19 画风)、ian-xiaohei(小黑IP) |
| `recipe_knowledge` | 配方知识索引 | S3 配卡词汇 / 移植队列 | shotcraft-cards(152 张) |
| `script_structure` | script.json segments | S1 | LLM链/规则（内置） |
| `chart_render` | 图表视频/图片资产 | S4 | manim（外部二进制，检测可用才路由） |

配方卡（tsx 自包含动效）走独立通道：`scripts/import_cards.py`（已吸收 talkcraft 79 张，63 张可自动灌内容）。

## 标准流程（五步）

```bash
# 1. 侦察：判断资产形态，推荐 adapter 类型
python scripts/absorb.py scan <project_dir>
#    remotion_tsx_cards → import_cards.py codemod 移植
#    prompt_pack        → image_prompt / recipe_knowledge adapter
#    python_pipeline    → api 吸收（外部调用，不 vendor 代码）

# 2. 生成骨架
python scripts/absorb.py scaffold image_prompt my-style /path/to/project --desc "一句话"

# 3. 实现两个函数：produce()（shot 内容 → 契约产出）+ self_check()（断言关键字段）

# 4. 契约验收
python scripts/absorb.py verify my-style

# 5. 自动进闸：image_prompt → S4B 图像任务单；recipe_knowledge → S3 词汇
```

来源、吸收方式（vendor/codemod/prompt_pack/api）、验证状态全部落盘
`pipeline/adapters/registry.json`——每个器官可溯源。

## 不能/不该集成的清单（技术理由，非遗忘）

| 项目 | 理由 |
|---|---|
| MoneyPrinterTurbo / OpenStory / FireRed-OpenStoryline / Pixelle / DiffusionStudio / OpenMontage / video-use | **它们是整管线产品**，与本项目同构。集成=架构套娃。它们的能力维度（TTS/字幕/切片/编辑）已由我们的阶段+闸门覆盖，且我们的版本有契约和 QA。 |
| autoclip / AI-Youtube-Shorts-Generator | 属于 **S7 分发阶段**（成片之后），S7 未启动。届时以 clipper adapter 接入。 |
| manim | 外部二进制依赖（Python 包+渲染链）。已留 `chart_render` 接口，检测到安装即自动路由数据镜头，不 vendor。 |
| lanshu / hbg-classical-poem / creator-buddy | 垂直片型模板（数字人/古诗），挂 S0 作片型预设，不是通用环节能力。 |
| hyperframes / remotion-dev_skills | Remotion 官方最佳实践——已是我们渲染层的规范来源，无需二包。 |
| gbro-collage-broll | 拼贴 B-roll 生成器，同 hand-drawn 模式可接（image_prompt adapter），待排期。 |
| video-talkcraft / video-shotcraft（剩余部分） | 七层系统（CameraRig/视差/让位）已在本渲染引擎有对应物（ShotComposition 全局层）；转场六式、sfx cue 表待吸收（queued）。 |

## 已完成吸收清单（provenance 可溯源）

- ✅ talkcraft 79 张动效配方卡（codemod 移植，63 injectable + card_lint 闸）
- ✅ shotcraft 152 张方法论卡（知识索引 → docs/cards-knowledge.json，S3 词汇源）
- ✅ hand-drawn-styles 19 画风（image_prompt adapter → S4B）
- ✅ ian-xiaohei 小黑 IP 配图公式（image_prompt adapter → S4B）
- ✅ guizang 封面通道（前轮已集成 s6_cover）
- 🔜 baoyu infographic / lieflat-charts（image_prompt，同模式 30 分钟/个）
- 🔜 talkcraft 转场六式 + sfx cue 表（S5 转场 / S6 音效）
- 🔜 shotcraft 高频卡 tsx 移植（知识→代码，走 import_cards 模式）

## 新增吸收：stock-footage（2026-09-03 深夜）
- **来源**：MoneyPrinterTurbo 的核心单点能力「文案→匹配素材视频」（api 吸收：吸收 Pexels/Pixabay
  搜索协议知识，不 vendor 代码）
- **实现**：`pipeline/adapters/stock_footage.py` + `scripts/s4c_stock_footage.py`
  - 关键词派生：LLM 翻译具象化 → 规则兜底（引号词/意图）
  - 降级梯度：有 key 全自动搜索下载 → 无 key 产出关键词任务单（人工素材站）
- **渲染端**：`RealFootage` 配方——manifest.broll_videos 有素材的 B-roll 自动升级真实素材，
  慢推 Ken Burns 覆盖；s5 自动 staging 到 public/

## A/B/C-roll 分层组合模型（分镜抽象升级）
- **A-roll**：IP/主持人，叙事者，画面主体（roll=A）
- **B-roll**：图文卡/移植卡/真实素材，与 A 轮换占画面主体（roll=B，RealFootage 自动升级）
- **C-roll**：正交叠层，与主体自由组合——particles（粒子）/light_sweep（扫光）/grain（颗粒）/
  vignette（暗角）/tint_warm|tint_cool（色调），渲染端 `src/overlays/`
- **纪律（机器闸）**：C-roll ≤2 层；A-roll ≤1 层（IP 镜头干净）；叠层随配方变更自动重算
  （assign_overlay 单一来源，装配与重排共用）

## 新增吸收：手写白板 + IP 角色 + 画风扩容（2026-09-09）

- ✅ **whiteboard-animator**（api 吸收，新能力 `video_render`）
  白板图→手绘动画视频（逐字书写/描边/笔刷填色，CPU 本地）。已装 .venv；
  链路：s4b 任务单生图 → `scripts/s4d_whiteboard.py` → manifest.broll_videos → S5 RealFootage
- ✅ **handraw-style-216**（prompt_pack → image_prompt）：216 画风库，描述型配方+编号参考图
- ✅ **vox-collage**（prompt_pack → image_prompt）：Vox 纸片拼贴 5 段式（风格块逐字复用保跨镜一致）
- ✅ **talkcraft 手写系 4 卡进 BEAT_CARDS**：typewriter-reveal(hook)/hand-drawn-ellipse+scribble-annotation(point)/ink-underline(quote)；
  typewriter-reveal 升级 injectable（TEXT[0/1]→line1/line2）
- ✅ **ARollScene v3 角色姿态状态机**：manifest.ip_poses（assets/ip/{idle,point,confident,shock}.png）
  → 剪纸角色按镜头序轮换姿态+呼吸；无切图降级 flip-book（vox/Kurzgesagt 模式）
- ✅ **卡文字字数闸**（lint.py）：TEXT 条数须等于 registry arities、单条 ≤16 字；content.ts 注入侧同口径截断
- ❌ **ian-xiaohei 下线**：非本人 IP（适配器已删除）。本人 IP（短发 T 恤女孩）素材约定见 assets/ip/README.md
- 🔧 修复：hand_drawn / shotcraft 两适配器因目录搬家失效的源路径

## 新增吸收：五项目评估（2026-09-09 下午）

- ✅ **gc-minimal-zine-poster**（prompt_pack → image_prompt `zine-poster`）：诗性纸感留白海报，固定系统逐字内置
- ✅ **html-ppt-skill**（一次性生成 → theme_tokens）：36 套主题 CSS 解析吸收，主题 10 → 46 套
- ✅ **remotion-bits**（npm 依赖 → C-roll 叠层）：新增 `snow`/`embers` 物理粒子叠层（需手动补装其未声明的 culori）
- ✅ **archify**（api → chart_render `archify`）：架构/流程/时序图 JSON IR → HTML → playwright 截 PNG（tech 类 B-roll）
- ❌ **dads-powerpoint**：产物是 .pptx，与本管线视频产物不符；设计原则与现有 46 主题重叠（日文 DADS 规范留存源目录）
- 📋 **消融实验启用**：`scripts/ablation.py`（特征开关 × 确定性指标，产物 docs/ablation.md）
- 📖 **最终操作规范**：docs/OPERATIONS.md（应用层命令 + 数据流转 + 闸门清单）

## 契约化改造第一批（2026-09-09 晚）

- ✅ #3 数字豁免：S1 protected_tokens（型号/单位/比例不走汉字铁律）+ S2 对齐碎片合并（>2s 强降级）
- ✅ #1 对齐置信度：三指标加权 → high/medium/low；字幕三级降级（high 逐字高亮/medium 词块/low 整句）；align-review.csv 人工复核入口
- ✅ #4 依赖指纹：record_completion/stage_fresh；上游 stale 拒绝下游（--force 豁免）；status freshness 表
- ✅ #5 保底王降级：BEAT_FALLBACK 同族变体确定性轮换（不走关键词配卡）；degraded_groups + 编排表 ⚠️；顺带修 rebalance 格位公式低估 bug
- ✅ #6 卡片视觉回归：card_snapshot.py（CardSnapshot 组合 + PIL diff>2% 告警）
- ✅ #2 跑题排除器骨架：s4_relevance_check.py（CLIP 自动探测/校准 sweep/无模型非阻塞）
- ✅ 影子编译器骨架：visual_ir.schema + visual_compiler.py（纯函数，contrast/point/step 三条映射）+ S3 影子字段 + ablation compiler_on 变体（确定性自检 PASS）
- ✅ STEPS 注入缺口修复：content.ts 补 STEPS（此前 step 卡被选中会渲演示内容）
- 📋 契约适配壳映射表：docs/stage-contracts.md（S1~S6 现有函数→契约接口）

## 2026-09-12 消融驱动的三 outward 吸收（5 项目调研：skills/ FireRed-OpenStoryline / Easel / anything2explainer / AuK）

| 特征 | 来源 | 落点 | 消融旗 |
|---|---|---|---|
| 行边缘密度/死空白带闸 | Easel card-design layout-laws + card_audit | scripts/s6_density_gate.py（s6_qa 建议级挂载）| abl_easel_density_gate |
| 句≤35/字幕块≤16/时长偏差≤15% 节奏闸 | anything2explainer narration-storyboard | pipeline/pace_gate.py（s3_check 建议级挂载）| abl_a2e_pacing_gate |
| 分段字数预算（时长×语速±35%，语速实测自校准） | FireRed-OpenStoryline generate_script | pipeline/pace_gate.shot_budgets | abl_firered_chars_budget |

首轮消融发现（job 2026-0908-ai-vendor-72h）：时长偏差 36%（S1 est 语速 4.2 vs 音色实测 6.6 字/秒，
已把预算改为 timing 实测自校准）；字幕块超限 15 处；密度口径对黑底留白风格偏严（advisory 观测中）。

backlog（未集成，按调研排序）：a2e fx.tsx 图元卡移植（import_cards 通道，M）、AuK-Flash 语音增强/源
分离 backend（需权重，M）、pixel2motion svg_path_audit/probe_motion_continuity 作 overlay QC（S）、
Easel content_guard 出站扫描（S）、Easel beatsync 节拍→入场驱动（S）。
