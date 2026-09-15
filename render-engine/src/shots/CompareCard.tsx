import {useCurrentFrame} from 'remotion';

interface Props {
  shot: any;
  timingSegs: any[];
  tokens: any;
  ipImage?: string;
  assets: any;
}

export function CompareCard({shot, tokens}: Props) {
  const frame = useCurrentFrame();

  // 简化解析：假设 visual 包含左右描述
  const parts = shot.visual.split('右');
  const leftDesc = parts[0].replace('左', '').replace('：', '').slice(0, 20) || '等待外界反馈';
  const rightDesc = parts[1]?.slice(0, 20) || '主动制造反馈';

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        background: tokens.bg,
        color: tokens.text,
      }}
    >
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          padding: 30,
          opacity: frame > 5 ? 1 : 0.2,
          transition: 'opacity 0.3s',
          borderRight: `2px solid ${tokens.anchor}40`,
        }}
      >
        <div style={{fontSize: 56, fontWeight: 800, color: '#999'}}>{leftDesc}</div>
      </div>
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          padding: 30,
          opacity: frame > 20 ? 1 : 0.2,
          transition: 'opacity 0.3s',
        }}
      >
        <div style={{fontSize: 56, fontWeight: 800, color: tokens.anchor}}>{rightDesc}</div>
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