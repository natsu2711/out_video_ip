// [outvideo] card-digit-roll —— 移植自 video-shotcraft assets/lib/DigitRoll.tsx（里程表式数字滚轮）。
// 内容注入点：globalThis.__OUTVIDEO_CARD__ = { TEXT: ["3000000","粉丝数"] }（TEXT[0]=数字串）
// 原动效保留：逐位滚轮 + 序贯落定。全程确定性。
import React from "react";
import { AbsoluteFill, interpolate, Easing, useCurrentFrame } from "remotion";

const __INJ__: any = (globalThis as any).__OUTVIDEO_CARD__ ?? {};
export const meta = { width: 960, height: 540, fps: 30, durationInFrames: 120 };

const DIGITS = "0123456789";

const DigitRoll: React.FC<{ value: string; delay?: number; fontSize?: number; color?: string }> = ({
  value, delay = 0, fontSize = 30, color = "#F5A623",
}) => {
  const frame = useCurrentFrame();
  const lineH = fontSize * 1.15;
  return (
    <span style={{ display: "inline-flex", overflow: "hidden", height: lineH, verticalAlign: "bottom" }}>
      {value.split("").map((ch, i) => {
        const target = DIGITS.indexOf(ch);
        if (target < 0) {
          return <span key={i} style={{ fontSize, lineHeight: `${lineH}px`, color }}>{ch}</span>;
        }
        const t = interpolate(frame, [delay + i * 4, delay + i * 4 + 22], [0, 1], {
          extrapolateLeft: "clamp", extrapolateRight: "clamp",
          easing: Easing.bezier(0.25, 0.8, 0.25, 1),
        });
        const offset = (10 + target) * t * lineH;
        return (
          <span key={i} style={{ display: "inline-block", height: lineH }}>
            <span style={{ display: "block", transform: `translateY(${-offset}px)` }}>
              {(DIGITS + DIGITS).split("").map((d, j) => (
                <span key={j} style={{ display: "block", fontSize, lineHeight: `${lineH}px`, color, fontVariantNumeric: "tabular-nums" }}>
                  {d}
                </span>
              ))}
            </span>
          </span>
        );
      })}
    </span>
  );
};

const TEXT: string[] = (__INJ__.TEXT as string[])?.length ? (__INJ__.TEXT as string[]).slice(0, 2) : ["3000000", "粉丝数"];
const NOTE: string = (__INJ__.CONFIG?.note as string) ?? "播放量突破";

export default function DigitRollCard() {
  return (
    <AbsoluteFill style={{ background: "#101014", alignItems: "center", justifyContent: "center" }}>
      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: 26, fontWeight: 700, color: "#9a9aa6", letterSpacing: 8, marginBottom: 26 }}>
          {NOTE}
        </div>
        <DigitRoll value={TEXT[0]} fontSize={130} color="#F5A623" delay={8} />
        {TEXT[1] && (
          <div style={{ marginTop: 30, fontSize: 30, fontWeight: 800, color: "#ececf1", letterSpacing: 4 }}>
            {TEXT[1]}
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
}
