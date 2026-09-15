# Omni Flash Production Prompt Contract

Use this contract only after explicit approval of the current Phase A.

## Production package order

Deliver these sections in order:

1. Global continuity block
2. Six standalone English prompts
3. Stitching guide
4. Voice and music continuity note

## Global continuity block

State the current aspect ratio, theme polarity, character form and its identity locks（`girl`：发型/服装/画风/参考图已附；`stickman`：线稿规格）, three-color palette in ordinary descriptive language, narrator identity, audio arc, and continuity strategy. Treat this block as a review summary; each prompt still repeats all critical locks.

## Standalone prompt order

Write every prompt in this order:

1. Output specification: approximately ten seconds, chosen aspect ratio, 720p target, 24 FPS, synchronized audio
2. Background and base line-art polarity; for light mode, use a flat, uniform, digitally pure-white canvas with no shading or three-dimensional surface treatment
3. Character lock, by form:
   - `stickman`: hollow circular head, no face, no clothing, no filled body, stable proportions, uniform medium line weight
   - `girl`: 2D hand-drawn flat illustration of the identical young woman in every clip — short black bob hair with uneven bangs, calm minimal facial features, loose navy-purple crew-neck T-shirt with a small chest print, dark trousers, clean thin line art, stable proportions; the attached reference images define identity only, never pose or background
4. Three-color palette, expressed only with ordinary color names, and semantic roles（girl 形态注明角色自身颜色不计入）
5. Composition strategy for the chosen ratio
6. First-frame state inherited from the previous clip
7. `[0–3s]`, `[3–7s]`, and `[7–10s]` visual beats, each driven by the character's action
8. Exact audio-only English dialogue in quotation marks
9. Identical narrator description, emotion, and delivery
10. BGM, synchronized SFX, and voice-first mixing
11. Final-frame transition state inherited by the next clip
12. Negative constraints, per form（见 Negative contract）

Make each prompt understandable without the global block or any other prompt.

## Style language

Use this wording to request density without character drift.

`stickman` 形态：

> rapid scene changes, kinetic motion-graphic transformations, and frequent visual events, while preserving an identical stick-figure design, constant line weight, and strict temporal consistency

`girl` 形态：

> rapid scene changes, kinetic motion-graphic transformations, and frequent visual events, while preserving the identical hand-drawn girl character — same bob haircut, same outfit, same flat illustration style — and strict temporal consistency

Avoid `rapid style changes`, which can invite model changes to drawing style, line weight, or character design.

## Reference images（girl form only）

Attach the reference sheets（`assets/girl-wave.jpg`, `girl-think.jpg`, `girl-calm.jpg`）to every generation request when the interface supports it. State inside each prompt that the references lock identity（face shape, hair, outfit, palette, illustration style）while storyboard beats define fresh poses, expressions, and staging. Never let a reference image dictate camera, background, or composition.

## Timed visual sequence

Translate the approved storyboard row into three connected events. State where the character begins, what she does and what changes because of that action, how the camera moves, which accent color carries meaning, and what fills or exits the final frame.

Use at least four content-relevant visual devices per prompt. Do not introduce new narrative claims during prompt expansion.

## Dialogue and visual text

Quote the approved English VO exactly once as audio-only dialogue. Instruct the model not to add, omit, paraphrase, repeat, reorder, caption, subtitle, or visually transcribe words.

Default every generated clip to no visible words, letters, numbers, captions, subtitles, interface copy, palette labels, production annotations, logos, or watermarks. Require icon-only message bubbles, content cards, clocks, meters, and notifications. Put optional approved phrases in a separate post-production overlay list outside the prompts.

## Palette notation

Use ordinary descriptive color names such as vivid red, electric blue, or warm gold. Never put hexadecimal, RGB, HSL, Pantone, or other technical color notation in a generation prompt. Models may reproduce prominent notation literally as unwanted interface text.

For light mode, describe the background as a completely flat, uniform, digitally pure-white canvas. Explicitly forbid gray or off-white tint, paper or canvas texture, grain, gradients, vignette, shadows, ambient occlusion, lighting falloff, bloom, fog, color grading, and three-dimensional background depth. Do not use a color code for white.

## Audio contract

State the same narrator delivery in all six prompts; emotion may shift beat to beat without changing voice identity or pace family. A user-named tonal direction replaces it across the whole video. Keep narration dominant over BGM and effects; match BGM tempo to the content's emotion.

Synchronize effects to visible events such as impacts, transformations, energy releases, steps, wipes, or object movement.

## Negative contract

`stickman` 形态禁止：

- photorealism and unwanted 3D rendering
- facial features, hair, or clothing
- extra limbs, malformed anatomy, disconnected lines, or changed proportions
- broken or changing line weight
- inverted theme polarity or unexplained colors
- unintended characters or irrelevant spectacle
- visible words, letters, numbers, technical color notation, palette labels, interface copy, captions, subtitles, logos, or watermarks
- altered, omitted, repeated, reordered, or added dialogue

`girl` 形态禁止：

- photorealism, 3D rendering, or any shift away from the flat hand-drawn illustration style
- changes to hair shape or color, outfit, or the chest print
- exaggerated cartoon expressions that break her calm personality, or chibi/child proportions
- a second full character stealing the lead action（abstract silhouettes as metaphors are acceptable）
- malformed anatomy, unstable proportions across clips, or reference-image poses copied verbatim
- inverted theme polarity or unexplained colors
- visible words, letters, numbers, technical color notation, palette labels, interface copy, captions, subtitles, logos, or watermarks
- altered, omitted, repeated, reordered, or added dialogue

## Stitching guide

List all six clips in order. For every cut, repeat the exact ending state and matching opening state. Include any trim, short audio crossfade, or match-cut note needed for assembly.

## Audio continuity note

Independent text-only generations may vary in voice and music. Recommend, in order:

1. Reuse the same voice or audio reference when the interface supports it.
2. Repeat the identical narrator description in every prompt.
3. For maximum consistency, generate synchronized SFX and add one continuous external English voiceover and BGM track during assembly.

## Phase B checks

- The user approved the current Phase A.
- Exactly six standalone prompts are present.
- Each prompt repeats ratio, theme, the character lock for the chosen form（girl prompts also state the reference-images-identity-only rule and attachments）, palette, voice, audio, transition, and negative locks.
- Each prompt has all three timed beats and at least four relevant visual devices.
- Every beat's core action is performed by the character.
- Every ending matches the next opening.
- Dialogue exactly matches the approved narration.
- Dialogue is explicitly audio-only and is never displayed visually.
- Standalone prompts contain no hexadecimal, RGB, HSL, Pantone, or other technical color notation.
- Generated scenes contain no visible writing; optional overlay phrases are listed separately for post-production.
