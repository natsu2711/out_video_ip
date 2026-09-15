import {useCurrentFrame, useVideoConfig} from 'remotion';
import {interpolate, spring} from 'remotion';

interface Props {
  shot: any;
  tokens: any;
}

export function MatrixHero({shot, tokens}: Props) {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  // 提取矩阵元素（简化版：从 visual 提取关键词）
  const keywords = shot.visual.match(/[^\s，。！？]{2,6}/g) || [
    '预测',
    '对比',
    '极速暴露',
  ];
  const numItems = Math.min(9, keywords.length);

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
        position: 'relative',
      }}
    >
      {/* 背景网格装饰 */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          backgroundImage: `
            linear-gradient(${tokens.anchor}10 1px, transparent 1px),
            linear-gradient(90deg, ${tokens.anchor}10 1px, transparent 1px)
          `,
          backgroundSize: '60px 60px',
          opacity: 0.3,
          zIndex: 0,
        }}
      />

      {/* 矩阵标题 */}
      <div
        style={{
          position: 'relative',
          zIndex: 1,
          fontSize: 40,
          fontWeight: 800,
          color: tokens.anchor,
          marginBottom: 48,
          textAlign: 'center',
          letterSpacing: '2px',
        }}
      >
        CORE MATRIX
      </div>

      {/* 矩阵网格 */}
      <div
        style={{
          position: 'relative',
          zIndex: 1,
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 20,
          width: '100%',
          maxWidth: 800,
        }}
      >
        {Array.from({length: numItems}).map((_, i) => {
          const delay = 20 + Math.floor(i / 3) * 10 + (i % 3) * 5;
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
                background: `${tokens.anchor}20`,
                border: `2px solid ${tokens.anchor}60`,
                borderRadius: 12,
                padding: 20,
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                minHeight: 100,
                opacity,
                transform: `scale(${scale})`,
                transition: 'all 0.3s',
              }}
            >
              <div
                style={{
                  fontSize: 24,
                  fontWeight: 700,
                  color: tokens.anchor,
                  textAlign: 'center',
                }}
              >
                {keywords[i]}
              </div>
            </div>
          );
        })}
      </div>

      {/* 底部说明 */}
      {shot.vo && (
        <div
          style={{
            position: 'relative',
            zIndex: 1,
            marginTop: 48,
            fontSize: 18,
            fontWeight: 500,
            color: tokens.text,
            opacity: 0.7,
            textAlign: 'center',
            maxWidth: '90%',
          }}
        >
          {shot.vo.slice(0, 60)}
        </div>
      )}
    </div>
  );
}