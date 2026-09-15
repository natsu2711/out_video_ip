# Examples

Load this reference only when a concrete example resolves ambiguity. Reuse the workflow and level of detail, not the topics, wording, metaphors, or palettes.

Each fragment below shows the character-lock language for one form. A full production has six chained clips; the fragments show the first clip's skeleton — later clips repeat the locks, inherit the previous final frame, and pass a named state forward.

## Form A — girl（短发 T 恤女孩）

### Required setup exchange

Assistant: “请确认：形象用短发 T 恤女孩（我会附上三张参考图）？画幅（16:9 / 9:16 / 1:1）？明暗主题？”
User: “9:16，浅色主题，用女孩。”

### Phase A header（节选）

**核心观点：** 内容做不下去，往往不是没想法，而是素材和想法散落各处没有闭环。
**形象：** 短发 T 恤女孩；她在片里是"整理者"——亲自搬运散落的素材块、接线、点亮闭环。
**画幅与主题：** 9:16 竖屏、浅色主题（纯白画布、深色线稿）。
**强调色（角色色之外）：** 鲜明警示橙（散乱与断点）、电光蓝（连接与自动化）、温暖成长绿（完成闭环）。

### Clip 1 prompt（节选自完整输出，演示语言密度）

```text
Create an approximately 10-second 9:16 vertical 2D kinetic motion-graphics clip targeting 720p at 24 FPS with synchronized audio.

Use a completely flat, uniform, digitally pure-white canvas with dark line art; no gray tint, no texture, no gradients, no shadows, no three-dimensional background depth. The only character is the identical young woman from the attached reference images: short black bob hair with uneven bangs, calm minimal facial features, loose navy-purple crew-neck T-shirt with a small chest print, dark trousers, clean thin line art, stable proportions. The references define her identity only — pose, expression, and staging come from this prompt, never from the reference images. She is the sole actor. Use vivid warning orange for scattered fragments and electric blue for connections as accents; her own hair and outfit colors stay fixed. Treat these ordinary color names as visual art direction only. Compose with foreground/background depth, vertical reveals, and interface-safe space. Generate no visible words, letters, numbers, technical annotations, captions, subtitles, or interface text; keep every card icon-only.

First frame: she stands at the bottom of a tall frame while paper squares (warning-orange outlines) fall past her from above.

[0–3s] A square bounces off her head; she looks up, rolls up her sleeves, and catches the next one mid-air.
[3–7s] She stacks the caught squares into a wobbling tower, grabs an electric-blue line, and ties the tower to an anchor block so it stops wobbling.
[7–10s] More squares rain down; she splits the blue line into a web that catches every falling square. End with the web spanning the full width for Clip 2.

Audio-only dialogue, exactly once: “Ideas are not the bottleneck. Everything you have collected is just waiting for one connective move.” Do not display or transcribe the dialogue visually.

Use the same bright, energetic adult female narrator with natural American English. Deliver with knowing warmth. Use light percussion with paper taps, a soft catch, a stretching elastic tone, and a rising web-hum; keep the voice dominant.

Do not generate photorealism, 3D rendering, changes to her hair, outfit, or chest print, chibi proportions, exaggerated cartoon expressions, a second lead character, unstable proportions, unexplained colors, visible writing, technical color notation, captions, subtitles, logos, or watermarks. Do not alter, omit, repeat, reorder, or add dialogue.
```

## Form B — stickman（火柴人）

### Required setup exchange

Assistant: “请选择视频尺寸（16:9、9:16 或 1:1），以及主题（白底黑火柴人或黑底白火柴人）。”
User: “16:9，黑底白火柴人。”

### Clip 1 prompt（节选，演示线稿锁语言）

```text
Create an approximately 10-second 16:9 horizontal 2D kinetic motion-graphics clip targeting 720p at 24 FPS with synchronized audio.

Use a pure black background and one minimalist white stick figure, Stick Figure A, slightly left of center. Lock a hollow circular head, no face, no hair, no clothing, no filled body, stable human-like proportions, and uniform medium white line weight. Use only saturated anxiety violet, vivid danger red, and warm action gold as accents; this clip primarily uses violet. Treat these ordinary color names as visual art direction only. Compose across left, center, and right with deliberate negative space on the right. Generate no visible words, letters, numbers, technical annotations, captions, subtitles, or interface text; keep every graphic icon-only.

First frame: A stands alone with lowered shoulders in empty black space.

[0–3s] Slowly push toward A. A tiny violet thought dot appears above and to the right of the head, pulses electrically, and draws A's attention.
[3–7s] The dot splits into hundreds of violet lines that form a huge rotating tangle across the right half. An icon-only white clock with unmarked hands spins backward in the upper-right, an icon-only white battery drains in the lower-right, and horizontal pressure waves bend the floor toward A.
[7–10s] The tangle expands and sweeps from right to left. A trembles as the camera accelerates into the rotating lines. End with violet lines filling the entire frame for Clip 2.

Audio-only dialogue, exactly once: “Do you ever feel exhausted before you have even begun?” Do not display or transcribe the dialogue visually.

Use the same bright, energetic adult female narrator with natural American English. Deliver this opening with urgent empathy. Use restrained minor-key piano around 72 BPM, a clock tick, electrical pulse, and rising low rumble; keep the voice dominant.

Do not generate photorealism, unwanted 3D rendering, faces, hair, clothing, filled bodies, extra limbs, malformed anatomy, disconnected lines, changed proportions, broken or changing line weight, inverted theme colors, unexplained colors, unintended characters, unrelated spectacle, visible writing, technical color notation, palette labels, interface copy, captions, subtitles, logos, or watermarks. Do not alter, omit, repeat, reorder, or add dialogue.
```

## Storyboard table pattern（两种形态通用）

| 时间 | 叙事目的 | 角色场景（她/火柴人做什么） | 动作、镜头与转场 | English VO | 中文参考 | BGM / SFX |
|---|---|---|---|---|---|---|

每行必须写出角色的核心动作。衔接：上一行的末帧状态 = 下一行的首帧状态，逐对点名。
