/** Studio 实时预览播放器：@remotion/player 驱动真实渲染组件（ShotRenderer）。
 * 与 CLI 渲染共用同一套组件与数据契约（JobData），所见即所渲。 */
import React, {forwardRef} from 'react';
import {Player, type PlayerRef} from '@remotion/player';
import {ShotRenderer} from '../../../../render-engine/src/compositions/ShotRenderer';
import {StudioCardHost} from './StudioCardHost';

const StudioShot: React.FC<{data: any; shotId: string}> = ({data, shotId}) => (
  <ShotRenderer
    data={data}
    shotId={shotId}
    cardHost={(p) => <StudioCardHost {...p} />}
    layerCard={StudioLayerCard}
  />
);

/** 图层卡槽：Vite 动态求值版（内容注入 + 缓存键与画布主卡同机制）。 */
const StudioLayerCard: React.FC<{slug: string; config: any; tokens: any}> = ({slug, config, tokens}) => {
  const [Card, setCard] = React.useState<React.ComponentType<any> | null>(null);
  const key = JSON.stringify(config ?? {});
  React.useEffect(() => {
    let alive = true;
    import('./StudioCardHost').then(({CARD_REGISTRY}) => {
      const entry = CARD_REGISTRY[slug];
      if (!entry) return;
      // 复用 buildCardContent（经 StudioCardHost 模块间接拿到，避免直接引 cards/index）
      const content = buildLayerContent(entry, config ?? {});
      loadLayerCard(slug, content).then((m) => {
        if (alive) setCard(() => m);
      }).catch(() => undefined);
    });
    return () => {
      alive = false;
    };
  }, [slug, key]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!Card) return <div style={{width: '100%', height: '100%', background: '#fff'}} />;
  // 设计尺寸契约：输出原稿，缩放由 LayerHost 计算
  return <Card />;
};

function buildLayerContent(entry: any, config: any): Record<string, unknown> {
  // 泛化槽位 + 形状感知：对象槽位（如 ROWS:{cls,text}）合并进默认形状，只覆盖 text
  const inj: Record<string, unknown> = {};
  const cap16 = (a: string[]) => a.map((t: string) => (t.length > 16 ? t.slice(0, 15) + '…' : t));
  const defaults = (entry as any).slotDefaults ?? {};
  for (const [key, n] of Object.entries(entry.arities ?? {})) {
    if (typeof n !== 'number' || (n as number) <= 0) continue;
    if (key === 'SLOTS') {
      const slots = config?.SLOTS as any[] | undefined;
      if (slots?.length) inj.SLOTS = slots.slice(0, n as number);
      continue;
    }
    const manual = (config?.[key] as string[] | undefined) ?? [];
    const texts = cap16(manual);
    const shape = defaults[key] ?? [];
    inj[key] = texts.length > 0
      ? (shape.length > 0 && typeof shape[0] === 'object' && shape[0] !== null
          ? texts.map((t: string, i: number) => ({...(shape[i % shape.length] as object), text: t}))
          : texts)
      : (shape.length > 0 && typeof shape[0] === 'object' ? shape.slice(0, n as number) : []);
  }
  if (config?.CONFIG) inj.CONFIG = config.CONFIG;
  return inj;
}

async function loadLayerCard(slug: string, content: Record<string, unknown>): Promise<React.ComponentType<any>> {
  const {loadCardEvaluating} = await import('./cardLoader');
  return loadCardEvaluating(slug, content);
}

export function shotDurationFrames(shot: any, fps: number): number {
  return Math.max(1, Math.floor(((shot.time.end_ms - shot.time.start_ms) / 1000) * fps));
}

export const StudioShotPlayer = forwardRef<PlayerRef, {
  data: any;
  shotId: string;
  className?: string;
  style?: React.CSSProperties;
  loop?: boolean;
}>(function StudioShotPlayer({data, shotId, className, style, loop = true}, ref) {
  const shot = data?.storyboard?.shots?.find((s: any) => s.id === shotId);
  if (!data || !shot) {
    return <div className={className} style={style}>无预览数据</div>;
  }
  const fps = data.project.canvas.fps;
  const duration = shotDurationFrames(shot, fps);
  return (
    <Player
      ref={ref as any}
      component={StudioShot as any}
      inputProps={{data, shotId}}
      durationInFrames={duration}
      compositionWidth={data.project.canvas.width}
      compositionHeight={data.project.canvas.height}
      fps={fps}
      loop={loop}
      controls={false}
      style={{width: '100%', height: '100%', ...(style ?? {})}}
      className={className}
    />
  );
});
