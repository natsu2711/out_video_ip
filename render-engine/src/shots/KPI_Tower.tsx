import {useCurrentFrame, useVideoConfig} from 'remotion';
import {interpolate, spring} from 'remotion';

interface Props {
  shot: any;
  tokens: any;
}

export function KPI_Tower({shot, tokens}: Props) {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  // 提取 KPI 数据（简化版：从 visual 提取数字）
  const numbers = shot.visual.match(/\d+/g) || ['100', '200', '300', '400'];
  const numKPIs = Math.min(4, numbers.length);

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
          fontSize: 40,
          fontWeight: 800,
          color: tokens.anchor,
          marginBottom: 64,
          opacity: frame > 15 ? 1 : 0,
        }}
      >
        关键指标
      </div>

      {/* KPI 塔 */}
      <div
        style={{
          display: 'flex',
          gap: 24,
          alignItems: 'flex-end',
          height: 300,
        }}
      >
        {Array.from({length: numKPIs}).map((_, i) => {
          const delay = 20 + i * 10;
          const heightPercent = parseInt(numbers[i] || '100', 10);
          const opacity = frame > delay ? 1 : 0;
          const barHeight = spring({
            frame: frame - delay,
            fps,
            config: {damping: 15, stiffness: 70},
          });

          return (
            <div
              key={i}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 12,
                opacity,
              }}
            >
              {/* KPI 柱 */}
              <div
                style={{
                  width: 60,
                  height: `${heightPercent * barHeight}px`,
                  background: `linear-gradient(to top, ${tokens.anchor}40, ${tokens.anchor})`,
                  borderRadius: '8px 8px 0 0',
                  transition: 'all 0.3s',
                }}
              />

              {/* 数值 */}
              <div
                style={{
                  fontSize: 28,
                  fontWeight: 800,
                  color: tokens.anchor,
                }}
              >
                {numbers[i]}%
              </div>
            </div>
          );
        })}
      </div>

      {/* 说明文字 */}
      {shot.vo && (
        <div
          style={{
            marginTop: 48,
            fontSize: 20,
            fontWeight: 500,
            color: tokens.text,
            opacity: 0.7,
            textAlign: 'center',
            maxWidth: '80%',
          }}
        >
          {shot.vo.slice(0, 50)}
        </div>
      )}
    </div>
  );
}