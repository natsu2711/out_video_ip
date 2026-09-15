import {useCurrentFrame, useVideoConfig} from 'remotion';
import {interpolate} from 'remotion';

interface Props {
  shot: any;
  timingSegs: any[];
  tokens: any;
  ipImage?: string;
  assets: any;
}

export function QuoteCard({shot, tokens}: Props) {
  const frame = useCurrentFrame();

  // 提取强调词：支持「」与 "" 两种引号
  const highlightMatchCN = shot.visual.match(/[「『]([^」』]+)[」』]/g) || [];
  const highlightMatchEN = shot.visual.match(/"([^"]+)"/g) || [];
  const allMatches = [...highlightMatchCN, ...highlightMatchEN];
  const highlight =
    allMatches[0]?.replace(/[「『」』"]/g, '') || shot.vo.slice(0, 10);

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
        padding: 50,
      }}
    >
      <div
        style={{
          fontSize: 32,
          fontWeight: 600,
          textAlign: 'center',
          lineHeight: 1.6,
          opacity: 0.9,
        }}
      >
        {shot.vo.split('—')[0]}
      </div>
      {highlight && (
        <div
          style={{
            fontSize: 48,
            fontWeight: 800,
            color: tokens.anchor,
            marginTop: 24,
            transform: `scale(${1 + Math.sin(frame * 0.08) * 0.06})`,
            textShadow: `0 0 20px ${tokens.anchor}40`,
          }}
        >
          {highlight}
        </div>
      )}
    </div>
  );
}