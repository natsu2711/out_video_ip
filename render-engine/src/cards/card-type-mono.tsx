// [outvideo] card-type-mono —— 等宽终端字幕卡（代码感：深底 + 光标行 + 等宽字阶）。
// 内容注入点：globalThis.__OUTVIDEO_CARD__ = { TEXT: ["第一行","第二行"] }
// 动效：逐行打字机 + 光标闪烁 + 行号。全程确定性。
import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";

const __INJ__: any = (globalThis as any).__OUTVIDEO_CARD__ ?? {};
export const meta = { width: 960, height: 540, fps: 30, durationInFrames: 120 };

const MONO = "'SF Mono','Menlo','Consolas','Courier New',monospace";

const TEXT: string[] = (__INJ__.TEXT as string[])?.length
  ? (__INJ__.TEXT as string[]).slice(0, 2)
  : ["n = 坚持的天数", "回报 ≈ n ** 2"];

export default function TypeMono() {
  const f = useCurrentFrame();
  const l1Chars = Math.floor(interpolate(f, [6, 34], [0, TEXT[0].length], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
  const l2Start = 36 + 4;
  const l2Chars = Math.floor(interpolate(f, [l2Start, l2Start + 28], [0, TEXT[1].length], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
  const cursorOn = f % 16 < 8;

  return (
    <AbsoluteFill style={{ background: "#0D1117" }}>
      {/* 终端窗口框 */}
      <div style={{
        position: "absolute", left: 70, right: 70, top: 100, bottom: 100,
        background: "#161B22", borderRadius: 14, border: "1px solid #30363D",
        padding: "28px 36px",
      }}>
        <div style={{ display: "flex", gap: 8, marginBottom: 26 }}>
          {["#FF5F56", "#FFBD2E", "#27C93F"].map((c) => (
            <div key={c} style={{ width: 13, height: 13, borderRadius: "50%", background: c, opacity: 0.9 }} />
          ))}
          <span style={{ marginLeft: 10, color: "#8B949E", fontFamily: MONO, fontSize: 15 }}>~/insight</span>
        </div>
        {[
          { n: 1, text: TEXT[0], chars: l1Chars, color: "#E6EDF3" },
          { n: 2, text: TEXT[1], chars: l2Chars, color: "#7EE787" },
        ].map((row) => (
          <div key={row.n} style={{ display: "flex", gap: 18, marginBottom: 20, alignItems: "baseline" }}>
            <span style={{ color: "#484F58", fontFamily: MONO, fontSize: 22, width: 24, textAlign: "right" }}>{row.n}</span>
            <span style={{ color: row.color, fontFamily: MONO, fontSize: 40, fontWeight: 700, whiteSpace: "nowrap" }}>
              {row.text.slice(0, row.chars)}
              {row.chars < row.text.length && cursorOn ? "▌" : ""}
            </span>
          </div>
        ))}
        <span style={{ color: "#7EE787", fontFamily: MONO, fontSize: 30 }}>{cursorOn ? "▌" : " "}</span>
      </div>
    </AbsoluteFill>
  );
}
