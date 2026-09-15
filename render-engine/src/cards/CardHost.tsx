import React, {useEffect} from 'react';
import {Freeze, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {cardExists, loadCardComponent, setCardContent, CARD_REGISTRY, type CardEntry} from './index';
import {buildCardContent} from './content';

/** 卡宿主：把 960×540 的横版卡适配进 1080×1920 竖屏画布。
 * 版式：卡居中成 16:9「画中画」区（上下留 tokens 背景与字幕空间），播完定格末帧（Freeze）。
 * 顺序保证：setCardContent 必须发生在卡模块首次 require 之前（模块求值时读注入）。 */
export function CardHost({slug, shot, tokens}: {slug: string; shot: any; tokens: any}) {
  const entry: CardEntry | undefined = CARD_REGISTRY[slug];
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const content = entry ? buildCardContent(entry, shot) : {};
  setCardContent(content);

  const Card = cardExists(slug) ? loadCardComponent(slug) : null;

  // 播完定格：卡自身时长之后冻结在末帧，避免时间轴越界产生的未定义行为
  const cardDur = entry?.durationInFrames ?? null;
  const freezeAt = cardDur ? Math.max(0, cardDur - 1) : null;
  const shouldFreeze = freezeAt !== null && frame >= freezeAt;

  if (!Card || !entry) {
    return (
      <div style={{width: '100%', height: '100%', display: 'flex', alignItems: 'center',
                   justifyContent: 'center', background: tokens.bg, color: `${tokens.text}88`, fontSize: 40}}>
        卡未移植: {slug}
      </div>
    );
  }

  // 960×540 卡 → 适配任意画幅（竖屏画中画 / 横屏近满幅），上移留字幕带
  const {width: cw, height: ch} = useVideoConfig();
  const scale = Math.min(cw / 960, ch / 540) * 0.9;
  const W = 960 * scale;
  const H = 540 * scale;
  const top = (ch - H) / 2 - ch * 0.04;

  // SidePanel：填 Host 移除后的右半区。config.side = {kind:'chart'|'bigword', ...}；
  // 缺省不渲染（留白也是排版）。chart = lieflat Glance 风迷你柱图（粗柱+数字，零依赖）。
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

  // shotcraft 系卡 1920×1080 全幅原生
  if (slug.startsWith('sc-')) {
    return (
      <div style={{width: '100%', height: '100%', background: tokens.bg, overflow: 'hidden'}}>
        <Card />
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
      {shouldFreeze ? (
        <Freeze frame={freezeAt!}>
          <Card />
        </Freeze>
      ) : (
        <Card />
      )}
      {sideEl}
    </div>
  );

  // sc- 卡 1920×1080 原生设计；主画面画幅同为 1920×1080，直接渲染
  return inner; // scWrapDone
}
