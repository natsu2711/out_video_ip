# S1 脚本结构化规则（agent 执行，产出 script.json）

## 输入
`story.md`（原始文案）

## 铁律
1. **保留原文措辞**——只做口播适配，不改写内容（同 lanshu 原则：polish without changing factual meaning silently）
2. **数字一律汉字写法**（对齐按文本逐字锚定，"100次"无法与"一百次"的读音对位——来自 talkcraft 实测坑）
3. 拉丁人名/品牌转中文写法（如 yangzengning → 杨振宁），原词记入 note
4. 按完整句子拆段（保留句末标点），单段 ≤ 40 字；超长复句拆为多段
5. 每段打两个标记：
   - `beat`：hook / point / step / case / contrast / quote / cta
   - `visual_hint`：scene(可画场景) / graphic(可图形化) / quote(金句) / real(需真实素材) / none

## 输出
`script.json`，通过 `schemas/script.schema.json` 校验；meta 记录 hook 一句话、closing 一句话、总字数、预估时长（字数/4.2 字每秒）。

## 后续约束
- S2 TTS 整段合成直接吃本文件全部 text（按行拼接）
- S3 编排以本文件 segment 为最小语义单元，用 timing.json 字级锚点切镜头
