// [outvideo] card-ppt-compare —— 吸收自自有项目 out_video_ppt（左右白卡对比 + 中间箭头 PopIn + 阴影同步淡入）。
// 内容注入点：globalThis.__OUTVIDEO_CARD__ = { TEXT: ["以前的做法","现在的做法"] }（2 条；可带 CONFIG.before/after 副标）
// 动效 DNA：cardIn 11帧+30px / stagger 4.2 / 箭头 Easing.bezier(0.34,1.56,0.64,1) 回弹
import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, Easing } from "remotion";

const __INJ__: any = (globalThis as any).__OUTVIDEO_CARD__ ?? {};
export const meta = { width: 960, height: 540, fps: 30, durationInFrames: 110 };

const ease = Easing.bezier(0.22, 1, 0.36, 1);
const easeBack = Easing.bezier(0.34, 1.56, 0.64, 1);
const C = {
  ink: "#212529", gray: "#868E96", border: "rgba(33,37,41,0.12)",
  cardBg: "#FFFFFF", paper: "#F8F7F4",
  blue: "#1971C2", blueBg: "#E7F5FF",
  red: "#D6336C", redBg: "#FDEEF2",
};
const MOTION = { cardIn: 11, cardShift: 30, stagger: 4.2 };

const CardIn: React.FC<{ delay?: number; children: React.ReactNode; style?: React.CSSProperties }> = ({
  delay = 0, children, style,
}) => {
  const f = useCurrentFrame();
  const p = interpolate(f - delay, [0, MOTION.cardIn], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease,
  });
  if (p <= 0) return null;
  return (
    <div style={{
      opacity: p,
      transform: `translateY(${(1 - p) * MOTION.cardShift}px)`,
      boxShadow: `0 ${12 * p}px ${32 * p}px rgba(33,37,41,${0.10 * p})`,
      ...style,
    }}>
      {children}
    </div>
  );
};

const TEXT: string[] = __INJ__.TEXT?.length >= 2 ? __INJ__.TEXT.slice(0, 2) : ["以前的做法", "现在的做法"];
const [before, after] = TEXT;
const beforeNote: string = (__INJ__.CONFIG?.before as string) ?? "旧路径 · 费力";
const afterNote: string = (__INJ__.CONFIG?.after as string) ?? "新路径 · 顺手";

function Side({ title, note, tone, delay, align }:
  { title: string; note: string; tone: "red" | "blue"; delay: number; align: "left" | "right" }) {
  const f = useCurrentFrame();
  const p = interpolate(f - delay, [0, MOTION.cardIn], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease,
  });
  const isBefore = tone === "red";
  return (
    <CardIn delay={delay} style={{
      flex: 1, background: C.cardBg, border: `1px solid ${C.border}`,
      borderRadius: 14, padding: "26px 28px", height: 220,
      display: "flex", flexDirection: "column", justifyContent: "center", gap: 10,
      opacity: p * (isBefore ? 0.85 : 1), // 旧做法压暗一档
    }}>
      <div style={{ fontSize: 15, fontWeight: 800, letterSpacing: 3, color: isBefore ? C.gray : C.blue }}>
        {isBefore ? "BEFORE" : "AFTER"}
      </div>
      <div style={{
        fontSize: 32, fontWeight: 900, lineHeight: 1.3,
        color: C.ink, textAlign: align,
        textDecoration: isBefore ? "line-through" : "none",
        textDecorationColor: "rgba(214,51,108,0.55)", textDecorationThickness: 3,
      }}>{title}</div>
      <div style={{ fontSize: 18, fontWeight: 700, color: isBefore ? C.gray : C.blue,
                    background: isBefore ? "#F1F3F5" : C.blueBg,
                    borderRadius: 8, padding: "4px 12px", justifySelf: "start" }}>{note}</div>
    </CardIn>
  );
}

export default function PptCompare() {
  const f = useCurrentFrame();
  // 中间箭头：两张卡落定后回弹入场
  const p = interpolate(f, [26, 36], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: easeBack });
  return (
    <AbsoluteFill style={{ background: C.paper, fontFamily: "'PingFang SC','Microsoft YaHei',sans-serif" }}>
      <div style={{ position: "absolute", left: 64, top: 52, display: "flex", alignItems: "baseline", gap: 18 }}>
        <div style={{ width: 34, height: 6, background: C.blue }} />
        <div style={{ fontSize: 34, fontWeight: 800, color: C.ink, letterSpacing: 6 }}>对比</div>
      </div>

      <div style={{ position: "absolute", left: 64, right: 64, top: 150, display: "flex", gap: 40, alignItems: "center" }}>
        <Side title={before} note={beforeNote} tone="red" delay={6} align="left" />
        <div style={{
          width: 74, height: 74, borderRadius: "50%", flexShrink: 0,
          background: C.ink, color: "#fff", display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 32, fontWeight: 900,
          opacity: Math.min(1, p * 1.3), transform: `scale(${0.5 + 0.5 * p})`,
        }}>→</div>
        <Side title={after} note={afterNote} tone="blue" delay={6 + MOTION.stagger} align="left" />
      </div>

      {/* 底部结论条：随箭头后淡入 */}
      {(() => {
        const p2 = interpolate(f, [40, 50], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
        if (p2 <= 0) return null;
        return (
          <div style={{
            position: "absolute", left: 64, right: 64, bottom: 56, opacity: p2,
            transform: `translateY(${(1 - p2) * 16}px)`,
            background: C.ink, color: "#fff", borderRadius: 10, padding: "12px 22px",
            fontSize: 19, fontWeight: 700,
          }}>
            结论：把力气花在新路径上，别在旧路径里证明自己
          </div>
        );
      })()}
    </AbsoluteFill>
  );
}
