import {useCurrentFrame, useVideoConfig} from 'remotion';
import {interpolate, spring} from 'remotion';

interface Props {
  shot: any;
  timingSegs: any[];
  tokens: any;
  ipImage?: string;
  assets: any;
}

/** 多项并列网格卡：2×2 / 2×3 网格逐格点亮 + 逐项编号。
 * 条目取 shot.motion[]，不足时用 visual 文案兜底为 2 格。 */
export function ListGrid({shot, tokens}: Props) {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const items = (shot.motion || []).filter(Boolean).slice(0, 6);
  const list = items.length >= 2 ? items : [String(shot.visual || '').slice(0, 12) || '要点 1', '要点 2'];
  const n = list.length;
  const cols = n <= 4 ? 2 : 3;

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        background: tokens.bg,
        color: tokens.text,
        padding: 70,
      }}
    >
      {/* 标题 */}
      <div
        style={{
          fontSize: 42,
          fontWeight: 800,
          color: tokens.anchor,
          marginBottom: 56,
          textAlign: 'center',
          opacity: frame > 6 ? 1 : 0,
        }}
      >
        {(shot.intent || '').slice(0, 14) || '要点'}
      </div>

      {/* 网格 */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${cols}, 1fr)`,
          gap: 28,
        }}
      >
        {list.map((label: string, i: number) => {
          const delay = 15 + i * 12;
          const pop = spring({frame: frame - delay, fps, config: {damping: 12, stiffness: 90}});
          return (
            <div
              key={i}
              style={{
                background: `${tokens.text}0d`,
                border: `2px solid ${tokens.anchor}33`,
                borderRadius: 20,
                padding: '36px 24px',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 18,
                opacity: pop,
                transform: `translateY(${interpolate(pop, [0, 1], [40, 0])}px)`,
              }}
            >
              {/* 编号 */}
              <div
                style={{
                  fontSize: 40,
                  fontWeight: 900,
                  color: tokens.anchor,
                  opacity: 0.9,
                }}
              >
                {String(i + 1).padStart(2, '0')}
              </div>
              {/* 条目 */}
              <div
                style={{
                  fontSize: 28,
                  fontWeight: 600,
                  lineHeight: 1.45,
                  textAlign: 'center',
                }}
              >
                {label}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
