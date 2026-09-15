import {useCurrentFrame, useVideoConfig, interpolate, spring} from 'remotion';
import {TYPE, weightFor, TIGHT} from '../lib/theme';

interface Props {
  shot: any;
  tokens: {bg: string; anchor: string; text: string};
  timingSegs: any[];
  ipImage?: string;
}

interface Ann {
  kind: 'highlight' | 'strike';
  word: string;
  color?: string;
  at_ms?: number; // 标注出现的镜头内相对时刻；缺省=镜头 55% 处
}

/** KineticTitle：逐字入场 + 手绘标注（马克笔道/划线）。
 *  吸收：remotion-dev_skills text-highlights 的交互语义 + guizang 瑞士字号阶梯。
 *  消融记录：@remotion/rough-notation 依赖与现有 remotion 4.0.216 无匹配版本
 *  （升全链风险 > 收益），标注改自绘 SVG（歪斜 + 圆角线帽近似手绘），零依赖。
 *  config: {
 *    text: string              // 标题（\n 分行）
 *    sub?: string              // 副文案
 *    annotate?: Ann            // 词标注：highlight=马克笔道 / strike=划掉
 *    charDur?: number          // 单字入场 ms（默认 260）
 *  } */
export function KineticTitle({shot, tokens}: Props) {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const cfg = shot.config ?? {};
  const text: string = cfg.text ?? shot.vo;
  const sub: string | undefined = cfg.sub;
  const ann: Ann | undefined = cfg.annotate;
  const charDur = cfg.charDur ?? 260;
  const STEP = 42;

  // 逐字入场：弹簧过冲（damping 13 → 落定时轻微回弹）+ 模糊聚焦（blur 10→0）
  const Chars = ({line, base}: {line: string; base: number}) => (
    <>
      {line.split('').map((ch, k) => {
        const localF = frame - Math.round((base + k * STEP) / 1000 * fps);
        const r = spring({frame: localF, fps, config: {damping: 13, stiffness: 110, mass: 0.9}});
        return (
          <span key={k} style={{
            display: 'inline-block', opacity: Math.min(1, r * 1.6),
            transform: `translateY(${(1 - r) * 64}px) scale(${0.72 + 0.28 * r})`,
            filter: `blur(${Math.max(0, (1 - r) * 10)}px)`,
            minWidth: ch === ' ' ? '0.3em' : undefined,
          }}>{ch === ' ' ? '\u00A0' : ch}</span>
        );
      })}
    </>
  );

  const durMs = shot.time.end_ms - shot.time.start_ms;
  const annAt = ann?.at_ms ?? durMs * 0.55;
  const annP = interpolate((frame / fps) * 1000, [annAt, annAt + 450], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

  /** 标注词：底道（highlight）或划线（strike），歪斜 -2° 手绘感，scaleX 0→1 */
  const Ann = ({word}: {word: string}) => {
    if (!ann) return <>{word}</>;
    const c = ann.color ?? tokens.anchor;
    const punch = spring({frame: frame - Math.round((annAt + 450) / 1000 * fps), fps,
                          config: {damping: 11, stiffness: 130}});
    return (
      <span style={{position: 'relative', display: 'inline-block', padding: '0 0.08em',
                    transform: `scale(${1.14 - 0.14 * Math.min(1, punch)})`}}>
        <span style={{position: 'relative', zIndex: 1}}>{word}</span>
        {ann.kind === 'highlight' ? (
          <span style={{
            position: 'absolute', left: '-2%', right: '-2%', top: '12%', bottom: '10%',
            background: c, opacity: 0.6, borderRadius: 6,
            transform: `scaleX(${annP}) rotate(-1.2deg)`, transformOrigin: 'left center',
          }} />
        ) : (
          <span style={{
            position: 'absolute', left: '-3%', right: '-3%', top: '52%', height: '0.09em',
            background: c, borderRadius: 4,
            transform: `scaleX(${annP}) rotate(-1.6deg)`, transformOrigin: 'left center',
          }} />
        )}
      </span>
    );
  };

  const lines = text.split('\n');
  const longest = Math.max(...lines.map((l) => l.replace(/\s/g, '').length), 1);
  const size = Math.round(Math.min(TYPE.display * 0.62, (1750 / longest) * 0.92));
  let cursor = 150;

  return (
    <div style={{width: '100%', height: '100%', background: tokens.bg, display: 'flex',
                 flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 34, padding: '0 80px'}}>
      {lines.map((line, i) => {
        const base = cursor;
        cursor += line.length * STEP + 180;
        if (ann && line.includes(ann.word)) {
          const at = line.indexOf(ann.word);
          const before = line.slice(0, at);
          const after = line.slice(at + ann.word.length);
          return (
            <div key={i} style={{fontSize: size, fontWeight: weightFor(size), color: tokens.text, ...TIGHT, textAlign: 'center'}}>
              <Chars line={before} base={base} />
              <Ann word={ann.word} />
              <Chars line={after} base={base + (before.length + ann.word.length) * STEP} />
            </div>
          );
        }
        return (
          <div key={i} style={{fontSize: size, fontWeight: weightFor(size), color: tokens.text, ...TIGHT, textAlign: 'center'}}>
            <Chars line={line} base={base} />
          </div>
        );
      })}
      {sub && (
        <div style={{fontSize: TYPE.h3, fontWeight: weightFor(TYPE.h3), color: `${tokens.text}99`, ...TIGHT}}>
          <Chars line={sub} base={cursor} />
        </div>
      )}
    </div>
  );
}
