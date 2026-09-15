import {useCurrentFrame, useVideoConfig} from 'remotion';
import {interpolate} from 'remotion';

interface Props {
  shot: any;
  tokens: any;
}

export function ImageLedCover({shot, tokens}: Props) {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  // 提取标题
  const titleMatch = shot.visual.match(/\"([^\"]+)\"/) || shot.visual.match(/【([^】]+)】/);
  const title = titleMatch ? titleMatch[1] : shot.vo.slice(0, 15);

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
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* 满铺底图占位 */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: `radial-gradient(circle at 50% 50%, ${tokens.anchor}40, ${tokens.bg} 70%)`,
          zIndex: 0,
        }}
      />

      {/* 超大标题 */}
      <div
        style={{
          position: 'relative',
          zIndex: 1,
          fontSize: 64,
          fontWeight: 800,
          color: tokens.text,
          textAlign: 'center',
          lineHeight: 1.2,
          maxWidth: '80%',
          transform: `scale(${1 + Math.sin(frame * 0.05) * 0.03})`,
          textShadow: `0 0 30px ${tokens.bg}80`,
        }}
      >
        {title}
      </div>

      {/* 下方小标签 */}
      {shot.vo && (
        <div
          style={{
            position: 'relative',
            zIndex: 1,
            marginTop: 32,
            fontSize: 20,
            fontWeight: 500,
            color: tokens.anchor,
            opacity: 0.8,
            letterSpacing: '1px',
          }}
        >
          {shot.vo.slice(0, 30)}...
        </div>
      )}
    </div>
  );
}