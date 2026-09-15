// [outvideo] card-ip-emote —— A-roll 表情层：IP 形象 / 火柴人 的表情特写（素材路径可换）。
// 内容注入点：globalThis.__OUTVIDEO_CARD__ = { TEXT: ["表情名"], CONFIG: {image: "uploads/xx.png", stickman: true} }
// 素材：CONFIG.image 为 staticFile 相对路径（未配置 → 内置火柴人表情脸）。
import React from "react";
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from "remotion";

const __INJ__: any = (globalThis as any).__OUTVIDEO_CARD__ ?? {};
export const meta = { width: 960, height: 540, fps: 30, durationInFrames: 90 };

const EMOTE: string = (__INJ__.TEXT as string[])?.[0] ?? "疑问";
const IMG: string | undefined = (__INJ__.CONFIG?.image as string) || undefined;
const STICKMAN = !!(__INJ__.CONFIG?.stickman ?? true);

const FACES: Record<string, React.ReactNode> = {
  疑问: <text x="0" y="14" textAnchor="middle" fontSize="44" fontWeight="900" fill="#141416">?</text>,
  思考: <g><text x="-16" y="10" textAnchor="middle" fontSize="30" fontWeight="900" fill="#141416">…</text></g>,
  开心: <g>
          <path d="M -18 6 Q 0 26 18 6" fill="none" stroke="#141416" strokeWidth="5" strokeLinecap="round" />
          <circle cx="-14" cy="-12" r="4" fill="#141416" /><circle cx="14" cy="-12" r="4" fill="#141416" />
        </g>,
};

export default function IpEmote() {
  const f = useCurrentFrame();
  const pop = interpolate(f, [2, 12], [0.6, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
    easing: (x) => 1 + 1.7 * Math.pow(x - 1, 3) + 1.7 * Math.pow(x - 1, 2),
  });
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <div style={{ transform: `scale(${pop})`, textAlign: "center" }}>
        {IMG ? (
          <Img src={staticFile(IMG)} style={{ width: 320, height: 320, objectFit: "cover", borderRadius: 24,
                                               boxShadow: "0 18px 60px rgba(0,0,0,0.35)" }} />
        ) : (
          <svg width={300} height={300} viewBox="-150 -150 300 300">
            <circle cx="0" cy="0" r={110} fill="#fff" stroke="#141416" strokeWidth={8} />
            {FACES[EMOTE] ?? FACES["疑问"]}
          </svg>
        )}
        <div style={{ marginTop: 18, fontSize: 34, fontWeight: 900, color: "#fff",
                      textShadow: "0 2px 14px rgba(0,0,0,0.5)", letterSpacing: 6 }}>{EMOTE}</div>
      </div>
    </AbsoluteFill>
  );
}
