# personal-ip-video-director

把一篇文稿/笔记/话题，变成一支一分钟的个人 IP 短视频（六段 × 10 秒 Gemini Omni Flash 提示词包）。
主角固定为**你自己的 IP 形象**，两种形态任选：

- **短发 T 恤女孩（默认）**——本项目原创 IP：齐耳黑短发、深蓝紫宽松 T 恤、白底手绘扁平风。参考图内置于 skill（`skills/directing-personal-ip-videos/assets/girl-*.jpg`），生成时随请求附带。
- **火柴人**——极简线稿形态（空心圆头、均匀线宽），适合抽象概念或不想露人物形象的选题。

## 来源与改造说明

- 基座：[stickman-video-director](../../../other/1other_video/stickman-video-director)（保留其完整工作流：Setup Gate → Phase A 导演预案 → 人工确认 → Phase B 六条 Omni Flash 提示词 → 缝合/音频连续性说明，以及配色、口播、负向约束等全部纪律）。
- 角色规范写法参照 [ian-xiaohei-illustrations](../../../other/2other_pic/ian-xiaohei-illustrations) 的 `xiaohei-ip.md` / `style-dna.md`（角色定义/外形/性格/职责/禁止/判断标准）。
- 改造方法遵循「保留它怎么工作，替换它长什么样」：工作流原样保留，火柴人单一角色 → 双形态个人 IP，并新增两条硬规则：
  1. **角色必须是动作主体**——每行分镜的核心动作由角色亲手完成；去掉角色画面仍成立即为不合格构图。
  2. **参考图只锁身份**——发型/服装/画风/配色，不锁姿势和背景；姿势按分镜重新设计。
- **默认节奏**：口播短句、动词开头；画面变化保持每 2–3 秒一次；BGM 跟随内容情绪。
  用户点名其他语气（如沉稳、舒缓）时按其指定执行。

## 用法

```
Use personal-ip-video-director
把下面这篇内容做成一分钟视频。形象用短发 T 恤女孩，9:16，浅色主题。
{粘贴文稿}
```

流程上它会先向你确认四件套（文稿 / 形态 / 画幅 / 明暗主题），缺什么一次性问齐；
先给 Phase A 导演预案（含六行分镜表）等你确认，确认后才产出六条 Omni Flash 提示词。

## 换 IP / 调风格

- 参考图在 `skills/directing-personal-ip-videos/assets/`，直接替换同名文件即可换形象；
  外形锁文字在 `references/ip-character.md` 同步改（发型/服装/画风三处）。
- 调试循环建议：生成 1 张测试 → 说不满意在哪 → **同时改 skill 和重测**（把反馈写回
  `ip-character.md` 的禁止/判断标准，而不是只改当前这张图）。

## 与 out_video-ip 管线的关系

同一套 IP 资产：`assets/ip/`（姿态池）同时供渲染引擎 ARollScene（剪纸角色状态机）和本 skill 使用。
想在正片里出这个女孩 → 跑 s4_manifest 把姿态登记进 manifest；想做 Omni Flash 短视频 → 用本 skill。

## 文件结构

```
personal-ip-video-director/
├── README.md                                ← 本文件
└── skills/directing-personal-ip-videos/
    ├── SKILL.md                             ← 入口：双形态、Setup Gate、输出/修订规则
    ├── assets/girl-{wave,think,calm}.jpg    ← 形态 A 参考图（换 IP 从这里换）
    └── references/
        ├── ip-character.md                  ← 角色规范（外形锁/性格/职责/禁止/判断标准）
        ├── storyboard-template.md           ← Phase A 契约（六行分镜 + 角色动作强制）
        ├── omni-flash-prompt-contract.md    ← Phase B 契约（角色锁按形态分两套）
        └── examples.md                      ← 两种形态的提示词语言示例
```
