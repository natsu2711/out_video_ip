// [outvideo] card-ticker-wall —— 移植自 video-shotcraft assets/lib/VerticalTicker.tsx（3D 纵向无限滚动墙）。
// 内容注入点：globalThis.__OUTVIDEO_CARD__ = { TEXT: ["词条1","词条2","词条3","词条4","词条5","词条6"] }
// 原动效保留：rotateX 透视倾斜 + 三列不同速度/方向无限循环 + 上下渐隐遮罩。全程确定性。
import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";

const __INJ__: any = (globalThis as any).__OUTVIDEO_CARD__ ?? {};
export const meta = { width: 960, height: 540, fps: 30, durationInFrames: 120 };

interface TickerColumn {
  items: React.ReactNode[];
  durationInSeconds: number;
  direction: -1 | 1;
}

const Column: React.FC<TickerColumn & { width: number; gap: number; fontSize: number }> = ({
  items, durationInSeconds, direction, width, gap, fontSize,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const loopFrames = durationInSeconds * fps;
  const progress = (frame % loopFrames) / loopFrames;
  const translateY = direction === -1 ? progress * -50 : -50 + progress * 50;
  return (
    <div style={{ width, height: "100%", display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", flexDirection: "column", transform: `translateY(${translateY}%)`, willChange: "transform" }}>
        {[...items, ...items].map((node, i) => (
          <div key={i} style={{ marginBottom: gap }}>{node}</div>
        ))}
      </div>
    </div>
  );
};

const WORDS: string[] = (__INJ__.TEXT as string[])?.length
  ? (__INJ__.TEXT as string[])
  : ["自由职业", "AI 工具", "被动收入", "内容创业", "远程办公", "个人品牌"];
const BG = "#0D1117";
const CH = { width: 250, gap: 26, fontSize: 30 };

export default function TickerWall() {
  const cols: TickerColumn[] = [
    { items: [WORDS[0 % WORDS.length], WORDS[3 % WORDS.length]].map((t) => (
        <div style={{ background: "#1C2128", border: "1px solid #30363D", borderRadius: 10,
                     padding: "14px 20px", color: "#E6EDF3", fontSize: CH.fontSize, fontWeight: 700 }}>{t}</div>)),
      durationInSeconds: 6, direction: -1 },
    { items: [WORDS[1 % WORDS.length], WORDS[4 % WORDS.length]].map((t) => (
        <div style={{ background: "#12261C", border: "1px solid #2F9E44", borderRadius: 10,
                     padding: "14px 20px", color: "#8CE99A", fontSize: CH.fontSize, fontWeight: 700 }}>{t}</div>)),
      durationInSeconds: 7.5, direction: 1 },
    { items: [WORDS[2 % WORDS.length], WORDS[5 % WORDS.length]].map((t) => (
        <div style={{ background: "#2B1D2E", border: "1px solid #D6336C", borderRadius: 10,
                     padding: "14px 20px", color: "#FCC2D7", fontSize: CH.fontSize, fontWeight: 700 }}>{t}</div>)),
      durationInSeconds: 5.5, direction: -1 },
  ];
  return (
    <AbsoluteFill style={{ backgroundColor: BG }}>
      <div style={{
        width: "100%", height: "100%", display: "flex", justifyContent: "center", gap: CH.gap,
        transform: "perspective(1000px) rotateX(20deg) scale(1.15)", transformOrigin: "center center",
      }}>
        {cols.map((col, idx) => <Column key={idx} {...col} width={CH.width} gap={CH.gap} fontSize={CH.fontSize} />)}
      </div>
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 140,
                    background: `linear-gradient(to bottom, ${BG} 0%, transparent 100%)`, zIndex: 10 }} />
      <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: 140,
                    background: `linear-gradient(to top, ${BG} 0%, transparent 100%)`, zIndex: 10 }} />
    </AbsoluteFill>
  );
}
