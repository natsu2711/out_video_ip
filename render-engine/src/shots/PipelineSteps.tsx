import {useCurrentFrame, useVideoConfig} from 'remotion';
import {interpolate, spring} from 'remotion';

interface Props {
  shot: any;
  tokens: any;
}

export function PipelineSteps({shot, tokens}: Props) {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  // 提取步骤（从 visual 或 motion 描述）
  const steps = shot.motion || [];
  const numSteps = Math.min(4, Math.max(2, steps.length || 3));

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        background: tokens.bg,
        color: tokens.text,
        padding: 40,
      }}
    >
      {/* 标题 */}
      <div
        style={{
          fontSize: 48,
          fontWeight: 800,
          color: tokens.anchor,
          marginBottom: 48,
          textAlign: 'center',
          opacity: frame > 15 ? 1 : 0,
          transform: `translateY(${interpolate(frame, [0, 20], [30, 0])}px)`,
        }}
      >
        流程步骤
      </div>

      {/* 步骤列表 */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 24,
          width: '80%',
        }}
      >
        {Array.from({length: numSteps}).map((_, i) => {
          const delay = 25 + i * 15;
          const opacity = frame > delay ? 1 : 0;
          const scale = spring({
            frame: frame - delay,
            fps,
            config: {damping: 12, stiffness: 80},
          });

          return (
            <div
              key={i}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 16,
                opacity,
                transform: `translateX(${interpolate(opacity, [0, 1], [50, 0])}px)`,
              }}
            >
              {/* 序号圈 */}
              <div
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: '50%',
                  background: tokens.anchor,
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                  fontSize: 24,
                  fontWeight: 800,
                  color: tokens.bg,
                }}
              >
                {i + 1}
              </div>

              {/* 步骤描述 */}
              <div
                style={{
                  flex: 1,
                  fontSize: 22,
                  fontWeight: 500,
                  lineHeight: 1.4,
                }}
              >
                {steps[i] || `步骤 ${i + 1} 描述`}
              </div>
            </div>
          );
        })}
      </div>

      {/* 箭头指示 */}
      <div
        style={{
          marginTop: 32,
          fontSize: 32,
          color: tokens.anchor,
          opacity: frame > 80 ? 0.6 : 0,
        }}
      >
        ↓
      </div>
    </div>
  );
}