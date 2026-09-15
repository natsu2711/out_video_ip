// [outvideo] card-type-serif —— 衬线宋体金句卡（书卷气排印：竖排装饰线 + 大号衬线主句 + 小注）。
// 内容注入点：globalThis.__OUTVIDEO_CARD__ = { TEXT: ["主句","小注"] }
// 动效：主句逐字浮现（clip-path 刷出），装饰线横向生长。全程确定性。
import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";

const __INJ__: any = (globalThis as any).__OUTVIDEO_CARD__ ?? {};
export const meta = { width: 960, height: 540, fps: 30, durationInFrames: 120 };

const SERIF = "'Songti SC','STSong','Noto Serif SC',serif";

const TEXT: string[] = (__INJ__.TEXT as string[])?.length ? (__INJ__.TEXT as string[]).slice(0, 2) : ["慢就是快", "少做无意义的事"];

export default function TypeSerif() {
  const f = useCurrentFrame();
  const lineP = interpolate(f, [4, 18], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: (x) => 1 - Math.pow(1 - x, 3) });
  const chars = Math.floor(interpolate(f, [10, 50], [0, TEXT[0].length], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
  const subP = interpolate(f, [52, 64], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ background: "#F7F4EC" }}>
      {/* 左侧竖排装饰（书脊感） */}
      <div style={{
        position: "absolute", left: 90, top: 80, bottom: 80, width: 1,
        background: "linear-gradient(#B08D57, transparent)", opacity: lineP,
      }} />
      <div style={{
        position: "absolute", left: 70, top: 80, writingMode: "vertical-rl",
        fontFamily: SERIF, fontSize: 20, letterSpacing: 10, color: "#B08D57",
        opacity: lineP,
      }}>{TEXT[1]?.slice(0, 8) ?? "排印"}</div>

      {/* 主句：衬线大字逐字刷出 */}
      <div style={{
        position: "absolute", left: 150, right: 80, top: 150,
        fontFamily: SERIF, fontSize: 76, fontWeight: 700, color: "#26221C",
        lineHeight: 1.35, letterSpacing: "0.06em",
      }}>
        {TEXT[0].slice(0, chars).split("").map((ch, i) => (
          <span key={i} style={{
            display: "inline-block",
            clipPath: `inset(0 0 0 0)`,
            opacity: 1,
            animation: "none",
          }}>{ch}</span>
        ))}
        {chars < TEXT[0].length && <span style={{ opacity: 0.3 }}>▌</span>}
      </div>

      {/* 小注 */}
      {TEXT[1] && (
        <div style={{
          position: "absolute", left: 152, top: 420, opacity: subP,
          transform: `translateY(${(1 - subP) * 12}px)`,
          fontFamily: SERIF, fontSize: 24, color: "#8A7A5C", letterSpacing: 4,
        }}>{TEXT[1]}</div>
      )}

      {/* 印章（红） */}
      <div style={{
        position: "absolute", right: 96, bottom: 76, width: 44, height: 44,
        border: "3px solid #C0392B", borderRadius: 6, opacity: subP,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontFamily: SERIF, color: "#C0392B", fontSize: 20, fontWeight: 700,
      }}>印</div>
    </AbsoluteFill>
  );
}
