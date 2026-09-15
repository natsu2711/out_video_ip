// [outvideo] card-stickman-talk —— 火柴人讲解卡（讲者形态 B：IP 出镜之外的友好极简形态）。
// 内容注入点：globalThis.__OUTVIDEO_CARD__ = { TEXT: ["主台词","补充台词"] }
// 动效：火柴人一笔画（stroke-dashoffset 描边生长）→ 气泡弹出 → 台词逐字显现。全程确定性。
import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";

const __INJ__: any = (globalThis as any).__OUTVIDEO_CARD__ ?? {};
export const meta = { width: 960, height: 540, fps: 30, durationInFrames: 120 };

const INK = "#F2F2F0";
const PAPER = "#141416";
const ACCENT = "#FF4B1F";

const TEXT: string[] = (__INJ__.TEXT as string[])?.length ? (__INJ__.TEXT as string[]).slice(0, 2) : ["一句话讲透", "比一堆术语更管用"];

// 火柴人线段表（以头部圆心为原点的相对坐标），每段一笔画依次生长
const LIMBS: Array<[number, number, number, number]> = [
  [0, 46, 0, 118],     // 躯干
  [0, 62, -30, 92],    // 左臂
  [0, 62, 30, 92],     // 右臂
  [0, 118, -22, 168],  // 左腿
  [0, 118, 22, 168],   // 右腿
];

function DrawLine({ x1, y1, x2, y2, t0, t1, color = INK, width = 5 }: {
  x1: number; y1: number; x2: number; y2: number; t0: number; t1: number; color?: string; width?: number;
}) {
  const f = useCurrentFrame();
  const p = interpolate(f, [t0, t1], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: (x) => 1 - Math.pow(1 - x, 3) });
  const len = Math.hypot(x2 - x1, y2 - y1);
  return (
    <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={color} strokeWidth={width} strokeLinecap="round"
          strokeDasharray={len} strokeDashoffset={len * (1 - p)} />
  );
}

export default function StickmanTalk() {
  const f = useCurrentFrame();
  const headP = interpolate(f, [2, 14], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const bubbleP = interpolate(f, [22, 32], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: (x) => 1 + 1.7 * Math.pow(x - 1, 3) + 1.7 * Math.pow(x - 1, 2) });
  const waveP = interpolate(f, [34, 44], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  // 台词逐字
  const chars = Math.floor(interpolate(f, [30, 66], [0, TEXT[0].length], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
  const subP = interpolate(f, [68, 80], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ background: PAPER }}>
      {/* 地面线 */}
      <DrawLine x1={60} y1={470} x2={900} y2={470} t0={0} t1={8} color="#3A3A40" width={3} />

      {/* 火柴人（左侧，描边生长） */}
      <svg width={420} height={540} viewBox="-210 -60 420 540"
           style={{ position: "absolute", left: 30, top: 20 }}>
        <circle cx={0} cy={20} r={26} fill="none" stroke={INK} strokeWidth={5}
                strokeDasharray={164} strokeDashoffset={164 * (1 - headP)}
                transform={`translate(0 ${interpolate(headP, [0, 1], [18, 0])})`} />
        {LIMBS.map(([x1, y1, x2, y2], i) => (
          <DrawLine key={i} x1={x1} y1={y1 + 20} x2={x2} y2={y2 + 20}
                    t0={12 + i * 3} t1={20 + i * 3} width={5} />
        ))}
        {/* 打招呼手臂：右臂末端抬起挥动 */}
        {waveP > 0 && (
          <line x1={0} y1={82} x2={38 * waveP} y2={60 - 14 * Math.sin(f / 3) * waveP}
                stroke={ACCENT} strokeWidth={5} strokeLinecap="round" />
        )}
      </svg>

      {/* 气泡 + 台词（右侧） */}
      <div style={{
        position: "absolute", right: 60, top: 120, width: 400,
        opacity: Math.min(1, bubbleP), transform: `scale(${0.7 + 0.3 * bubbleP})`,
        transformOrigin: "left center",
      }}>
        <div style={{
          background: "#fff", color: "#141416", borderRadius: 18,
          padding: "26px 30px", position: "relative",
          boxShadow: "0 18px 50px rgba(0,0,0,0.45)",
          fontSize: 38, fontWeight: 900, lineHeight: 1.4, minHeight: 150,
        }}>
          {TEXT[0].slice(0, chars)}
          <span style={{ opacity: f % 20 < 10 ? 1 : 0.2 }}>▌</span>
          {/* 气泡尾巴指向火柴人 */}
          <div style={{
            position: "absolute", left: -14, top: 46, width: 0, height: 0,
            borderTop: "12px solid transparent", borderBottom: "12px solid transparent",
            borderRight: "16px solid #fff",
          }} />
        </div>
        {TEXT[1] && (
          <div style={{
            marginTop: 16, opacity: subP, transform: `translateY(${(1 - subP) * 14}px)`,
            color: "#9a9aa6", fontSize: 22, fontWeight: 700, paddingLeft: 8,
          }}>
            {TEXT[1]}
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
}
