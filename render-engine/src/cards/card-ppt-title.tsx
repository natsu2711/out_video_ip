// [outvideo] card-ppt-title —— 移植自自有项目 out_video_ppt（PhasePill 章节药丸 + FadeUp 大标题）。
// 内容注入点：globalThis.__OUTVIDEO_CARD__ = { TEXT: ["章节标题","阶段名"] }
// 动效 DNA：PhasePill 先弹（easeBack）→ 大标题 FadeUp（bezier 0.22,1,0.36,1，位移 24px）。
import React from "react";
import { AbsoluteFill, interpolate, Easing, useCurrentFrame } from "remotion";

const __INJ__: any = (globalThis as any).__OUTVIDEO_CARD__ ?? {};
export const meta = { width: 960, height: 540, fps: 30, durationInFrames: 110 };

const ease = Easing.bezier(0.22, 1, 0.36, 1);
const easeBack = Easing.bezier(0.34, 1.56, 0.64, 1);
const C = { ink: "#212529", gray: "#868E96", paper: "#F8F7F4", red: "#D6336C", blue: "#1971C2" };

const TEXT: string[] = (__INJ__.TEXT as string[])?.length ? (__INJ__.TEXT as string[]).slice(0, 2) : ["培养跑路能力", "阶段 01"];

export default function PptTitle() {
  const f = useCurrentFrame();
  const pillP = interpolate(f, [4, 14], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: easeBack });
  const titleP = interpolate(f, [14, 26], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  const barP = interpolate(f, [22, 34], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });

  return (
    <AbsoluteFill style={{ background: C.paper, fontFamily: "'PingFang SC','Microsoft YaHei',sans-serif" }}>
      {/* PhasePill：章节药丸 */}
      <div style={{
        position: "absolute", left: 110, top: 150, opacity: Math.min(1, pillP * 1.3),
        transform: `scale(${0.6 + 0.4 * pillP})`, transformOrigin: "left center",
        display: "inline-flex", alignItems: "center", gap: 10,
        background: "#fff", border: `2px solid ${C.blue}`, borderRadius: 999,
        padding: "10px 26px",
      }}>
        <span style={{ width: 10, height: 10, borderRadius: "50%", background: C.blue }} />
        <span style={{ fontSize: 24, fontWeight: 800, color: C.blue, letterSpacing: 3 }}>{TEXT[1]}</span>
      </div>

      {/* 大标题 */}
      <div style={{
        position: "absolute", left: 110, top: 240, right: 110,
        opacity: titleP, transform: `translateY(${(1 - titleP) * 24}px)`,
        fontSize: 84, fontWeight: 900, color: C.ink, letterSpacing: "0.04em", lineHeight: 1.25,
      }}>{TEXT[0]}</div>

      {/* 底部进度线 */}
      <div style={{ position: "absolute", left: 110, bottom: 96, width: 500, height: 8, background: "#E9ECEF", borderRadius: 4 }}>
        <div style={{ width: `${barP * 62}%`, height: "100%", background: C.red, borderRadius: 4 }} />
      </div>
      <div style={{ position: "absolute", right: 110, bottom: 84, fontSize: 16, fontFamily: "'SF Mono',Menlo,monospace", color: C.gray }}>
        01 / 03
      </div>
    </AbsoluteFill>
  );
}
