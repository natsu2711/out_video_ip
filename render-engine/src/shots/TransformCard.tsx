import {useCurrentFrame, useVideoConfig} from 'remotion';
import {interpolate, spring} from 'remotion';

interface Props {
  shot: any;
  timingSegs: any[];
  tokens: any;
  ipImage?: string;
  assets: any;
}

/** 去掉「（锚：'xxx'）」等内部标注 */
function cleanLabel(s: string): string {
  return String(s).replace(/（[^）]*）/g, '').replace(/\([^)]*\)/g, '').trim();
}

/** A→B 转变卡（竖屏友好：上下堆叠 + 下行箭头，参照 talkcraft 竖屏变形卡）。
 * 前后态取 shot.motion[0]/motion[1]，或 visual 里按「→」切分。 */
export function TransformCard({shot, tokens}: Props) {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  // 持续悬浮微动：6s 周期 ±6px（帧驱动确定性，保证爆发后长驻期不冻结）
  const floatY = Math.sin((frame / fps) * ((Math.PI * 2) / 6)) * 6;

  let before = cleanLabel((shot.motion || [])[0] || '');
  let after = cleanLabel((shot.motion || [])[1] || '');
  if (!before || !after) {
    const parts = String(shot.visual || '').split('→');
    before = before || cleanLabel(parts[0]).slice(0, 12) || '旧状态';
    after = after || cleanLabel(parts[1]).slice(0, 12) || '新状态';
  }
  before = before.split('→')[0].trim() || before;
  after = after.split('→').pop()?.trim() || after;

  // 时间轴（竖屏三拍：左态入 → 箭头压缩 → 右态爆发），长镜头等比拉伸
  const durScale = Math.max(1, fps * 4.5 / (fps * 4.5));
  const t1 = fps * 1.0 * durScale;
  const t2 = fps * 2.2 * durScale;
  const t3 = fps * 3.2 * durScale;

  const beforeOpacity = interpolate(frame, [0, t1 * 0.6, t2, t2 + 10], [0, 1, 1, 0.18], {
    extrapolateRight: 'clamp',
  });
  const beforeScale = interpolate(frame, [0, t1, t2, t3], [0.85, 1, 1, 0.55], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const afterPop = spring({frame: frame - t3, fps, config: {damping: 10, stiffness: 110}});
  const arrowSlide = interpolate(frame, [t2, t3], [0, 24], {
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
        alignItems: 'center',
        justifyContent: 'center',
        gap: 56,
        background: tokens.bg,
        color: tokens.text,
        padding: 80,
        transform: `translateY(${floatY}px)`,
      }}
    >
      {/* 上：旧态 */}
      <div
        style={{
          textAlign: 'center',
          opacity: beforeOpacity,
          transform: `scale(${beforeScale})`,
          filter: beforeScale < 0.7 ? 'blur(3px)' : 'none',
        }}
      >
        <div style={{fontSize: 28, color: `${tokens.text}77`, marginBottom: 18, letterSpacing: 4}}>
          以 前
        </div>
        <div
          style={{
            fontSize: 58,
            fontWeight: 800,
            lineHeight: 1.35,
            color: `${tokens.text}cc`,
            border: `3px solid ${tokens.text}33`,
            borderRadius: 24,
            padding: '28px 56px',
          }}
        >
          {before}
        </div>
      </div>

      {/* 中：箭头（压缩期滑入高亮） */}
      <div
        style={{
          fontSize: 72,
          fontWeight: 900,
          color: tokens.anchor,
          opacity: interpolate(frame, [t1 * 0.9, t1 * 1.5], [0, 1], {extrapolateRight: 'clamp'}),
          transform: `translateY(${arrowSlide}px)`,
        }}
      >
        ↓
      </div>

      {/* 下：新态（爆发） */}
      <div
        style={{
          textAlign: 'center',
          opacity: Math.max(0, Math.min(1, afterPop)),
          transform: `scale(${0.8 + 0.35 * Math.max(0, afterPop)})`,
        }}
      >
        <div style={{fontSize: 28, color: tokens.anchor, marginBottom: 18, letterSpacing: 4, opacity: afterPop}}>
          现 在
        </div>
        <div
          style={{
            fontSize: 68,
            fontWeight: 900,
            lineHeight: 1.35,
            color: tokens.anchor,
            textShadow: `0 0 50px ${tokens.anchor}66`,
          }}
        >
          {after}
        </div>
      </div>
    </div>
  );
}
