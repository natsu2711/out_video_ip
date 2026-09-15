// [outvideo] card-ppt-steps —— 吸收自自有项目 out_video_ppt（PPT 白卡 + CardIn 阶梯入场 + 阴影同步淡入）。
// 内容注入点：globalThis.__OUTVIDEO_CARD__ = { STEPS: ["步骤1","步骤2",...] }（4 条以内，≤16 字/条）
// 动效 DNA（与源项目一致）：ease bezier(0.22,1,0.36,1) / cardIn 11帧+30px位移 / stagger 4.2帧 / 阴影随进度淡入
import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, Easing } from "remotion";

const __INJ__: any = (globalThis as any).__OUTVIDEO_CARD__ ?? {};
export const meta = { width: 960, height: 540, fps: 30, durationInFrames: 120 };

const ease = Easing.bezier(0.22, 1, 0.36, 1);
const C = {
  ink: "#212529", gray: "#868E96", border: "rgba(33,37,41,0.12)",
  cardBg: "#FFFFFF", paper: "#F8F7F4",
  blue: "#1971C2", blueBg: "#E7F5FF",
  red: "#D6336C", redBg: "#FDEEF2",
  green: { bg: "#EBFBEE", fg: "#2F9E44" },
  shadow: "0 12px 32px rgba(33,37,41,0.10)",
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

const STEPS: string[] = __INJ__.STEPS ?? ["第一步 · 明确问题", "第二步 · 拆解动作", "第三步 · 小步验证"];
const N = Math.min(4, Math.max(2, STEPS.length));
const items = STEPS.slice(0, N);
const accents = [C.blue, C.red, C.green.fg, "#D9480F"];
const accentBgs = [C.blueBg, C.redBg, C.green.bg, "#FFF4E6"];

export default function PptSteps() {
  const f = useCurrentFrame();
  const vertical = N > 3; // 4 步竖排，2-3 步横排
  return (
    <AbsoluteFill style={{ background: C.paper, fontFamily: "'PingFang SC','Microsoft YaHei',sans-serif" }}>
      {/* 页首标题条：等宽字距，PPT 目录页风格 */}
      <div style={{ position: "absolute", left: 64, top: 52, display: "flex", alignItems: "baseline", gap: 18 }}>
        <div style={{ width: 34, height: 6, background: C.red }} />
        <div style={{ fontSize: 34, fontWeight: 800, color: C.ink, letterSpacing: 6 }}>关键步骤</div>
      </div>

      <div style={{
        position: "absolute", left: 64, right: 64, top: 128, bottom: 56,
        display: "flex", flexDirection: vertical ? "column" : "row",
        gap: vertical ? 20 : 28, alignItems: "stretch",
      }}>
        {items.map((t, i) => {
          const delay = 6 + i * MOTION.stagger;
          const p = interpolate(f - delay, [0, MOTION.cardIn], [0, 1], {
            extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease,
          });
          return (
            <CardIn key={i} delay={delay}
                    style={{ flex: 1, position: "relative", background: C.cardBg,
                             border: `1px solid ${C.border}`, borderRadius: 14, padding: vertical ? "18px 26px" : "22px 26px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                <div style={{
                  width: 52, height: 52, borderRadius: 12, flexShrink: 0,
                  background: accentBgs[i % 4], color: accents[i % 4],
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 24, fontWeight: 900,
                  transform: `scale(${0.6 + 0.4 * p})`, // 数字块回弹
                }}>{i + 1}</div>
                <div style={{ fontSize: 27, fontWeight: 800, color: C.ink, lineHeight: 1.25 }}>{t}</div>
              </div>
              {/* 连接线：前一张落定后从左往右生长 */}
              {i < N - 1 && (
                <div style={{
                  position: "absolute",
                  ...(vertical ? { left: 48, bottom: -20, width: 3, height: 20 * p, background: C.border }
                               : { right: -28, top: "50%", width: 28 * p, height: 3, background: C.border }),
                }} />
              )}
            </CardIn>
          );
        })}
      </div>

      {/* 右下角页码占位（PPT footer 传统） */}
      <div style={{ position: "absolute", right: 48, bottom: 26, fontSize: 15, color: C.gray, fontWeight: 700 }}>
        {String(Math.min(N, 99)).padStart(2, "0")}
      </div>
    </AbsoluteFill>
  );
}
