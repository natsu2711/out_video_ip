/** C-roll 叠层系统：与主体（A/B-roll）正交可组合的氛围层。
 * 确定性：全部用索引哈希，零 Math.random（talkcraft 铁律）。 */
import {AbsoluteFill, OffthreadVideo, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Particles as BitsParticles, Spawner, Behavior} from 'remotion-bits'; // remotion-bits 吸收（物理粒子）

/** 索引→伪随机（确定性） */
export function hash01(i: number): number {
  const x = Math.sin(i * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
}

/** 漂移粒子层：细小光点缓慢上浮（数量/颜色可控，默认稀薄不抢主体） */
export function Particles({count = 14, color = "#FFD9A0", opacity = 0.5, seed = 1, size = 5}: {
  count?: number; color?: string; opacity?: number; seed?: number; size?: number;
}) {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const dots = Array.from({length: count}, (_, i) => {
    const h1 = hash01(i * 3 + seed * 17);
    const h2 = hash01(i * 5 + seed * 23);
    const h3 = hash01(i * 7 + seed * 31);
    const x = h1 * 100;
    const y = ((h2 * 100 - t * (3 + h3 * 4)) % 110 + 110) % 110 - 5; // 循环上浮
    const tw = 0.4 + 0.6 * Math.abs(Math.sin(t * (0.8 + h3) + i));   // 闪烁
    return {x, y, o: opacity * tw, s: size * (0.5 + h1 * 0.8)};
  });
  return (
    <div style={{position: 'absolute', inset: 0, overflow: 'hidden', pointerEvents: 'none'}}>
      {dots.map((d, i) => (
        <div key={i} style={{
          position: 'absolute',
          left: `${d.x}%`, top: `${d.y}%`,
          width: d.s, height: d.s, borderRadius: '50%',
          background: color,
          opacity: d.o,
          filter: `blur(${d.s > 4 ? 1 : 0}px)`,
        }} />
      ))}
    </div>
  );
}

/** 雪落层（remotion-bits 物理粒子）：慢速下落，冬季/记忆/时间流逝语境。
 * ponytail: 参数保守——失败模式只是"稀疏小白点"，不会毁画面 */
export function SnowFall({color = "#FFFFFF", opacity = 0.65}: {color?: string; opacity?: number}) {
  return (
    <div style={{position: 'absolute', inset: 0, overflow: 'hidden', pointerEvents: 'none', opacity}}>
      <BitsParticles startFrame={120}>
        <Spawner rate={0.12} burst={14} max={36} position={{x: 0.5, y: -0.02}}
                 area={{width: 1.05, height: 0.02}} velocity={{x: 0, y: 0.6, varianceX: 0.15, varianceY: 0.25}}
                 lifespan={260} lifespanVariance={60}>
          <div style={{width: 5, height: 5, borderRadius: '50%', background: color,
                       boxShadow: `0 0 6px ${color}88`}} />
        </Spawner>
        <Behavior wiggle={{magnitude: 0.4, frequency: 0.35}} opacity={{frames: [0, 200, 260], values: [0, 0.9, 0]}} />
      </BitsParticles>
    </div>
  );
}

/** 余烬上浮层（remotion-bits 物理粒子）：暖点上升，燃尽/努力/余温语境 */
export function Embers({color = "#FFB36B", opacity = 0.6}: {color?: string; opacity?: number}) {
  return (
    <div style={{position: 'absolute', inset: 0, overflow: 'hidden', pointerEvents: 'none', opacity}}>
      <BitsParticles startFrame={120}>
        <Spawner rate={0.1} burst={12} max={30} position={{x: 0.5, y: 1.02}}
                 area={{width: 1.0, height: 0.02}} velocity={{x: 0, y: -0.5, varianceX: 0.2, varianceY: 0.2}}
                 lifespan={280} lifespanVariance={70}>
          <div style={{width: 4, height: 4, borderRadius: '50%', background: color,
                       boxShadow: `0 0 8px ${color}`}} />
        </Spawner>
        <Behavior drag={0.02} wiggle={{magnitude: 0.3, frequency: 0.5}} opacity={{frames: [0, 60, 280], values: [0, 1, 0]}} />
      </BitsParticles>
    </div>
  );
}

/** 扫光层：斜向光带匀速扫过（talkcraft「一个节拍一个重音」——每镜至多一次） */
export function LightSweep({color = "#FFFFFF", opacity = 0.14, duration = 3.2, delay = 1.2}: {
  color?: string; opacity?: number; duration?: number; delay?: number;
}) {
  const frame = useCurrentFrame();
  const {fps, width} = useVideoConfig();
  const t = frame / fps;
  const p = Math.min(1, Math.max(0, (t - delay) / duration));
  if (p <= 0 || p >= 1) return null;
  const x = -width * 0.6 + (width * 2.2) * p;
  return (
    <div style={{
      position: 'absolute', inset: 0, overflow: 'hidden', pointerEvents: 'none',
    }}>
      <div style={{
        position: 'absolute', left: x, top: -200, width: width * 0.35, height: '160%',
        background: `linear-gradient(105deg, transparent 0%, ${color} 45%, ${color} 55%, transparent 100%)`,
        opacity: opacity * Math.sin(p * Math.PI),
        transform: 'rotate(8deg)',
        filter: 'blur(30px)',
      }} />
    </div>
  );
}

/** 胶片颗粒层：SVG feTurbulence 噪声 + 逐帧相位（细颗粒质感） */
export function Grain({opacity = 0.06}: {opacity?: number}) {
  const frame = useCurrentFrame();
  const seed = 1 + (frame % 8); // 8 帧循环噪声相位
  return (
    <svg style={{position: 'absolute', inset: 0, width: '100%', height: '100%', opacity, pointerEvents: 'none', mixBlendMode: 'overlay'}}>
      <filter id="grainF">
        <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed={seed} />
        <feColorMatrix type="saturate" values="0" />
      </filter>
      <rect width="100%" height="100%" filter="url(#grainF)" />
    </svg>
  );
}

/** 暗角层：四角轻压暗（聚焦中心，Apple 范式） */
export function Vignette({strength = 0.5}: {strength?: number}) {
  return (
    <div style={{
      position: 'absolute', inset: 0, pointerEvents: 'none',
      background: `radial-gradient(ellipse 72% 62% at 50% 46%, transparent 55%, rgba(0,0,0,${0.55 * strength}) 100%)`,
    }} />
  );
}

/** 色调层：全画面轻染色（soft-light，暖/冷按幕切换） */
export function ColorTint({tone = "warm", opacity = 0.1}: {tone?: "warm" | "cool" | "neutral"; opacity?: number}) {
  const colors = {warm: "#FF9A3C", cool: "#3C8AFF", neutral: "#FFFFFF"};
  return (
    <div style={{
      position: 'absolute', inset: 0, pointerEvents: 'none',
      background: colors[tone] ?? colors.neutral,
      mixBlendMode: 'soft-light', opacity,
    }} />
  );
}


/** RealFootage：B-roll 真实素材占满画面（MoneyPrinterTurbo 能力吸收的渲染端）。
 * 素材由 S4C 搜索下载并登记进 manifest.broll_videos；缺失时静默黑底（闸会拦）。 */
export function RealFootage({shot, assets, tokens}: {shot: any; assets: any; tokens: any}) {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const entry = assets?.broll_videos?.[shot.id];
  if (!entry) {
    return <div style={{width: '100%', height: '100%', background: tokens.bg}} />;
  }
  // 素材慢推（Ken Burns 覆盖真实素材，避免二阶静止）
  const prog = Math.min(1, frame / Math.max(1, durationInFrames));
  const scale = 1 + 0.09 * prog;
  return (
    <AbsoluteFill style={{background: '#000', overflow: 'hidden'}}>
      <OffthreadVideo
        src={staticFile(String(entry.path).replace(/^public\//, ''))}
        style={{width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${scale})`}}
      />
    </AbsoluteFill>
  );
}

/** StaticNoise：防冻结保底层（卡播完定格 / 长驻静态画面的 companions）。
 * 每帧换噪点 tile + 位移 → 帧间必有差异，freezedetect(n=0.003) 永不触发。
 * ★ 不用 transform 也不用 feTurbulence 每帧重算：canvas tile 预生成 8 张轮换，代价近零。
 * 视觉 = 极轻胶片颗粒（opacity 0.04），不抢主体。 */
const NOISE_TILES: string[] = (() => {
  const tiles: string[] = [];
  if (typeof document === 'undefined') return tiles; // Node/SSR 安全
  for (let k = 0; k < 8; k++) {
    const c = document.createElement('canvas');
    c.width = 128;
    c.height = 128;
    const ctx = c.getContext('2d')!;
    const img = ctx.createImageData(128, 128);
    let s = 12345 + k * 6789;
    for (let i = 0; i < img.data.length; i += 4) {
      s = (s * 1103515245 + 12345) & 0x7fffffff; // LCG，确定性
      const v = (s >>> 16) & 0xff;
      img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
      img.data[i + 3] = 255;
    }
    ctx.putImageData(img, 0, 0);
    tiles.push(c.toDataURL());
  }
  return tiles;
})();

export function StaticNoise({opacity = 0.04, seed = 0}: {opacity?: number; seed?: number}) {
  const frame = useCurrentFrame();
  if (!NOISE_TILES.length) return null;
  const tile = NOISE_TILES[(frame + seed) % NOISE_TILES.length];
  const jx = ((frame * 37 + seed * 91) % 64) - 32;
  const jy = ((frame * 53 + seed * 17) % 64) - 32;
  return (
    <div
      style={{
        position: 'absolute',
        inset: -64,
        pointerEvents: 'none',
        opacity,
        backgroundImage: `url(${tile})`,
        backgroundRepeat: 'repeat',
        backgroundPosition: `${jx}px ${jy}px`,
        mixBlendMode: 'normal',
      }}
    />
  );
}
