# S3 视觉编排规则（agent 执行，产出 storyboard.json）

## 输入
`script.json`（语义段）+ `timing.json`（时间真相源，句级 t000..tNNN + 字级锚点）

## 拆镜流程（导演视角）
1. 先通读全文逻辑，划分叙事幕（hook → 问题 → 转折 → 三步法 → 总结 CTA）
2. 按语义段组合镜头：一个镜头覆盖 1~3 个相邻 timing 段
3. 每个镜头先回答五问（来自方法论）：
   - 这一段观众最需要理解什么？（intent）
   - 什么画面让这句话更具体？（visual）
   - 画面主体发生什么变化？（motion，按旁白顺序 1~3 拍，可锚定字级时间）
   - 镜头最后停在什么结果上？
   - 如何承接上一镜？（transition_in）

## 分类决策
- `roll`: A（IP 小剧场/人物） | B（信息图形）
- 判断标准：讲到具体知识/结构/数据 → B；情绪/经历/情境/对话感 → A
- B 细分：`b_type`: graphic（无素材图形化）| text（金句/章节/主张）| real（需真实素材，标 assets_needed）
- A 细分：`view_angle`: host（主持人正对镜头）| protagonist（主角在场景做动作）| supporting（配角补充）| pov（第一人称视角）

## 节奏铁律（s3_check.py 强制）
1. 连续同 roll 镜头 ≤ 3
2. A-roll 四视角相邻镜头不重复同一视角
3. text 类 B-roll 不连续超过 2 个
4. 镜头时长 3~15s；>8s 的镜头 motion 必须有 ≥2 拍
5. hook 5s 内必须有第一个视觉冲击镜头

## 配方绑定铁律（方差第一锁）
每个镜头 `recipe_ref` 必填，取值：
- `local:shots/<组件名>` —— render-engine 内置镜头组件（见 docs/shot-library.md）
- `shotcraft:<卡片名>` / `talkcraft:<卡片名>` —— 外部配方卡骨架（M3+ 逐步内置化）
`visual` 与 `motion` 字段是对该配方在此镜头的实例化描述（主体文案/元素/节拍），不是自由创作。

## 输出
`storyboard.json`（过 schema 校验）→ `s3_check.py` 节奏校验 → `s3_table.py` 渲染 Markdown 编排表 → **闸门：人工审阅后放行**
