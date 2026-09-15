import {useCurrentFrame} from 'remotion';

interface Props {
  shot: any;
  timingSegs: any[];
  tokens: any;
  ipImage?: string;
  assets: any;
}

export function ChapterCard({shot, tokens}: Props) {
  const frame = useCurrentFrame();

  // 提取序号和标题
  const numMatch = shot.vo.match(/(\d+)[:.、]/);
  const num = numMatch ? numMatch[1] : '';
  const title = shot.vo.replace(numMatch?.[0] || '', '').trim().slice(0, 15);

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        background: `linear-gradient(135deg, ${tokens.bg}, ${tokens.anchor}20)`,
        color: tokens.text,
        padding: 40,
      }}
    >
      <div
        style={{
          fontSize: 180,
          fontWeight: 900,
          color: tokens.anchor,
          opacity: 0.15,
          position: 'absolute',
          top: '20%',
          right: '10%',
        }}
      >
        {num.padStart(2, '0')}
      </div>
      <div
        style={{
          fontSize: 56,
          fontWeight: 800,
          color: tokens.anchor,
          marginTop: 40,
          transform: `scale(${1 + Math.sin(frame * 0.1) * 0.04})`,
        }}
      >
        第{num}步
      </div>
      <div
        style={{
          fontSize: 42,
          fontWeight: 700,
          marginTop: 16,
          opacity: frame > 15 ? 1 : 0,
          transition: 'opacity 0.3s',
        }}
      >
        {title}
      </div>
      <div
        style={{
          width: 200,
          height: 4,
          background: tokens.anchor,
          marginTop: 32,
          borderRadius: 2,
          opacity: 0.8,
        }}
      />
    </div>
  );
}