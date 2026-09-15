/** 单镜头渲染体：ShotComposition 的主体，数据经 props 传入（不读 getInputProps）。
 * CLI 渲染（Remotion bundler）与 Studio 实时预览（Vite + @remotion/player）共用本组件。
 * cardHost 由调用方注入：CLI 传 webpack require.context 版 CardHost；
 * Studio 传 Vite 动态 import 版（卡内容注入要求模块求值前 setCardContent，两套加载器各自保证）。
 * 本文件禁止 import ../cards/*（cards/index.tsx 的 require.context 在 Vite 下不存在）。 */
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {shotProps, JobData} from '../lib/loader';
import {TitleCard} from '../shots/TitleCard';
import {QuoteCard} from '../shots/QuoteCard';
import {ChapterCard} from '../shots/ChapterCard';
import {CompareCard} from '../shots/CompareCard';
import {ARollScene} from '../shots/ARollScene';
import {ImageLedCover} from '../shots/ImageLedCover';
import {PipelineSteps} from '../shots/PipelineSteps';
import {CompareCardEnhanced} from '../shots/CompareCardEnhanced';
import {KPI_Tower} from '../shots/KPI_Tower';
import {MatrixHero} from '../shots/MatrixHero';
import {MapCard} from '../shots/MapCard';
import {StepsCard} from '../shots/StepsCard';
import {TransformCard} from '../shots/TransformCard';
import {ListGrid} from '../shots/ListGrid';
import {EndingCard} from '../shots/EndingCard';
import {ScreenshotCard} from '../shots/ScreenshotCard';
import {KineticTitle} from '../shots/KineticTitle';
import {BEAT_COLORS} from '../lib/theme';
import {KaraokeLine} from '../captions/KaraokeLine';
import {ColorTint, Grain, LightSweep, Particles, RealFootage, Vignette, StaticNoise, SnowFall, Embers} from '../overlays';
import {Presentation, type PresentationKind} from '../systems/Presentation';
import {CameraRig} from '../systems/CameraRig';
import {useIdle} from '../systems/CameraRig';
import {LayerHost} from '../layers/LayerHost';

const SHOT_COMPONENTS: Record<string, React.ComponentType<any>> = {
  'local:shots/KineticTitle': KineticTitle,
  'local:shots/TitleCard': TitleCard,
  'local:shots/QuoteCard': QuoteCard,
  'local:shots/ChapterCard': ChapterCard,
  'local:shots/CompareCard': CompareCard,
  'local:shots/ARollScene': ARollScene,
  'local:shots/ImageLedCover': ImageLedCover,
  'local:shots/PipelineSteps': PipelineSteps,
  'local:shots/CompareCardEnhanced': CompareCardEnhanced,
  'local:shots/KPI_Tower': KPI_Tower,
  'local:shots/MatrixHero': MatrixHero,
  'local:shots/MapCard': MapCard,
  'local:shots/StepsCard': StepsCard,
  'local:shots/TransformCard': TransformCard,
  'local:shots/ListGrid': ListGrid,
  'local:shots/EndingCard': EndingCard,
};

export type CardHostRenderer = (p: {slug: string; shot: any; tokens: any}) => React.ReactNode;

