// [outvideo] card-test-card —— 由 scripts/gen_card.py 一键生成（模板: steps）。
// 内容注入点：globalThis.__OUTVIDEO_CARD__ = { TEXT: [...] }（改文字即用，动效不动）
import React from "react";
import { AbsoluteFill, interpolate, Easing, useCurrentFrame } from "remotion";

const __INJ__: any = (globalThis as any).__OUTVIDEO_CARD__ ?? {};
export const meta = { width: 960, height: 540, fps: 30, durationInFrames: 110 };

const ease = Easing.bezier(0.22, 1, 0.36, 1);

const STEPS: string[] = (__INJ__.STEPS as string[])?.length
  ? (__INJ__.STEPS as string[]).slice(0, 3)
  : ["1. 步骤 1", "2. 步骤 2", "3. 步骤 3"];

export default function Card() {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: "#F8F7F4" }}>
      {STEPS.map((t, i) => {
        const p = interpolate(f, [4 + i * 4.2, 15 + i * 4.2], [0, 1],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
        if (p <= 0) return null;
        return (
          <div key={i} style={{
            position: "absolute", left: 64, right: 64, top: 70 + i * 120, height: 96, opacity: p,
            transform: `translateY(${(1 - p) * 30}px)`,
            background: "#FFFFFF", border: "1px solid rgba(33,37,41,0.12)", borderRadius: 14,
            display: "flex", alignItems: "center", gap: 16, padding: "0 26px",
            boxShadow: `0 ${10 * p}px ${26 * p}px rgba(33,37,41,${0.10 * p})`,
          }}>
            <div style={{ width: 48, height: 48, borderRadius: 10, background: "#D6336C",
                          color: "#fff", display: "flex", alignItems: "center", justifyContent: "center",
                          fontSize: 22, fontWeight: 900, transform: `scale(${0.6 + 0.4 * p})` }}>
              {i + 1}
            </div>
            <div style={{ fontSize: 30, fontWeight: 800, color: "#212529" }}>{t}</div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
}
