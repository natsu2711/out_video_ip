# anything2explainer 对比吸收（2026-09-10）

对比对象：`/Users/bainazi/Documents/outtt/other/1other_video/anything2explainer`。
结论：其 agent 编排和确认闸描述很完整，但本项目的 schema、状态机、适配器注册表、
确定性重跑、S3 编排闸和 S6 机器验收更强。因此不整包吸收流程，只移植可复算的视觉 QA。

## 已吸收

### 1. 逐镜视觉量化

- 新增：`scripts/s6_frame_metrics.py`
- 触发：`s6_qa.py` 每次自动执行；也可单独重跑：
  `.venv/bin/python scripts/s6_frame_metrics.py jobs/<job> --samples 3`
- 产物：
  - `qa/frame-metrics-report.json`
  - `qa/frame-metrics-report.md`
  - `qa/metric-frames/SXXX-NN.jpg`

指标来自 anything2explainer 的构图/光/运动量化思路，并按本项目改造：

| 指标 | 作用 | 建议阈 |
|---|---|---|
| `hero_px_median` | 主体/标题等效尺寸，避免小字小图形撑场 | <140px 警告 |
| `empty_ratio` | 主体过小且缺少大面积柔光的样本比例 | >34% 警告 |
| `glow_px_median` | 焦点光/颜色柔光面积，暴露灰暗焦点 | <800px² 警告 |
| `clutter_score_median` | 对象数 + 背景碎屑合成杂讯 | ≥65 警告 |
| `static_seconds` | 相邻采样的最低画面运动 | >1.5s 警告 |

该报告 `blocking:false`，不会改变原 7 条 S6 硬闸或 pipeline 退出码。原 7 条
仍负责冻结、响度、时长、A-roll 存在性和字幕存在性；视觉美学先做建议级灰度，
等更多样片校准后再决定是否把个别指标升级为硬闸。

画布不硬编码：尺寸从 `out/video-final.mp4` 探测，内容区按比例裁掉安全边和字幕带；
16:9 与 9:16 job 都可使用。

### 2. 真 contact sheet

- `qa/contact-sheet.html` 是人工复查入口，每个抽帧带时间、镜号、配方、VO 和画面描述。
- `qa/contact-sheet.jpg` 由多帧缩略图拼成，保留为离线/预览 fallback。
- 不再把最后一帧误用为 contact sheet。

## 暂不吸收

| 来源能力 | 处理 | 原因 |
|---|---|---|
| 时长/语言确认闸 | 不加 | 本项目由文稿和 S2 timing 契约推导，S0 已建 job。 |
| 先审全稿旁白再进画面 | 延后评估 | 当前 S1/S2/S3 有 schema 和字级对齐；加一道“旁白冻结稿”需要改状态机和 gate 语义。 |
| TTS 选择确认 | 不加 | S2 backend/voice 已在 `project.json` 固化，可重跑；交互选型更适合初始化工具，不宜嵌进自动 pipeline。 |
| 首 30 秒风格 pilot | 延后评估 | 有价值，但会引入新渲染产物和指纹；先以 contact sheet + frame metrics 暴露风格风险。 |
| 直接复制其 720p 阈值 | 拒绝 | 其规则面向 1280x720 幕底；本项目已有 16:9 样本和 9:16 新建默认，必须按画布缩放。 |

## 验证

样片：`jobs/2026-0908-ai-vendor-72h`。

```bash
.venv/bin/python -m py_compile scripts/s6_frame_metrics.py scripts/s6_qa.py
.venv/bin/python scripts/s6_qa.py jobs/2026-0908-ai-vendor-72h
```

结果：原 7 条硬闸 `ALL PASS`；视觉建议为 `pass 11 / warn 5 / shots 16`。
警告集中在低柔光或结尾主体偏小，尚未阻断 S6。人工复查打开：

```bash
open jobs/2026-0908-ai-vendor-72h/qa/contact-sheet.html
```
