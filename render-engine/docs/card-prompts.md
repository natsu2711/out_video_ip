# 资产卡工作提示词（v1，2026-09-14）

本项目资产卡的唯一权威规范。以下三段提示词分别用于：**A 新建卡 / B 蒸馏别人的卡 / C 修复现有的卡**。
直接整段复制给 AI（我或任何 agent），附上具体卡名/来源即可。

---

## 核心契约（三段提示词共用，AI 必须先读）

```
【资产卡契约 · out_video-ip】

一张资产卡 = 动效骨架（锁死，永不改）+ 内容槽位（全部可注入）。

1. 文件：render-engine/src/cards/card-<slug>.tsx
   注册：render-engine/src/cards/registry.json 加条目：
   {slug, component, tier: "injectable", arities: {TEXT: n, SLOTS: n},
    durationInFrames, category3: "narrative"|"visual", desc, sourceFile}

2. 注入头（每个卡文件必须）：
   const __INJ__: any = (globalThis as any).__OUTVIDEO_CARD__ ?? {};

3. 内容槽位两类（都要有，缺一即不合格）：
   - 文字槽 __INJ__.TEXT / TEXT2 / TEXT3：string[]。写法（保留原默认值兜底）：
     const ITEMS = ((__INJ__.TEXT as string[])?.length ? (__INJ__.TEXT as string[]) : ["默认文案A", "默认文案B"]);
     JSX 里硬编码标题（如 <Title text="HELLO"/>）必须改为：
     <Title text={((__INJ__.TEXT as string[])?.[0] ?? "HELLO")} />
   - 图片/面板槽 __INJ__.SLOTS：{text?, image?}[]。wireframe 面板/空白矩形/占位图
     必须抽成槽位，写法（图片支持 http URL 和 staticFile 相对路径，兜底原骨架）：
     const SLOT = (__INJ__.SLOTS as any[])?.[i];
     {SLOT?.image
       ? <img src={/^https?:/.test(SLOT.image) ? SLOT.image : staticFile(SLOT.image)}
              style={{width: W, height: H, objectFit: 'cover'}}/>
       : <原骨架/>}
     {SLOT?.text && <div …>{SLOT.text}</div>}   // 槽也可只填文字

4. 尺寸契约：卡组件输出原始设计尺寸原稿（不自带缩放）。
   shotcraft 系=1920×1080；talkcraft 系=960×540。宿主按 designSizeOf(slug) 缩放一次。

5. 动效骨架禁止改：所有 interpolate/Easing/seg 时间轴、布局、颜色逻辑原样保留。
   只允许把"写死的演示内容"（灰条、假图表、Feature A、wireframe）换成上面的槽位读取。

6. 完成判据（AI 必须逐条自验后才算完成）：
   a. 不传 TEXT/SLOTS 渲染 = 原卡画面（默认值兜底生效）
   b. 传 {"TEXT":["我的文案"]} 渲染 = 画面出现"我的文案"，动效不变
   c. 传 {"SLOTS":[{"image":"…"}]} 渲染 = 面板显示该图，动效不变
   d. esbuild 语法预检通过：npx esbuild card-x.tsx --loader:.tsx=tsx --outfile=/dev/null
   e. 渲染验证：cd render-engine && npx remotion still src/index.ts CardSnapshot \
      /tmp/v.png --props '{"slug":"x","TEXT":["测试"],"SLOTS":[{"image":"…"}]}' --frame=39
   f. registry 条目 tier=injectable + arities 齐全
```

---

## 提示词 A：新建资产卡

