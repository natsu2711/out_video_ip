import {useCurrentFrame, useVideoConfig} from 'remotion';
import {interpolate, spring} from 'remotion';

interface Props {
  shot: any;
  timingSegs: any[];
  tokens: any;
  ipImage?: string;
  assets: any;
}

/** CTA 收尾卡：口号浮现 → 引导箭头/评论区提示 → 定格 + 呼吸。
 * 口号取 shot.motion[0]（缺省用 vo 末句），互动引导取 motion[1]。 */
export function EndingCard({shot, timingSegs, tokens}: Props) {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();

  const slogan =
    (shot.motion || [])[0] ||
    (timingSegs?.[timingSegs.length - 1]?.text || '').slice(0, 18) ||
    '关注我，下期见';
  const cta = (shot.motion || [])[1] || '评论区聊聊 👇';

  // 定格呼吸：最后 1/3 时长进入 idle 呼吸
  const idleStart = durationInFrames * 0.6;
  const breath = frame > idleStart ? 1 + Math.sin(frame * 0.08) * 0.012 : 1;

  const sloganPop = spring({frame: frame - 8, fps, config: {damping: 11, stiffness: 70}});
  const ctaOpacity = interpolate(frame, [fps * 1.2, fps * 2.0], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        gap: 60,
        background: tokens.bg,
        color: tokens.text,
        padding: 60,
      }}
    >
      {/* 口号 */}
      <div
        style={{
          fontSize: 64,
          fontWeight: 900,
          textAlign: 'center',
          lineHeight: 1.35,
          color: tokens.anchor,
          opacity: Math.max(0, Math.min(1, sloganPop)),
          transform: `scale(${(0.85 + 0.15 * Math.max(0, sloganPop)) * breath})`,
          textShadow: `0 0 50px ${tokens.anchor}44`,
        }}
      >
        {slogan}
      </div>

      {/* 互动引导 */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 14,
          opacity: ctaOpacity,
        }}
      >
        {/* 下指箭头动画 */}
        <div
          style={{
            fontSize: 48,
            color: tokens.anchor,
            transform: `translateY(${Math.sin(frame * 0.15) * 8}px)`,
          }}
        >
          ↓
        </div>
        <div style={{fontSize: 34, fontWeight: 600, color: `${tokens.text}dd`}}>{cta}</div>
      </div>
    </div>
  );
}
