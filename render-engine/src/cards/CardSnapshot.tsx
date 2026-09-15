import {AbsoluteFill} from 'remotion';
import {cardExists, loadCardComponent, setCardContent, CARD_REGISTRY, type CardEntry} from './index';
import {designSizeOf} from './size';

/** 卡片快照渲染：固定 fixture 内容渲指定卡（视觉回归/单卡预览用，scripts/card_snapshot.py 驱动）。
 * 注入顺序与 CardHost 同约：setCardContent 必须发生在卡模块首次 require 之前。
 * props 泛化：除 TEXT/STEPS 外，registry.arities 声明的任意槽位（ROWS/ITEMS/...）均可经同名 prop 注入。 */
export const CardSnapshot: React.FC<{slug: string; [key: string]: unknown}> = ({slug, ...rest}) => {
  const entry: CardEntry | undefined = CARD_REGISTRY[slug];
  const inj: Record<string, unknown> = {};
  if (entry) {
    const defaults = (entry as any).slotDefaults ?? {};
    for (const [key, n] of Object.entries(entry.arities ?? {})) {
      if (typeof n !== 'number' || n <= 0) continue;
      const val = rest[key] as any[] | undefined;
      if (!val) continue;
      if (key === 'SLOTS') { inj[key] = val.slice(0, n); continue; }  // 对象槽：{text?,image?} 原样
      const shape = defaults[key] ?? [];
      inj[key] = shape.length > 0 && typeof shape[0] === 'object' && shape[0] !== null
        ? val.slice(0, n).map((t, i) => ({...(shape[i % shape.length] as object), text: t}))
        : val.slice(0, n);
    }
  }
  setCardContent(inj);
  const Card = cardExists(slug) ? loadCardComponent(slug) : null;
  if (!Card || !entry) {
    return (
      <AbsoluteFill style={{background: '#fff'}}>
        <div style={{padding: 40, color: '#900', fontSize: 28}}>{slug} 不存在或未移植</div>
      </AbsoluteFill>
    );
  }
  // 设计尺寸契约：内容按原稿渲染，缩放由本容器按 designSizeOf 统一计算（只缩一次）
  const {w: dw, h: dh} = designSizeOf(slug);
  const s = Math.min(1920 / dw, 1080 / dh);
  return (
    <AbsoluteFill style={{background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
      <div style={{width: dw, height: dh, transform: `scale(${s})`, transformOrigin: 'center center', flexShrink: 0}}>
        <Card />
      </div>
    </AbsoluteFill>
  );
};
