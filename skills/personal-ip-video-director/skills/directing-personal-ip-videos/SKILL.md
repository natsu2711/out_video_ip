---
name: directing-personal-ip-videos
description: Use when turning copy, notes, articles, or topics into one-minute personal-IP videos — hand-drawn girl-presenter explainers or minimal stick-figure animations — motivational shorts, or Gemini Omni Flash prompt packages.
---

# Directing Personal-IP Videos

## Core contract

Turn one source into a confirmed director's proposal and then six standalone prompts for approximately ten-second Gemini Omni Flash clips. Preserve the source's meaning while strengthening its hook, progression, and closing callback. Every scene is performed by the chosen personal IP character — never a decoration.

## Character forms

Exactly one form per video, chosen at setup and locked through all six clips:

- `girl`（默认）— the house character「短发 T 恤女孩」: hand-drawn flat illustration, short black bob hair, loose navy-purple T-shirt, dark trousers. Identity comes from `assets/girl-*.jpg` reference sheets plus the verbal lock in `references/ip-character.md`. Requires attaching the reference images to the generation request.
- `stickman` — minimal line figure: hollow circular head, no face, no clothing, uniform medium line weight. Pure text lock.

Read `references/ip-character.md` before planning either form. Switching form mid-project is a global change and invalidates prior approval.

## Setup gate

Require these before planning:

- source material
- character form: `girl` or `stickman`（girl 需确认能拿到参考图；都没有时提示用户补充，不要默默改用火柴人）
- aspect ratio: `16:9`, `9:16`, or `1:1`
- theme: light or dark base（girl 形态下指背景与线稿明暗，女孩自身配色不变）

If anything is missing, ask for all missing items in one concise message and stop. Never select a form, aspect ratio, or theme silently. Do not re-ask choices already supplied.

Urgency, generation cost, client pressure, and requests to "pick normal settings" do not waive this gate.

## Workflow

1. Read `references/ip-character.md`, then `references/storyboard-template.md`, and produce Phase A in the user's language, with English VO and a reference translation.
2. Stop after the director's proposal and request explicit approval.
3. If the user changes form, ratio, theme, narration, scene structure, or global style, recompose Phase A and request approval again.
4. Only after approval of the current Phase A, read `references/omni-flash-prompt-contract.md` and produce Phase B.
5. Use `references/examples.md` only when a concrete end-to-end example would resolve ambiguity.

Topic approval, schedule pressure, or approval of an older draft is not approval of the current Phase A.

## Output rules

- Target 130–150 English VO words across six clips.
- Give each clip three timed beats, at least four relevant visual devices, and a visual change every two to three seconds.
- The character performs every scene's core action: moving, connecting, breaking, testing, climbing, pressing — not standing beside it. If the scene still works after removing the character, redesign the scene.
- Keep the character's identity locks consistent: girl form locks hair, outfit, palette, and illustration style; stickman form locks proportions and line weight. Narrator stays consistent regardless of form.
- Limit the video to three saturated accent colors beyond the character's own colors. Name them only with ordinary descriptive words such as vivid red, electric blue, or warm gold.
- Never place hexadecimal, RGB, HSL, Pantone, or other technical color notation inside a model prompt. Treat palette choices as visual art direction, never visible content.
- For the light theme, request a flat, uniform, digitally pure-white canvas and forbid gray or off-white tint, texture, gradients, shadows, lighting, bloom, fog, and three-dimensional background depth. Do not express the white as a color code.
- Make each model prompt self-contained and repeat all critical locks. Girl form prompts must also state that the attached reference images define identity only — re-pose and re-express freely, never copy a reference pose or background.
- Treat narration as audio-only. Quote exact dialogue and forbid alteration, repetition, captions, subtitles, or visual transcription.
- Default generated clips to no visible words, letters, numbers, interface copy, or technical annotations. Make cards and notifications icon-only. Put any optional two-to-five-word overlay in a separate post-production note, never inside the generation prompt.
- Match every clip ending to the next clip opening.
- Do not invent unsupported facts, statistics, quotations, or product claims.

## Revision rules

Recompose rather than rename:

- `16:9`: stage action across left, center, and right; use lateral tracking and negative space.
- `9:16`: use depth, stacked motion, vertical reveals, and interface-safe placement.
- `1:1`: use compact central composition and shorter travel paths.

Theme changes invert background and base line art while preserving the character's own colors, accent semantics, and contrast. Form changes swap the entire cast and a fresh Phase A. Any global change invalidates prior approval.

## Final check

Apply the checklist in the loaded reference, including the character-identity checks for the chosen form. Repair any failed condition before responding.
