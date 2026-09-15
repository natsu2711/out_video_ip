/** Studio 版卡宿主：与 render-engine/src/cards/CardHost.tsx 同构，但卡组件经 Vite 动态加载。
 * （CardHost 依赖 webpack require.context，Vite 下不可用；这里复刻其画中画布局/定格/侧栏逻辑。） */
import React, {useEffect, useMemo, useState} from 'react';
import {Freeze, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import registryJson from '../../../../render-engine/src/cards/registry.json';
import {buildCardContent} from '../../../../render-engine/src/cards/content';
import type {CardEntry} from '../../../../render-engine/src/cards/index';
import {loadCardEvaluating} from './cardLoader';

export const CARD_REGISTRY = registryJson as unknown as Record<string, CardEntry>;

export function StudioCardHost({slug, shot, tokens}: {slug: string; shot: any; tokens: any}) {
  const entry: CardEntry | undefined = CARD_REGISTRY[slug];
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const content = useMemo(
    () => (entry ? buildCardContent(entry, shot) : {}),
    [entry, shot],
  );
  const contentKey = JSON.stringify(content);
  const [Card, setCard] = useState<React.ComponentType<any> | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setErr(null);
    if (!entry) {
      setCard(null);
      return;
    }
    loadCardEvaluating(slug, content)
      .then((m) => {
        if (alive) setCard(() => m);
      })
      .catch((e) => {
        if (alive) setErr(String(e?.message ?? e));
      });
    return () => {
      alive = false;
    };
  }, [slug, contentKey]);

  // 播完定格：卡自身时长之后冻结在末帧，避免时间轴越界产生的未定义行为
  const cardDur = entry?.durationInFrames ?? null;
  const freezeAt = cardDur ? Math.max(0, cardDur - 1) : null;
  const shouldFreeze = freezeAt !== null && frame >= freezeAt;

  const {width: cw, height: ch} = useVideoConfig();
  const scale = Math.min(cw / 960, ch / 540) * 0.9;
  const W = 960 * scale;
  const H = 540 * scale;
  const top = (ch - H) / 2 - ch * 0.04;

  // SidePanel：config.side = {kind:'chart'|'bigword', ...}
  const side = (shot as any).config?.side;
  const sideEl = (() => {
    if (!side) return null;
    const f = useCurrentFrame();
    const p = interpolate(f, [10, 28], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
    const wrap: React.CSSProperties = {
      position: 'absolute', right: 36, top: '12%', bottom: '12%', width: '42%',
      display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 14,
      opacity: p, transform: `translateX(${(1 - p) * 40}px)`,
    };
    if (side.kind === 'bigword') {
      return (
        <div style={{...wrap, alignItems: 'flex-start'}}>
          <div style={{fontSize: 96, fontWeight: 900, color: '#1A1A1A', lineHeight: 1}}>{side.word}</div>
          {side.note && <div style={{fontSize: 26, fontWeight: 700, color: side.color ?? '#666'}}>{side.note}</div>}
        </div>
      );
    }
    if (side.kind === 'chart' && Array.isArray(side.data)) {
      const max = Math.max(...side.data.map((d: any) => d.value));
      return (
        <div style={{...wrap}}>
          {side.title && <div style={{fontSize: 22, fontWeight: 700, color: '#555', letterSpacing: 2}}>{side.title}</div>}
          {side.data.map((d: any, i: number) => {
            const barP = interpolate(f, [14 + i * 5, 30 + i * 5], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
            return (
              <div key={i} style={{display: 'flex', alignItems: 'center', gap: 10}}>
                <div style={{width: 52, fontSize: 17, color: '#8a8a8a', textAlign: 'right'}}>{d.label}</div>
                <div style={{flex: 1, height: 26, background: '#EFEFEA', borderRadius: 4, overflow: 'hidden'}}>
                  <div style={{width: `${(d.value / max) * 100 * barP}%`, height: '100%',
                               background: side.color ?? '#1A1A1A', borderRadius: 4}} />
                </div>
                <div style={{width: 64, fontSize: 20, fontWeight: 800, color: '#1A1A1A', fontVariantNumeric: 'tabular-nums'}}>{d.value}</div>
              </div>
            );
          })}
        </div>
      );
    }
    return null;
  })();

  if (err) {
    return (
      <div style={{width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                   background: tokens.bg, color: '#f66', fontSize: 28, flexDirection: 'column', gap: 12}}>
        <div>卡加载失败: {slug}</div>
        <div style={{fontSize: 16, color: '#a66', maxWidth: '80%'}}>{err}</div>
      </div>
    );
  }

  // shotcraft 系卡按 1920×1080 全幅设计 → 全幅原生渲染，不进画中画盒
  if (slug.startsWith('sc-')) {
    return (
      <div style={{width: '100%', height: '100%', background: tokens.bg, overflow: 'hidden'}}>
        {!Card ? (
          <div style={{width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                       color: '#999', fontSize: 26}}><span className="spin" /></div>
        ) : shouldFreeze ? (
          <Freeze frame={freezeAt!}>
            <Card />
          </Freeze>
        ) : (
          <Card />
        )}
      </div>
    );
  }

  const inner = (
    <div
      style={{
        position: 'absolute',
        left: 0,
        top,
        width: W,
        height: H,
        overflow: 'hidden',
        borderRadius: 24,
        boxShadow: '0 30px 90px rgba(0,0,0,0.55)',
        background: '#fff',
      }}
    >
      {!Card ? (
        <div style={{width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                     color: '#999', fontSize: 26}}><span className="spin" /></div>
      ) : shouldFreeze ? (
        <Freeze frame={freezeAt!}>
          <Card />
        </Freeze>
      ) : (
        <Card />
      )}
      {sideEl}
    </div>
  );
  return inner;
}
