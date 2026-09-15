import {Img, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {interpolate} from 'remotion';

interface Props {
  shot: any;
  tokens: {bg: string; anchor: string; text: string};
  ipImage?: string;
  assets?: {ip_poses?: {[pose: string]: string}};
}

const PAPER = '#FAFAF6';
const INK = '#1A1A1A';
const RED = '#E23A2E';
const BLUE = '#2B6CB0';

/** 场景元素：每镜一个手绘风主体（黑粗线 + 红/蓝批注，ian-xiaohei 原则——小人参与核心动作） */
function Scene({kind, frame, fps, note}: {kind: string; frame: number; fps: number; note?: string}) {
  const pop = (at: number) => interpolate(frame, [at, at + 8], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  if (kind === 'countdown') {
    // 翻页倒计时牌：72:00:00 起每 20 帧跳一次（确定性）
    const base = 72 - Math.floor(frame / 20);
    const t = `${String(base).padStart(2, '0')}:00:00`;
    const flip = frame % 20 < 4;
    return (
      <div style={{position: 'relative'}}>
        <div style={{
          background: '#fff', border: `6px solid ${INK}`, borderRadius: 16, padding: '28px 56px',
          fontFamily: 'Menlo, monospace', fontSize: 110, fontWeight: 900, color: INK,
          boxShadow: `0 10px 0 ${INK}`, transform: flip ? `scaleY(0.92)` : 'none',
        }}>{t}</div>
        {note && (
          <div style={{position: 'absolute', right: -30, top: -34, fontSize: 40, fontWeight: 900, color: RED,
                       transform: `rotate(8deg) scale(${pop(14)})`}}>{note}</div>
        )}
      </div>
    );
  }
  if (kind === 'pit') {
    // 地面裂缝 + 陷阱
    return (
      <div style={{position: 'relative', width: 640, height: 300}}>
        <svg width="640" height="300" viewBox="0 0 640 300">
          <path d="M40 60 L180 150 L120 160 L300 260 L280 190 L480 240 L420 150 L600 60"
                fill="none" stroke={INK} strokeWidth="10" strokeLinejoin="round"
                strokeDasharray="2000" strokeDashoffset={2000 - 2000 * pop(10)} />
        </svg>
        {note && (
          <div style={{position: 'absolute', left: 200, top: 40, fontSize: 72, fontWeight: 900, color: RED,
                       transform: `rotate(-6deg) scale(${pop(30)})`}}>{note}</div>
        )}
      </div>
    );
  }
  if (kind === 'sign') {
    // 举牌：大牌子 + 支撑杆
    return (
      <div style={{position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
        <div style={{
          background: '#fff', border: `6px solid ${INK}`, borderRadius: 12, padding: '24px 64px',
          fontSize: 84, fontWeight: 900, color: INK, boxShadow: `0 8px 0 ${INK}`,
          transform: `scale(${pop(8)})`,
        }}>{note || '方法'}</div>
        <div style={{width: 14, height: 120, background: INK}} />
      </div>
    );
  }
  if (kind === 'stage') {
    // 对比台：两块定价表 + 对错章
    return (
      <div style={{display: 'flex', gap: 40}}>
        {['¥A', '¥B'].map((p, i) => (
          <div key={p} style={{position: 'relative'}}>
            <div style={{
              background: '#fff', border: `5px solid ${INK}`, borderRadius: 10, padding: '18px 42px',
              fontSize: 60, fontWeight: 900, color: INK, transform: `scale(${pop(8 + i * 8)})`,
            }}>{p}</div>
            <div style={{position: 'absolute', right: -22, top: -26, fontSize: 44, fontWeight: 900,
                         color: i === 0 ? RED : BLUE, transform: `rotate(${i === 0 ? -12 : 10}deg) scale(${pop(26 + i * 8)})`,
                         border: `4px solid ${i === 0 ? RED : BLUE}`, borderRadius: '50%', padding: '2px 10px'}}>
              {i === 0 ? '对' : '错'}
            </div>
          </div>
        ))}
      </div>
    );
  }
  return null;
}

/** A-roll IP 镜头 v3：白纸卡舞台 + 角色姿态状态机 + 手绘场景。
 * assets.ip_poses 提供姿态切图（idle/point/confident/shock）时 → 剪纸角色：按镜头序轮换姿态 + 呼吸微动；
 * 无切图时降级为原 flip-book 单图模式（不阻塞出片）。
 * ponytail: 姿态按镜头序轮换，待分镜 shot 带 beat 字段后换成语义驱动（contrast→shock / point→confident）。 */
export function ARollScene({shot, tokens, ipImage, assets}: Props) {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const cfg = shot.config ?? {};
  const sceneKind: string = cfg.scene ?? 'sign';
  const imgSrc = ipImage ? staticFile(ipImage) : undefined;

  // 姿态状态机：规范姿态名（idle/point/confident/shock/question）优先；
  // 全是非规范名（如 ip_think01…）→ 全池排序轮换。呼吸 ±1.5% 两.4s 一周期
  const poses: Record<string, string> = assets?.ip_poses ?? {};
  const CANON = ['idle', 'point', 'confident', 'shock', 'question'];
  const canonPoses = CANON.filter((p) => poses[p]);
  const posePool = canonPoses.length ? canonPoses : Object.keys(poses).sort();
  const shotIdx = parseInt(String(shot.id ?? '').replace(/\D/g, ''), 10) || 0;
  const poseSrc = posePool.length ? staticFile(poses[posePool[shotIdx % posePool.length]]) : undefined;
  const charSrc = poseSrc ?? imgSrc;
  const breath = 1 + Math.sin((frame / fps) * Math.PI * 2 / 2.4) * 0.015;

  // flip-book：镜像交替 + 弹跳（简笔小人原地蹦）
  const flip = Math.floor(frame / 12) % 2 === 1 ? -1 : 1;
  const bounce = Math.abs(Math.sin((frame / fps) * Math.PI * 2 / 1.2)) * 10;
  // 入场：小人从下方弹入
  const enter = interpolate(frame, [4, 18], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  return (
    <div style={{width: '100%', height: '100%', background: tokens.bg, position: 'relative', display: 'flex',
                 alignItems: 'center', justifyContent: 'center'}}>
      {/* 白纸卡舞台 */}
      <div style={{
        position: 'absolute', left: 90, right: 90, top: 70, bottom: 190,
        background: PAPER, borderRadius: 28, border: `5px solid ${INK}`,
        boxShadow: `0 14px 0 rgba(0,0,0,0.45)`,
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 70,
        overflow: 'hidden',
      }}>
        {/* 场景主体（左） */}
        <div style={{flex: 1, display: 'flex', justifyContent: 'center'}}>
          <Scene kind={sceneKind} frame={frame} fps={fps} note={cfg.note} />
        </div>
        {/* 角色（右）：姿态切图优先（呼吸/镜像/弹跳），无切图降级 flip-book 单图 */}
        {charSrc && (
          <div style={{
            width: 380, height: 460, position: 'relative', flexShrink: 0,
            transform: `translateY(${(1 - enter) * 80 - bounce}px)`,
            opacity: enter,
          }}>
            <div style={{position: 'absolute', bottom: 0, left: '50%', transform: 'translateX(-50%)',
                         width: 300, height: 26, borderRadius: '50%', background: `${INK}22`}} />
            <Img src={charSrc} style={{
              width: '100%', height: '100%', objectFit: 'contain',
              mixBlendMode: 'multiply',
              transform: `scaleX(${flip}) scale(${breath})`,
            }} />
          </div>
        )}
      </div>
    </div>
  );
}
