# IP Studio —— out_video-ip 可视化工作台

把整条「故事文稿 → 成片」流水线（S0~S6）拆成**每个环节都可查看、可验证、可修改**的本地 Web 界面。
界面交互逻辑参照 `overlay-studio`（三栏布局：列表 | 实时画布+时间轴 | schema 驱动参数面板）。

## 启动

```bash
bash studio/start.sh          # 一键启动（后端 8321 + 前端 5188，自动开浏览器）
```

或分步：

```bash
# 1) 后端（项目 venv 内，FastAPI 只读/执行薄封装）
.venv/bin/python -m uvicorn studio.server.app:app --port 8321

# 2) 前端（Vite dev，已配 /api 代理与 render-engine/public 静态目录）
cd studio/web && npm install && ./node_modules/.bin/vite --port 5188
```

打开 http://localhost:5188 。**预览画布与 CLI 渲染共用同一套 Remotion 组件**（`render-engine/src/compositions/ShotRenderer.tsx`），
改什么立即看到什么，`remotion render` 的结果与预览一致。

## 九个页面 → 七个环节的映射

| 页面 | 对应环节 | 能做什么 |
|---|---|---|
| 流水线 | 全局 | s0~s6 状态卡（完成/失败/待闸门/stale 指纹）、产物存在性、单阶段运行/强制重跑、闸门放行/驳回、新建作业、实时日志浮窗 |
| 编排 | S3 闸门① | **核心编辑器**：镜头列表 + 实时画布预览 + **右侧双页签「镜头属性 / 资产库」**；时间轴拖拽边界=重新分组 seg_ids；**游标检查器**（点时间轴任意秒 → 该时刻的镜头/段落/命中词/活动图层/附近音效，支持从此处播/✂拆分/♪加音效/🎬换效果/➕图层）；**图层栈 + 剪映式编辑**（画布 Gizmo 拖动/缩放、时间轴图层轨拖时间窗、面板数值双向同步）；**效果选择器**（9 类效果源一键换，见下「换效果=脚本链」）；客户端 lint + 服务端校验；键盘 scrub |
| 资产库 | 全局资产 | **浏览与试穿**（与编排右页签同源，全 10 类 + 大图预览）+ **蒸馏外部项目/新增**：登记蒸馏源（overlay-studio / vibe_motion_skills / remotion-dev / shotcraft…）→ 扫描候选（tsx 特效/资产卡/渲染脚本/方法论 md）→ 勾选吸收（复制进 assets/distill/ + 登记 docs/distill-backlog.json 移植队列），全程文件操作无 LLM |
| 资产库 | 全局资产 | **先回答「我到底有哪些」**：总览实时扫描全项目资产（约 600 项）；10+ 类别可搜索可预览——移植卡 79 / 自研组件 16 / 氛围叠层 8 / 入场动效 5 / **音效 33**（11 家族、试听、加 cue）/ **画风库 235**（handraw-style-216 带编号参考图）/ **方法论卡 152** / 主题 46 / **IP 姿态 21** / 字体排印；动效四类用当前镜头口播**实时试穿**并一键应用；**蒸馏外部项目/新增**（见上） |
| 脚本 | S1 | 分段文本/beat/visual_hint 编辑，保护 token 只读展示，保存后下游自动标 stale |
| 配音 | S2 | vo.wav 播放 + 逐段置信度/匹配分/词级时间轴（保护词高亮、点击 seek） |
| 素材 | S4 | manifest 缩略图浏览（IP/场景图/B-roll 视频 hover 播放/截图）、生图任务单、相关性打分；工具按钮：重建 manifest / 图任务单 / 图库 dry-run / ComfyUI 生图（支持 `--only S00X`）/ CLIP 打分；**上传替换**单镜素材并自动重新 staging |
| 渲染 | S5 | preflight、逐镜重渲、全量渲染、props/segment 在盘状态、video-silent 预览与下载 |
| 验收 | S6 | QA 规则 R1~R5 结果表、音效可听度、联络表、帧指标、成片播放/下载 |
| 主题 | 全局 | 46 套主题一键试切（画布即时变色）、bg/anchor/text 手动微调、「保存并应用」跑 apply_theme.py |

通用：⌘S 保存（schema 校验，失败拒绝写盘并给出具体错误）、⌘Z / ⇧⌘Z 撤销重做（拖动/滑杆自动合并）、作业切换记住上次选择。

## 换效果 = 工程化脚本链（不走 LLM）

编排页的「换效果/加图层」走 `POST /api/job/{id}/apply-effect`：**改 JSON + 调对应脚本，全程确定性**。
给了关键词/画风/步骤，就不存在模型随机性——同样的输入永远得到同样的产物。

| 效果 | 脚本链 | 产物去向 |
|---|---|---|
| 图表（workflow） | `tools.py build_workflow_ir`（步骤→schema v2 IR）→ archify → PNG | `assets/screenshots/{shot}.png` → S5 自动 ScreenshotCard |
| 图表（原生） | 直接传 archify `{type, ir}`（architecture/sequence/dataflow/lifecycle） | 同上 |
| 手绘图 | excalidraw 元素 → render_excalidraw.py → PNG（其模板依赖 CDN，不稳时用图表/生图替代） | 同上 |
| AI 生图 | `tools.py gen_image_brief`（adapter.produce 纯模板）→ 写 image_briefs → `s4e --only {shot}` | `assets/broll/{shot}.png`（可续接白板动画） |
| 白板动画 | `tools.py whiteboard_one`（whiteboard-animator 单镜版） | `assets/broll_videos/{shot}.mp4` → RealFootage |
| 图库视频 | `tools.py stock_one`（关键词显式传入，跳过 LLM 翻译） | 同上 |
| 上传 | `/upload-asset`（图→screenshots / 视频→broll_videos） | 主画面自动切换或作图层 |
| 网页实拍 | `s4_capture screenshot/record {url}` | screenshots → ScreenshotCard / 录屏 → RealFootage |
| 配方/氛围/音效 | 纯 storyboard JSON 写入（.bak + schema 校验） | 立即在预览生效 |

