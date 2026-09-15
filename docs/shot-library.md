# 内置镜头组件库（recipe_ref 词汇表 · 首批 9 个）

所有组件位于 `render-engine/src/shots/`，接口统一（props: shot/timing/assets/tokens）。
组件内禁止硬编码时间、颜色、文案——一切来自 props。

| 组件 | 类型 | 适用结构 | 关键动效 |
|---|---|---|---|
| `TitleCard` | B/text | 开场大字冲击（hook） | 关键词砸入 + 相机脉冲 + 底色闪变 |
| `QuoteCard` | B/text | 金句/主张/结论强调 | 整句浮现 → 关键词锚点强调 → 落幅定格 |
| `ChapterCard` | B/text | 章节卡（第一步/第二步…） | 序号放大 + 标题推入 + 分隔线扫过 |
| `CompareCard` | B/graphic | 左右对比 / VS / 正反 | 左右两栏先后入场 → 中间 VS 冲突 → 落幅 |
| `StepsCard` | B/graphic | 步骤展开（1→2→3） | 步骤逐项出现 + 连接线生长 + 当前项高亮 |
| `TransformCard` | B/graphic | A→B 转变（零散→结构/月→小时） | 左态呈现 → 压缩/汇聚动画 → 右态爆发 |
| `ListGrid` | B/graphic | 多项并列（三对比/清单） | 网格逐格点亮 + 逐项编号 |
| `ARollScene` | A | IP 小剧场（host/protagonist/supporting/pov 四视角） | 分层静帧 + CameraRig 运镜 + 呼吸 + 重音脉冲 |
| `EndingCard` | B/text | CTA 收尾 | 口号浮现 + 引导箭头 + 定格 |

## 动效系统（所有组件可用的全局层）
- `CameraRig`：镜头级连续相机曲线（缓动 scale/translate/rotate），重音字帧 ±3f 冲击脉冲
- `Idle`：元素呼吸（sin ±0.5%），杜绝静止帧
- `Environment`：呼吸 vignette + 分幕色温（hook 冷 → 正文中性 → CTA 暖）
- `KaraokeLine`：底部素排字幕（整句硬现硬走，不抢画面）

## 规范来源
- 层矩阵/七层反 PPT 系统：video-talkcraft（缩配为首批 4 系统，后续按卡扩充）
- 运动承接转场：video-shotcraft 六式（push-through/whip-pan/震切/粒子溶接…M5+ 逐步内置）
