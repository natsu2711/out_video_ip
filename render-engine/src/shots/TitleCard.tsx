import {useCurrentFrame, useVideoConfig} from 'remotion';
import {interpolate} from 'remotion';

interface Props {
  shot: any;
  timingSegs: any[];
  tokens: any;
  ipImage?: string;
  assets: any;
}

/** 从 motion/visual 提取「」引号文案（去掉锚点标注），按拍次呈现 */
function extractQuotes(shot: any): string[] {
  const src = [
    ...(shot.motion || []),
    String(shot.visual || ''),
  ].join(' ');
  const matches = src.match(/[「『]([^」』]+)[」』]/g) || [];
  return matches
    .map((m: string) => m.replace(/[「『」』]/g, ''))
    .filter((t: string) => t && !t.startsWith('锚'))
    .slice(0, 3);
}

/** 开场大字卡：引言灰字浮现 → 锚点大字砸入（相机脉冲+底色闪变） */
export function TitleCard({shot, tokens}: Props) {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const quotes = extractQuotes(shot);
  const lead = quotes[0] || '先想清楚一件事';
  const punch = quotes[1] || shot.vo.slice(0, 12);

  // 三拍节奏（约 1s / 2.5s / 4s 处），渲染时长不同自动等比靠前
  const t1 = Math.min(fps * 1.0, fps);
  const t2 = fps * 2.2;
  const t3 = fps * 3.6;
  const shock = Math.max(0, 1 - Math.abs(frame - t2) / 6); // 砸入脉冲
  // 持续悬浮微动：6s 周期 ±6px（帧驱动确定性，保证长驻期不冻结）
  const floatY = Math.sin((frame / fps) * ((Math.PI * 2) / 6)) * 6;

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        background: `linear-gradient(to bottom, ${tokens.bg}, #000)`,
        color: tokens.text,
        padding: 60,
        gap: 48,
        transform: `translateY(${floatY}px)`,
      }}
    >
      {/* 引言（灰字） */}
      <div
        style={{
          fontSize: 40,
          fontWeight: 600,
          opacity: interpolate(frame, [t1 * 0.3, t1], [0, 0.75], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          }),
          transform: `translateY(${interpolate(frame, [t1 * 0.3, t1], [24, 0], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          })}px)`,
          textAlign: 'center',
          lineHeight: 1.5,
        }}
      >
        {lead}
      </div>

      {/* 锚点大字 */}
      <div
        style={{
          fontSize: punch.length > 12 ? 64 : 84,
          fontWeight: 900,
          color: tokens.anchor,
          textAlign: 'center',
          lineHeight: 1.3,
          opacity: interpolate(frame, [t2, t2 + 8], [0, 1], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          }),
          transform: `scale(${1 + shock * 0.12})`,
          textShadow: `0 0 ${30 + shock * 50}px ${tokens.anchor}88`,
        }}
      >
        {punch}
      </div>

      {/* 收尾补充行（如有第三段） */}
      {quotes[2] && (
        <div
          style={{
            fontSize: 34,
            fontWeight: 700,
            color: `${tokens.text}cc`,
            opacity: interpolate(frame, [t3, t3 + 10], [0, 1], {
              extrapolateLeft: 'clamp',
              extrapolateRight: 'clamp',
            }),
          }}
        >
          {quotes[2]}
        </div>
      )}
    </div>
  );
}