## 分层（shot.layers 契约）

主画面配方之外，每镜可叠多层（`storyboard.json` 的 `shot.layers[]`，数组序 = z 序）：

```json
{"id":"L2","kind":"card","ref":"number-counter","in_ms":500,"out_ms":3000,
 "x":0.72,"y":0.35,"scale":1,"opacity":1,"presentation":"rise_fade",
 "config":{"TEXT":["三千万订阅","72小时"]}}
```

- `kind`: `card`（移植卡画中画）| `overlay`（氛围）| `text`（大字标注）| `media_image` | `media_video`
- 时间窗 `in_ms/out_ms` 为镜头内相对毫秒（借鉴 slidev `v-click=[4,5]` 的窗口语义）；`presentation` 入场：none/rise_fade/slam_in/blur_focus
- 渲染端 `render-engine/src/layers/LayerHost.tsx`：层在主画面之上、氛围/字幕之下，**不进相机变换**（位置稳定）；
  卡片内容注入与主画面同机制（CLI=webpack 求值 / Studio=Vite 动态求值；同一 slug 的内容在单进程内共享——同镜避免重复选同一张卡）
- **剪映式编辑**（编排页）：画布上点选图层 → Gizmo 拖动位置 / 拖角缩放；时间轴上每层一条轨道条
  （拖左缘=入点、右缘=出点、中部=平移）；右侧面板数值双向同步。选镜后预览自动跳 35% 代表帧
  （移植卡多为冲击式入场，f0 近乎空白易误判为"文字看不到"——资产库卡预览同理跳 70% 帧）
- 字幕安全区（video-use 规则）：card/media 图层 y 缺省 0.62（避开竖屏底部 ~30% 字幕带）
- 画面稳定：层入场确定性 ramp；静态画面由全局 Ken Burns + StaticNoise 兜底，不触发 freezedetect
- **EDL 互操作**（video-use 方言）：`GET /api/job/{id}/edl` 导出剪辑决策列表（每镜一个 range，
  图层按时间窗换算为 overlays + 输出时间轴偏移），供外部 ffmpeg 旁路混剪/审阅
- 后续集成位（调研结论）：@remotion/transitions 做镜间过渡、MoneyPrinterTurbo 的字幕分区/底板规格、Easel 节拍→入场驱动——接口都已预留（层时间窗 + 入场枚举）

## 架构

```
studio/
├── start.sh              # 一键启动
├── server/
│   ├── app.py            # FastAPI：/api/jobs /snapshot /artifact(读=GET,写=PUT+jsonschema 校验+.bak)
│   │                     #   /run /gate /tool /stage-assets /render-still /render-shot /render-status
│   │                     #   /upload-asset /file /project-file /external-file(参考图白名单)
│   │                     #   /inventory(全项目资产盘点) /meta /runs(日志轮询)
│   └── tools.py          # 单镜重渲 / 单帧静帧（复用 s5_render 的 props 组装与 staging）
└── web/                  # Vite + React 18 + TS（无 UI 库，暗色工作台）
    ├── vite.config.ts    # dedupe react/remotion 单实例；publicDir=render-engine/public；/api 代理
    └── src/
        ├── preview/      # StudioPlayer(@remotion/player 驱动 ShotRenderer)
        │                 # StudioCardHost(Vite 版卡宿主) cardLoader(内容注入+哈希换链重求值)
        ├── store.tsx     # 草稿/撤销重做/保存/运行器轮询
        ├── ui.tsx        # schema 驱动控件（range/text/select/toggle/color/textlist/json）
        └── views/        # pipeline / storyboard / library / script / timing / assets / render / qa / theme
```

关键机制：

- **预览=渲染**：`ShotComposition` 只剩 `getInputProps()` 壳，主体在 `ShotRenderer`（props 传入）。
  CLI 渲染传 webpack 版 CardHost，Studio 传 Vite 版（互不影响，`remotion render` 输出不变）。
- **卡内容注入**：卡在模块求值时读 `globalThis.__OUTVIDEO_CARD__`。Studio 用「注入 → 动态 import（URL 带内容哈希）→ 串行队列」
  实现内容变更即重新求值；内容不变则复用模块，不闪不抖。
- **时间轴重分组**：镜头时间唯一真相源是 timing.json（契约禁手改）。拖动边界改的是镜头对 `seg_ids` 的划分，
  保存后 s3_check 会重算时间并做节奏校验——与命令行行为一致。
- **指纹可视化**：后端读 state.json + `pipeline.state.stage_fresh`，产物/输入一变即显示 stale，杜绝在过期产物上继续生产。

## 注意

- s2（TTS）依赖 index-tts 独立 venv、s4e 依赖本地 ComfyUI(8188)、s4c 需要 Pexels/Pixabay key——按钮照常触发，失败会在日志浮窗显示原因。
- 前端需以 dev 模式跑（卡片动态加载用的 `/@fs` 求值是 dev 能力）；后端/前端端口写死在 vite.config.ts 与 start.sh。
