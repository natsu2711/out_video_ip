/** 图层宿主：一个镜头内的多层合成（在主配方之上、氛围叠层/字幕之下）。
 * 数据契约：shot.layers: ShotLayer[]（数组顺序 = z 序，后面的更高）。
 * 稳定性纪律：图层不进相机变换（位置稳定）；每层有入场动效 + 时间窗，静态内容由
 * 全局 Ken Burns/StaticNoise 兜底防冻结。CardSlot 由调用方注入（CLI=webpack 版，Studio=Vite 版）。 */
import {AbsoluteFill, Img, OffthreadVideo, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {ColorTint, Embers, Grain, LightSweep, Particles, SnowFall, Vignette} from '../overlays';

export interface ShotLayer {
  id: string;
  kind: 'overlay' | 'card' | 'media_image' | 'media_video' | 'text';
  ref?: string;            // overlay 名 / 卡 slug / staticFile 相对路径
  label?: string;
  enabled?: boolean;       // 缺省 true
  in_ms?: number;          // 镜头内相对时刻，缺省 0
  out_ms?: number | null;  // 缺省到镜头末
  x?: number;              // 0..1 锚点（画面比例），缺省 0.5
  y?: number;
  scale?: number;          // 缺省 1
  opacity?: number;        // 缺省 1
  presentation?: 'none' | 'rise_fade' | 'slam_in' | 'blur_focus';
  /** 素材层动态（media 专用）：全屏→缩到右上角 / 小→占满全屏 / 缓推 / 缓拉 */
  motion?: 'none' | 'corner_takeover' | 'grow_takeover' | 'kenburns_in' | 'kenburns_out';
  /** 出场：设了 out_ms 后的退场方式（fade=末 8 帧淡出，none=硬切） */
  exit?: 'fade' | 'none';
  config?: {TEXT?: string[]; STEPS?: string[]; CONFIG?: Record<string, unknown>; text?: string; size?: number; color?: string; weight?: number; font?: string};
}

const ENTR_FRAMES = 8;
// 字幕带安全区（video-use SUB_FORCE_STYLE 规则：竖版字幕占底部 ~30%）：
// 未显式给 y 的 media/card 层默认锚在安全区上沿，防止新图层被字幕盖住
const SUBTITLE_SAFE_Y = 0.62;

function entrance(kind: string | undefined, localFrame: number): {opacity: number; dy: number; scaleMul: number; blur: number} {
  const t = Math.min(1, localFrame / ENTR_FRAMES);
  if (!kind || kind === 'none') return {opacity: 1, dy: 0, scaleMul: 1, blur: 0};
  if (kind === 'rise_fade') return {opacity: t, dy: (1 - t) * 36, scaleMul: 1, blur: 0};
  if (kind === 'slam_in') return {opacity: t, dy: 0, scaleMul: 1 + (1 - t) * 0.18, blur: 0};
  if (kind === 'blur_focus') return {opacity: t, dy: 0, scaleMul: 1, blur: (1 - t) * 14};
  return {opacity: 1, dy: 0, scaleMul: 1, blur: 0};
}

function overlayNode(name: string, idx: number, anchor: string): React.ReactNode {
  const map: Record<string, React.ReactNode> = {
    particles: <Particles seed={idx + 7} color={anchor} opacity={0.4} />,
    light_sweep: <LightSweep color={anchor} opacity={0.16} />,
    grain: <Grain opacity={0.05} />,
    vignette: <Vignette strength={0.5} />,
    tint_warm: <ColorTint tone="warm" opacity={0.1} />,
    tint_cool: <ColorTint tone="cool" opacity={0.1} />,
    snow: <SnowFall opacity={0.6} />,
    embers: <Embers color={anchor} opacity={0.55} />,
  };
  return map[name] ?? null;
}

export function LayerHost({shot, tokens, layerCard}: {
  shot: any;
  tokens: {bg: string; anchor: string; text: string};
  layerCard?: React.ComponentType<{slug: string; config: any; tokens: any}>;
}) {
  const frame = useCurrentFrame();
  const {fps, durationInFrames, width: canvasW} = useVideoConfig();
  const layers = ((shot?.layers ?? []) as ShotLayer[]).filter((l) => l.enabled !== false);
  if (layers.length === 0 || !layerCard) return null;
  const CardSlot = layerCard;

  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      {layers.map((L, i) => {
        const startF = Math.max(0, Math.floor(((L.in_ms ?? 0) / 1000) * fps));
        const endF = L.out_ms != null ? Math.ceil((L.out_ms / 1000) * fps) : durationInFrames;
        if (frame < startF || frame >= endF) return null;
        const ent = entrance(L.presentation, frame - startF);
        // 出场：设了 out_ms 的层，退场前 8 帧淡出（入场对称）
        const spanF = Math.max(1, endF - startF);
        const exitT = (endF - frame) / 8;
        if (L.out_ms != null && (L.exit ?? 'fade') === 'fade' && exitT < 1) {
          ent.opacity *= Math.max(0, exitT);
        }
        const scale = (L.scale ?? 1) * ent.scaleMul;
        // y 缺省按 kind 分配：card/媒体层锚字幕安全区上沿；text 缺省贴字幕带上方；overlay 全屏
        const defaultY = L.kind === 'overlay' ? 0.5 : L.kind === 'text' ? 0.78 : SUBTITLE_SAFE_Y;
        const style: React.CSSProperties = {
          position: 'absolute',
          left: `${(L.x ?? 0.5) * 100}%`,
          top: `${(L.y ?? defaultY) * 100}%`,
          transform: `translate(calc(-50% + 0px), calc(-50% + ${ent.dy}px)) scale(${scale})`,
          opacity: (L.opacity ?? 1) * ent.opacity,
          filter: ent.blur > 0 ? `blur(${ent.blur}px)` : undefined,
          zIndex: i,
        };

        if (L.kind === 'overlay') {
          return <AbsoluteFill key={L.id} style={{zIndex: i}}>{overlayNode(L.ref ?? '', i, tokens.anchor)}</AbsoluteFill>;
        }
        if (L.kind === 'card') {
          if (!layerCard) return null;
          // 卡层盒按画布宽 50%（横竖屏自适应）：内容统一 1920×1080 设计 × 0.5 壳
          return (
            <div key={L.id} style={style}>
              <div style={{transform: 'translate(-50%, -50%)', position: 'absolute', left: '50%', top: '50%'}}>
                <div style={{width: canvasW / 2, height: canvasW / 2 * 0.5625, borderRadius: 18, overflow: 'hidden',
                             boxShadow: '0 18px 60px rgba(0,0,0,0.45)', background: '#fff'}}>
                <div style={{width: 1920, height: 1080,
                             transform: `scale(${canvasW / 2 / 1920})`, transformOrigin: 'top left'}}>
                  <CardSlot slug={L.ref ?? ''} config={L.config ?? {}} tokens={tokens} />
                </div>
                </div>
              </div>
            </div>
          );
        }
        if (L.kind === 'media_image' || L.kind === 'media_video') {
          // 动态预设（跨整个时间窗插值，确定性）：
          //   corner_takeover 全屏→缩到右上角 | grow_takeover 小→突然占满全屏
          //   kenburns_in 缓推近 | kenburns_out 缓拉远
          const m = L.motion ?? 'none';
          const span = Math.max(1, endF - startF);
          const t = Math.min(1, Math.max(0, (frame - startF) / span));
          let mx = (L.x ?? 0.5), my = (L.y ?? 0.62), ms = L.scale ?? 1;
          if (m === 'corner_takeover') {
            ms = ms * (2.4 - 1.5 * t); mx = mx + (0.86 - mx) * t; my = my + (0.16 - my) * t;
          } else if (m === 'grow_takeover') {
            ms = ms * (0.45 + 1.3 * t); mx = mx + (0.5 - mx) * t; my = my + (0.5 - my) * t;
          } else if (m === 'kenburns_in') {
            ms = ms * (1 + 0.18 * t);
          } else if (m === 'kenburns_out') {
            ms = ms * (1.18 - 0.18 * t);
          }
          const mStyle: React.CSSProperties = {
            ...style,
            left: `${mx * 100}%`, top: `${my * 100}%`,
            transform: `translate(-50%, -50%) scale(${ms * ent.scaleMul})`,
          };
          const boxStyle: React.CSSProperties = L.kind === 'media_video'
            ? {maxWidth: '94vw', maxHeight: '88vh', borderRadius: 14, boxShadow: '0 16px 50px rgba(0,0,0,0.4)', display: 'block'}
            : {maxWidth: '94vw', maxHeight: '88vh', borderRadius: 14, boxShadow: '0 16px 50px rgba(0,0,0,0.4)', display: 'block'};
          return L.kind === 'media_image' ? (
            <div key={L.id} style={mStyle}>
              <Img src={staticFile(L.ref ?? '')} style={boxStyle} />
            </div>
          ) : (
            <div key={L.id} style={mStyle}>
              <OffthreadVideo src={staticFile(L.ref ?? '')} muted style={boxStyle} />
            </div>
          );
        }
        if (L.kind === 'text') {
          const cfg = L.config ?? {};
          const FONT_MAP: Record<string, string> = {
            serif: "'Songti SC','STSong','Noto Serif SC',serif",
            mono: "'SF Mono','Menlo','Consolas',monospace",
          };
          return (
            <div key={L.id} style={style}>
              <div style={{
                fontWeight: cfg.weight ?? 900,
                fontFamily: cfg.font === 'serif' || cfg.font === 'mono' ? FONT_MAP[cfg.font] : undefined,
                fontSize: cfg.size ?? 64, color: cfg.color ?? tokens.text,
                letterSpacing: '-0.03em', lineHeight: 1.1,
                textShadow: '0 2px 18px rgba(0,0,0,0.35)',
                whiteSpace: 'nowrap',
              }}>
                {cfg.text ?? (cfg.TEXT ?? []).join(' ')}
              </div>
            </div>
          );
        }
        return null;
      })}
    </AbsoluteFill>
  );
}