```
读 render-engine/docs/card-prompts.md 的【资产卡契约】，新建一张卡：

卡名（slug）：<英文短名>
用途：<一句话：这个卡表达什么内容/什么动效>
设计尺寸：<1920×1080（默认）或 960×540>
时长：<帧数 @30fps>
分类：<narrative 叙事与展示 | visual 运镜与视觉特效>

画面内容：
- 动效骨架：<描述动画：什么元素、几拍、什么缓动、何时定格>
- 文字槽：<几条，各显示在哪、多大>
- 图片/面板槽：<几格，各在哪个位置、多大尺寸>

参考：render-engine/src/cards/card-sc-floating-glossy-label-pills.tsx（槽位样板）
完成后按契约第 6 条逐项自验并贴验证截图。
```

## 提示词 B：蒸馏别人的卡（把外部 tsx 改造成本项目卡）

```
读 render-engine/docs/card-prompts.md 的【资产卡契约】，蒸馏这张外部卡：

来源文件：<外部 tsx 路径>
slug：<sc-来源名 或自定义>

步骤：
1. 先读该卡的 md 文档（若有，通常在 video-shotcraft/references/shots/<分类>/<名>.md），
   按文档识别三类信息：
   - "占位/wireframe/dummy"描述 → 这些是槽位改造点
   - 参数表里的"内容坐标系 330×255"之类 → 槽位容器的宽高
   - 动效描述（几拍/缓动/位移量） → 骨架，锁死不动
2. 复制到 render-engine/src/cards/card-<slug>.tsx，改 import：
   - 外部图片 → ./_sc_assets/（文件先拷过去）
   - 外部共享组件（VerticalTicker/ClipCard 等）→ ./_sc_assets/<名>
   - 额外的 @remotion/* 包 → 先 npm install @remotion/<包>@4.0.216
3. 按契约第 3 条做 Slot Replacement：所有硬编码演示内容 → TEXT/SLOTS 槽位
4. 登记 registry（tier=injectable，arities 如实标注 TEXT/SLOTS 数量）
5. 按契约第 6 条逐项自验（必须渲染验证传参与不传参两种）
```

## 提示词 C：修复现有卡（显示不对 / 内容改不了）

```
读 render-engine/docs/card-prompts.md 的【资产卡契约】，修复这张卡：

卡名：<slug>（文件 render-engine/src/cards/card-<slug>.tsx）
症状：<具体现象，如：画面只显示四分之一 / 文字改了没反应 / 渲染报错 / 大片空白>

排查顺序（按命中率）：
1. 大片空白/半截 → 尺寸契约违规（卡内自带缩放 or 设计尺寸与 designSizeOf 不符）
2. 文字改不动 → 槽位没接：搜硬编码字符串，按契约第 3 条接 __INJ__
3. 图片改不动 → wireframe 没抽槽：按 md 文档把面板抽成 SLOTS
4. 渲染报错 → esbuild 预检定位行号；常见：import 路径（./_sc_assets）、
   staticFile 未 import、__INJ__ 头缺失
5. 修完必须按契约第 6 条全量自验（不许只验不改的那部分）
```

---

## 已验证的样板（AI 参考实现）

| 样板 | 槽位形态 |
|---|---|
| `card-sc-floating-glossy-label-pills` | 4 面板截图槽（330×255）+ 4 胶囊文字槽，wireframe→截图整块替换 |
| `card-sc-cel-flash-stomp` | TitleBlock 文字槽（标题+换帧词组） |
| `card-ppt-steps` / `card-ppt-compare` | 纯文字槽（STEPS/TEXT），PPT 动效 |
| `card-ip-emote` | 文字槽 + CONFIG.image（IP 表情图可换） |

## 常见坑（给 AI 的负面清单）

- 禁止在卡内加 scale 壳/transform 缩放（宿主负责，双重缩放=画面剩 1/4，实测踩坑）
- 禁止删默认值兜底（不传参必须能渲染原画面）
- wireframe 灰条**不许保留在槽位路径上**——有 image 就整块替换，没有才画灰条
- registry 漏登记 = 资产库看不到；arities 撒谎 = 编辑器槽位数不对
- SLOTS 是对象数组（{text?,image?}），不要当 string[] 处理
