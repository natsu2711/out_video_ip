import React, {Fragment} from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {interpolate, spring} from 'remotion';

interface Props {
  shot: any;
  timingSegs: any[];
  tokens: any;
  ipImage?: string;
  assets: any;
}

/** 步骤卡（横排 1→2→3）：编号逐个点亮 + flex 连接线（无绝对定位，版式稳定）+ 当前进度高亮。
 * 条目取 shot.motion[]（剥离锚点标注），缺省用「步骤 N」。 */
function cleanLabel(s: string): string {
  // 去掉「（锚：'xxx'）」等内部标注
  return s.replace(/（[^）]*）/g, '').replace(/\([^)]*\)/g, '').trim();
}

export function StepsCard({shot, tokens}: Props) {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const steps = (shot.motion || []).map(cleanLabel).filter(Boolean).slice(0, 4);
  const items = steps.length >= 2 ? steps : ['步骤 1', '步骤 2', '步骤 3'];
  const n = items.length;
  // 当前高亮步：随时间推进（每步停留 2.2s）
  const current = Math.min(n - 1, Math.floor(frame / (fps * 2.2)));

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
        padding: 60,
      }}
    >
      {/* 标题（intent 去内部标注） */}
      <div
        style={{
          fontSize: 44,
          fontWeight: 800,
          color: tokens.anchor,
          marginBottom: 90,
          textAlign: 'center',
          opacity: frame > 8 ? 1 : 0,
          letterSpacing: 2,
        }}
      >
        {cleanLabel(shot.intent || '').slice(0, 14) || '流程'}
      </div>

      {/* 横排步骤 + flex 连接线 */}
      <div style={{display: 'flex', alignItems: 'flex-start', width: '100%'}}>
        {items.map((label: string, i: number) => {
          const delay = 12 + i * 20;
          const pop = spring({frame: frame - delay, fps, config: {damping: 12, stiffness: 90}});
          const active = i <= current;
          const isLast = i === n - 1;
          return (
            <Fragment key={i}>
              <div
                style={{
                  flex: isLast ? 0 : 1,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  width: isLast ? undefined : `${100 / n}%`,
                }}
              >
                {/* 序号圆 */}
                <div
                  style={{
                    width: 104,
                    height: 104,
                    borderRadius: '50%',
                    background: active ? tokens.anchor : 'transparent',
                    border: `4px solid ${active ? tokens.anchor : `${tokens.text}44`}`,
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    fontSize: 48,
                    fontWeight: 800,
                    color: active ? tokens.bg : `${tokens.text}66`,
                    transform: `scale(${Math.max(0.01, pop)})`,
                  }}
                >
                  {i + 1}
                </div>
                {/* 步骤文案 */}
                <div
                  style={{
                    marginTop: 30,
                    fontSize: 30,
                    fontWeight: 600,
                    textAlign: 'center',
                    lineHeight: 1.4,
                    color: i === current ? tokens.anchor : `${tokens.text}aa`,
                    opacity: pop,
                    maxWidth: 240,
                    wordBreak: 'break-all',
                  }}
                >
                  {label}
                </div>
              </div>
              {/* 连接线：flex 占位元素（非绝对定位，版式稳定） */}
              {!isLast && (
                <div
                  style={{
                    height: 4,
                    flex: 1,
                    marginTop: 50,
                    marginLeft: -10,
                    marginRight: -10,
                    borderRadius: 2,
                    background: i < current ? tokens.anchor : `${tokens.text}22`,
                    transformOrigin: 'left',
                    transform: `scaleX(${interpolate(
                      frame,
                      [delay + 15, delay + 30],
                      [0, 1],
                      {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
                    )})`,
                  }}
                />
              )}
              </Fragment>
          );
        })}
      </div>
    </div>
  );
}
