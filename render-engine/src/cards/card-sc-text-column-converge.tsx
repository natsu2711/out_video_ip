// [outvideo] card-sc-text-column-converge —— 移植自 video-shotcraft/demos/typography/text-column-converge
// 原动效保留；内容接线：raw 档（可在编排手动用，后续逐张接 __INJ__）
// text-column-converge —— raycast-teams（实测素材 28–36s 段）重做版：
// 原片测量（1280 宽）：NEW 左缘钉死 x=412，特性词右缘钉死 x=867，
// 两词到左右屏边距相等（412 vs 413），轮换期间间距完全不收缩；
// 词换到 RAYCAST 后才发生唯一一次合拢——约 1.2s ease-in-out 连续滑动
// （左缘 412→554 / 右缘 867→725），"NEW RAYCAST" 以屏幕中线居中定格；
// 定格后约 0.6s，斜体 "COMING 2026" 在下方近乎硬切浮现。
import React from 'react';
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';

// 词轮换表：停留帧数不均（机器节奏），全程钉在右缘，不做间距收缩
const __INJ__: any = (globalThis as any).__OUTVIDEO_CARD__ ?? {};
// 文字槽：TEXT = 特性词轮换数组（末词触发合拢）；TEXT2 = 左侧标签（默认 NEW）；TEXT3 = 斜体小字
const INJ_WORDS = (__INJ__.TEXT as string[])?.length ? (__INJ__.TEXT as string[]) : null;
const STEPS: { word: string; dur: number }[] = (INJ_WORDS ?? [
  'LAUNCHER DESIGN', 'COMPACT MODE', 'HOTKEY RECORDER', 'HOTKEY TYPES',
  'VOICE FEATURES', 'SETTINGS DESIGN', 'AI CHAT', 'FILE SEARCH', 'RAYCAST',
]).map((word, i) => ({ word, dur: [16, 12, 9, 8, 7, 8, 10, 12][i] ?? (i === (INJ_WORDS ?? []).length - 1 ? 999 : 8) }));
const NEW_LABEL = (__INJ__.TEXT2 as string[])?.[0] ?? 'NEW';
const SUB_TEXT = (__INJ__.TEXT3 as string[])?.[0] ?? 'COMING 2026';

const START = 8; // 开场黑场立静

// 原片 1280 宽 → 1920 宽换算（×1.5）
const NEW_LEFT_EDGE = 618; // 412×1.5：NEW 左缘（= 左屏边距）
const WORD_RIGHT_EDGE = 1302; // 868×1.5：特性词右缘（= 右屏边距，1920-1302=618 对称）

const FS = 42; // 原片字高很小（720p 下 cap ~20px → 1080p ~30px → 字号 ~42）
const LSP = 3; // letterSpacing
// 合拢终点按本字体实际步进计算（监视器等宽：0.6em + letterSpacing），
// 保证 "NEW RAYCAST" 恰好一个空格咬合、整行居中于 960，不会重叠
const ADV = 0.6 * FS + LSP; // 每字符步进
const LINE_W = 11 * ADV; // "NEW RAYCAST" 共 11 字符
const MERGED_LEFT = 960 - LINE_W / 2; // 合拢后 NEW 左缘
const MERGED_RIGHT = 960 + LINE_W / 2; // 合拢后 RAYCAST 右缘
const CONVERGE_DUR = 36; // 合拢时长：原片 ~1.2s ≈ 36 帧
const CONVERGE_DELAY = 10; // RAYCAST 停稳后先静置 10 帧再合拢（原片 32.4→32.7s）
const SUB_DELAY = 18; // 合拢定格后 ~0.6s 出斜体小字

export const TextColumnConverge: React.FC = () => {
  const f = useCurrentFrame();
  const t = f - START;

  // 定位当前步
  let acc = 0;
  let idx = 0;
  let stepStart = 0;
  for (let i = 0; i < STEPS.length; i++) {
    if (t >= acc) { idx = i; stepStart = acc; }
    acc += STEPS[i].dur;
  }
  const cur = STEPS[idx];
  const isLast = idx === STEPS.length - 1;
  const local = t - stepStart;

  // 唯一一次合拢：RAYCAST 停稳 CONVERGE_DELAY 帧后，ease-in-out 连续滑动
  const cvT = isLast ? local - CONVERGE_DELAY : -1;
  const cv = interpolate(cvT, [0, CONVERGE_DUR], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.inOut(Easing.cubic),
  });

  // NEW 左缘：618 → 831；特性词右缘：1302 → 1088
  const newLeft = interpolate(cv, [0, 1], [NEW_LEFT_EDGE, MERGED_LEFT]);
  const wordRight = interpolate(cv, [0, 1], [WORD_RIGHT_EDGE, MERGED_RIGHT]);

  const converged = cv >= 1;

  // 斜体小字：合拢定格后 SUB_DELAY 帧，近乎硬切（4 帧快速淡入，无位移）
  const subT = converged ? cvT - CONVERGE_DUR - SUB_DELAY : -1;
  const subOp = interpolate(subT, [0, 4], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

  const visible = t >= 0;

  const font: React.CSSProperties = {
    fontFamily: '"SF Mono", Menlo, monospace',
    fontWeight: 500,
    fontSize: FS,
    letterSpacing: 3,
    color: '#f2f2f4',
    whiteSpace: 'nowrap',
    lineHeight: 1,
  };

  return (
    <AbsoluteFill style={{ background: '#050506', overflow: 'hidden' }}>
      {visible && (
        <div style={{ position: 'absolute', inset: 0 }}>
          {/* NEW：左缘定位（轮换期间钉死在左屏边距处） */}
          <div style={{
            ...font, position: 'absolute',
            left: newLeft, top: 519,
          }}>
            {NEW_LABEL}
          </div>
          {/* 特性词：右缘定位（词换长换短，右缘不动） */}
          <div style={{
            ...font, position: 'absolute',
            right: 1920 - wordRight, top: 519,
          }}>
            {cur.word}
          </div>

          {/* 斜体小字：合拢后在整行正下方浮现，与整行同左缘 */}
          <div style={{
            ...font,
            fontStyle: 'italic',
            color: '#d8d8dc',
            position: 'absolute',
            left: MERGED_LEFT, top: 519 + FS + 14,
            opacity: subOp,
          }}>
            {SUB_TEXT}
          </div>
        </div>
      )}
    </AbsoluteFill>
  );
};


export default TextColumnConverge;
