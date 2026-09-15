import {useCurrentFrame} from 'remotion';
import {interpolate} from 'remotion';

interface Props {
  shot: any;
  tokens: any;
}

export function CompareCardEnhanced({shot, tokens}: Props) {
  const frame = useCurrentFrame();

  // 提取对比内容（简化版：按左右分割）
  const parts = shot.visual.split('右') || ['', shot.visual];
  const leftText = parts[0].replace('左', '').replace('：', '').slice(0, 30) || '现状';
  const rightText = parts[1]?.slice(0, 30) || '目标';

  const leftOpacity = frame > 10 ? 1 : 0;
  const rightOpacity = frame > 25 ? 1 : 0;

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        background: tokens.bg,
        position: 'relative',
      }}
    >
      {/* 左栏 */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          padding: 40,
          opacity: leftOpacity,
          transform: `translateX(${interpolate(leftOpacity, [0, 1], [-30, 0])}px)`,
          borderRight: `2px solid ${tokens.anchor}40`,
        }}
      >
        <div style={{fontSize: 56, fontWeight: 800, color: '#666', marginBottom: 16}}>
          BEFORE
        </div>
        <div style={{fontSize: 32, fontWeight: 600, color: tokens.text, textAlign: 'center'}}>
          {leftText}
        </div>
      </div>

      {/* 右栏 */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          padding: 40,
          opacity: rightOpacity,
          transform: `translateX(${interpolate(rightOpacity, [0, 1], [30, 0])}px)`,
        }}
      >
        <div style={{fontSize: 56, fontWeight: 800, color: tokens.anchor, marginBottom: 16}}>
          AFTER
        </div>
        <div style={{fontSize: 32, fontWeight: 600, color: tokens.text, textAlign: 'center'}}>
          {rightText}
        </div>
      </div>

      {/* VS 标记 */}
      <div
        style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          fontSize: 48,
          fontWeight: 900,
          color: tokens.anchor,
          opacity: frame > 30 ? 1 : 0,
        }}
      >
        VS
      </div>
    </div>
  );
}