export function ShotRenderer({data, shotId, cardHost, layerCard}: {
  data: Omit<JobData, 'shotId'>;
  shotId: string;
  cardHost: CardHostRenderer;
  /** 图层卡槽注入：CLI=webpack 版 LayerCard；Studio=Vite 异步版。缺省则忽略 card 图层 */
  layerCard?: React.ComponentType<{slug: string; config: any; tokens: any}>;
}) {
  const {shot, timingSegs, tokens} = shotProps(data as JobData, shotId);
  // 字幕降级阶梯：组内取最差对齐置信度（timing.json 每段 align_confidence）
  const subConfidence = timingSegs.some((s: any) => s.align_confidence === 'low') ? 'low' as const
    : timingSegs.some((s: any) => s.align_confidence === 'medium') ? 'medium' as const : 'high' as const;
  const raw = shot.recipe_ref as string;
  // C-roll 分层：A/B 占画面主体（已由 roll 决定），overlay 是正交氛围层（动效/粒子/光影/色调）
  const shotIdxForOverlay = parseInt(String(shot.id).replace(/\D/g, ""), 10) || 0;
  const OVERLAY_MAP: Record<string, React.ReactNode> = {
    particles: <Particles seed={shotIdxForOverlay} color={`${tokens.anchor}`} opacity={0.4} />,
    light_sweep: <LightSweep color={tokens.anchor} opacity={0.16} />,
    grain: <Grain opacity={0.05} />,
    vignette: <Vignette strength={0.5} />,
    tint_warm: <ColorTint tone="warm" opacity={0.1} />,
    tint_cool: <ColorTint tone="cool" opacity={0.1} />,
    snow: <SnowFall opacity={0.6} />,
    embers: <Embers color={tokens.anchor} opacity={0.55} />,
  };
  const overlayNodes = (shot.overlay ?? [])
    .filter((o: any) => OVERLAY_MAP[typeof o === 'string' ? o : o?.type])
    .slice(0, 2)  // C-roll 层≤2：氛围不抢主体（talkcraft 同屏重音唯一）
    .map((o: any) => OVERLAY_MAP[typeof o === 'string' ? o : o?.type]);

  // B-roll 真实素材优先：manifest 有素材的镜头自动升级 RealFootage（MoneyPrinterTurbo 能力）
  const brollV = (data.assets as any)?.broll_videos?.[shot.id];
  const effectiveRaw = (shot.roll === 'B' && brollV) ? 'RealFootage' : raw;

  // 真实截图优先（s4_capture Playwright 实拍，资讯类证据镜头）：manifest.screenshots[shot.id]
  const shotImg = (data.assets as any)?.screenshots?.[shot.id];
  const layerHostNode = <LayerHost shot={shot} tokens={tokens} layerCard={layerCard} />;
  if (shotImg && effectiveRaw !== 'RealFootage') {
    return (
      <div style={{width: '100%', height: '100%', background: tokens.bg}}>
        <Presentation kind={(shot as any).presentation as PresentationKind | undefined}>
          <ScreenshotCard src={shotImg} tokens={tokens} />
        </Presentation>
        {layerHostNode}
        {overlayNodes}
        <StaticNoise seed={shotIdxForOverlay} />
        <KaraokeLine
          text={shot.vo}
          words={timingSegs.flatMap((s: any) => s.words ?? [])}
          offsetMs={shot.time.start_ms}
          confidence={subConfidence}
        />
      </div>
    );
  }
  if (effectiveRaw.startsWith('card:')) {
    // 移植卡路由：talkcraft 配方卡（内容注入 + 画中画宿主）+ 字幕 + 氛围叠层 + StaticNoise
    // 背景（消融后 v2）：深色基底 + 拍次色氛围光（位置/色随镜头轮换）+ 轻网点
    const slug = effectiveRaw.slice('card:'.length);
    const beat = BEAT_COLORS[shotIdxForOverlay % BEAT_COLORS.length];
    const gx = 28 + (shotIdxForOverlay * 17) % 44;
    const gy = 22 + (shotIdxForOverlay * 29) % 46;
    return (
      <div style={{width: '100%', height: '100%', background: '#0A0A0A', position: 'relative'}}>
        <div style={{position: 'absolute', inset: '-18%',
                     background: `radial-gradient(circle at ${gx}% ${gy}%, ${beat}2E, transparent 58%)`}} />
        <div style={{position: 'absolute', inset: 0, opacity: 0.07,
                     backgroundImage: `radial-gradient(circle, ${beat}CC 1.5px, transparent 1.5px)`,
                     backgroundSize: '18px 18px'}} />
        <div style={{position: 'absolute', left: 0, top: 0, bottom: 0, width: 5, background: beat, opacity: 0.85}} />
        <Presentation kind={(shot as any).presentation as PresentationKind | undefined}>
          {cardHost({slug, shot, tokens})}
        </Presentation>
        {layerHostNode}
        {overlayNodes}
        <StaticNoise seed={shotIdxForOverlay} />
        <KaraokeLine
          text={shot.vo}
          words={timingSegs.flatMap((s: any) => s.words ?? [])}
          offsetMs={shot.time.start_ms}
          confidence={subConfidence}
        />
      </div>
    );
  }
  if (effectiveRaw === 'RealFootage') {
    return (
      <div style={{width: '100%', height: '100%', background: tokens.bg}}>
        <Presentation kind={(shot as any).presentation as PresentationKind | undefined}>
          <RealFootage shot={shot} assets={data.assets} tokens={tokens} />
        </Presentation>
        {layerHostNode}
        {overlayNodes}
        <KaraokeLine
          text={shot.vo}
          words={timingSegs.flatMap((s: any) => s.words ?? [])}
          offsetMs={shot.time.start_ms}
          confidence={subConfidence}
        />
      </div>
    );
  }
  // 契约约定：storyboard.json 里 recipe_ref 用短名（如 ListGrid）；兼容旧产物的 local:shots/ 全键
  const recipeKey = (effectiveRaw.includes(':') ? effectiveRaw : `local:shots/${effectiveRaw}`) as keyof typeof SHOT_COMPONENTS;
  const ShotComp = SHOT_COMPONENTS[recipeKey];

  if (!ShotComp) {
    throw new Error(`未注册的 recipe_ref: ${shot.recipe_ref}`);
  }

  const ipImage = (data.assets.ip_scenes?.[shotId] ?? data.assets.ip_images?.['three_view']) || '../assets/ip-placeholder/ip.jpg';
  const idle = useIdle();

  // ★ 全局 Ken Burns 连续相机曲线：每镜必有运动，消除冻结段；确定性可复现。
  // ★ 匀速线性（不缓动）：缓动在首尾速度趋零会被 freezedetect 判冻结（实测踩坑）
  const camFrame = useCurrentFrame();
  const {durationInFrames: camDur} = useVideoConfig();
  const shotIdx = parseInt(shotId.replace(/\D/g, ''), 10) || 0;
  const dir = (shot as any).camera?.dir === 'in' ? 1 : (shot as any).camera?.dir === 'out' ? -1 : (shotIdx % 2 === 0 ? 1 : -1);
  const prog = Math.min(1, camFrame / Math.max(1, camDur));
  const camScale = dir === 1 ? 1 + 0.1 * prog : 1.1 - 0.1 * prog;
  const camTx = (2 * prog - 1) * 18 * (shotIdx % 3 === 0 ? -1 : 1);
  const camTy = (2 * prog - 1) * 10 * (shotIdx % 2 === 0 ? 1 : -1);

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        background: tokens.bg,
        color: tokens.text,
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      {/* 漂移微光：锚点色柔光随相机线性漂移，黑底文字镜头也保证可感知运动 */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            position: 'absolute',
            width: '170%',
            height: '170%',
            left: `${-35 + 60 * prog * (shotIdx % 2 === 0 ? 1 : -1)}%`,
            top: `${-35 + 30 * prog * (shotIdx % 3 === 0 ? -1 : 1)}%`,
            opacity: 1 - 0.35 * prog,
            background: `radial-gradient(circle at 50% 50%, ${tokens.anchor}18, transparent 55%)`,
          }}
        />
      </div>
      <CameraRig motion={null}>
        <div
          style={{
            width: '100%',
            height: '100%',
            transform: `scale(${idle.scale * camScale}) translate(${camTx}px, ${camTy}px)`,
          }}
        >
          <Presentation kind={(shot as any).presentation as PresentationKind | undefined}>
            <ShotComp
              shot={shot}
              timingSegs={timingSegs}
              tokens={tokens}
              ipImage={ipImage}
              assets={data.assets}
            />
          </Presentation>
        </div>
      </CameraRig>

      {layerHostNode}
      {timingSegs.length > 0 && (
        <KaraokeLine
          text={shot.vo}
          words={timingSegs.flatMap((s) => s.words)}
          offsetMs={shot.time.start_ms}
          confidence={subConfidence}
        />
      )}    </div>
  );
}
