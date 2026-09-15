// [outvideo] card-sc-page-waterfall-wall —— 移植自 video-shotcraft/demos/ui-entrance/page-waterfall-wall
// 原动效保留；内容接线：raw 档（可在编排手动用，后续逐张接 __INJ__）
import React from 'react';
import {
  AbsoluteFill,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import { VerticalTicker, TickerColumn } from './VerticalTicker';

const BG = '#101014';

const __INJ__: any = (globalThis as any).__OUTVIDEO_CARD__ ?? {};
const IMG1 = (__INJ__.CONFIG as any)?.image_1 ? String((__INJ__.CONFIG as any).image_1) : null;
const IMG2 = (__INJ__.CONFIG as any)?.image_2 ? String((__INJ__.CONFIG as any).image_2) : null;
const IMG3 = (__INJ__.CONFIG as any)?.image_3 ? String((__INJ__.CONFIG as any).image_3) : null;

const shot = (file: string, override?: string | null) => (
  <div
    style={{
      borderRadius: 16,
      overflow: 'hidden',
      boxShadow: '0 12px 40px rgba(0,0,0,0.45)',
      background: '#fff',
    }}
  >
    <Img src={staticFile(String(override ?? `textures/${file}`))} style={{ width: '100%', display: 'block' }} />
  </div>
);

// 3 列差速反向（配方卡参数：loop 12/9/14s，中列反向）
export const buildColumns = (loops: [number, number, number]): TickerColumn[] => [
  {
    items: [shot('card1.png', IMG1), 'card2.png', 'card3.png', 'card10.png'].map((f) =>
      typeof f === 'string' ? shot(f) : f,
    ),
    durationInSeconds: loops[0],
    direction: -1,
  },
  {
    items: [shot('card4.png', IMG2), 'card5.png', 'card6.png', 'projects-empty.png'].map((f) =>
      typeof f === 'string' ? shot(f) : f,
    ),
    durationInSeconds: loops[1],
    direction: 1,
  },
  {
    items: [shot('card7.png', IMG3), 'card8.png', 'card9.png', 'float-search.png'].map((f) =>
      typeof f === 'string' ? shot(f) : f,
    ),
    durationInSeconds: loops[2],
    direction: -1,
  },
];

export const PageWaterfallWall: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  // 镜头缓推寄生在外层，墙自身循环、镜头单向
  const push = interpolate(frame, [0, durationInFrames], [1, 1.06]);

  return (
    <AbsoluteFill style={{ backgroundColor: BG }}>
      <AbsoluteFill style={{ transform: `scale(${push})` }}>
        <VerticalTicker
          columns={buildColumns([12, 9, 14])}
          backgroundColor={BG}
          columnWidth={560}
          gap={30}
        />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// 接缝自检用：短 loop（3s=90f）、无镜头推，f0 与 f90 应逐像素一致
export const SeamTest: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: BG }}>
    <VerticalTicker
      columns={buildColumns([3, 3, 3])}
      backgroundColor={BG}
      columnWidth={560}
      gap={30}
    />
  </AbsoluteFill>
);


export default PageWaterfallWall;
