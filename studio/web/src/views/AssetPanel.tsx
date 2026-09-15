/** 资产库面板（合并进编排编辑器的右侧页签）：
 * 类别 chips + 搜索 + 列表 + 选中项预览/编辑 + 一键应用到当前镜头（主画面或新图层）。
 * 与独立页同源逻辑，布局压缩为单列。 */
import React, {useEffect, useMemo, useRef, useState} from 'react';
import type {PlayerRef} from '@remotion/player';
import {Player} from '@remotion/player';
import {AbsoluteFill} from 'remotion';
import {useStore} from '../store';
import {api, type Shot} from '../api';
import {StudioShotPlayer} from '../preview/StudioPlayer';
import {StudioCardHost, CARD_REGISTRY} from '../preview/StudioCardHost';
import {deriveTexts} from '../../../../render-engine/src/cards/content';
import {TYPE, TIGHT} from '../../../../render-engine/src/lib/theme';
import {Row, TextListField, JsonField} from '../ui';

type Cat = 'card' | 'local' | 'overlay' | 'presentation' | 'sfx' | 'style' | 'method' | 'theme' | 'ip' | 'type';

// shotcraft 分类词表（中文）
// shotcraft 分类词表（中文 + 用途：什么时候用这一类）
export const CAT_ZH: Record<string, string> = {
  opening: '开业及品牌', typography: '排版', 'ui-entrance': '用户界面入口', camera: '相机',
  data: '数据', interaction: '相互作用', transition: '过渡',
  rhythm: '韵律', effects: '光线与强调', outro: '结尾',
};

// 每类的使用说明：这一类解决什么问题
export const CAT_GUIDE: Record<string, string> = {
  opening: '开场/章节/品牌亮相——视频开头和章节切换时用',
  typography: '文字排版强调——金句、关键词、大字标语时用',
  'ui-entrance': '产品/软件界面演示——展示 App、网页、终端操作时用',
  camera: '镜头运动——推拉摇移、页面捕获时用',
  data: '数字与图表——讲数据、增长、统计时用',
  interaction: '互动演示——光标操作、地图路线、画中画时用',
  transition: '转场——两个画面之间的切换特效',
  rhythm: '韵律节奏——步骤推进、章节进度、时间线时用',
  effects: '光线与强调——圈重点、高亮扫过、色块强调时用',
  outro: '结尾——关注引导、订阅提示、CTA 时用',
};

interface Inventory {
  motion: {cards: {count: number; injectable: number; raw: number}; shot_components: {count: number; items: string[]}; overlays: {count: number; items: string[]}; presentations: {count: number; items: string[]}};
  sfx: {count: number; items: Array<{name: string; file: string; family: string}>; families: string[]};
  themes: {count: number; items: string[]};
  image_styles: Array<{adapter: string; kind: string; count: number; items: Array<{num: string; name: string; desc: string; ref?: string}>}>;
  shotcraft: {count: number; categories: Record<string, number>; cards: Array<{slug: string; category: string; title: string; essence: string}>};
  ip_assets: {poses: string[]; pose_count: number; ref_count: number; placeholder: string[]};
  fonts: {note: string};
}

const CATS: {id: Cat; label: string}[] = [
  {id: 'card', label: '图卡'},
  {id: 'local', label: '组件'},
  {id: 'overlay', label: '叠层'},
  {id: 'presentation', label: '入场'},
  {id: 'sfx', label: '音效'},
  {id: 'style', label: '画风'},
  {id: 'method', label: '方法论'},
  {id: 'theme', label: '主题'},
  {id: 'ip', label: 'IP'},
  {id: 'type', label: '排印'},
];

export function AssetPanel() {
  const s = useStore();
  const meta = s.snap!.meta;
  const [inv, setInv] = useState<Inventory | null>(null);
  const [cat, setCat] = useState<Cat>('card');
  const [q, setQ] = useState('');
  const [picked, setPicked] = useState<{cat: Cat; id: string} | null>(null);
  const [draftContent, setDraftContent] = useState<{TEXT?: string[]; STEPS?: string[]; CONFIG?: any}>({});
  const [cardCat, setCardCat] = useState('');
  const n3 = useMemo(() => {
    const d = {narrative: 0, visual: 0};
    Object.values(meta.cards).forEach((c) => {
      if (c.tier !== 'injectable') return;
      if ((c as any).category3 === 'visual') d.visual++; else d.narrative++;
    });
    return d;
  }, [meta]);
  const playerRef = useRef<PlayerRef>(null);

  useEffect(() => {
    if (!inv) fetch('/api/inventory').then((r) => r.json()).then(setInv).catch(() => undefined);
  }, [inv]);

  const shots: Shot[] = s.sbDraft?.shots ?? [];
  const baseShot: Shot | undefined = shots.find((x) => x.id === s.selectedShotId) ?? shots[0];
  const tokens = s.projDraft?.style?.b_roll?.palette ?? {bg: '#F6F5EF', anchor: '#E4572E', text: '#1A1A1A'};
  const fps = s.projDraft?.canvas?.fps ?? 30;

  const countOf = (c: Cat): number => {
    if (!inv) return 0;
    switch (c) {
      case 'card': return inv.motion.cards.injectable;
      case 'local': return inv.motion.shot_components.count;
      case 'overlay': return inv.motion.overlays.count;
      case 'presentation': return inv.motion.presentations.count;
      case 'sfx': return inv.sfx.count;
      case 'style': return inv.image_styles.reduce((m, g) => m + g.count, 0);
      case 'method': return inv.shotcraft.count;
      case 'theme': return inv.themes.count;
      case 'ip': return inv.ip_assets.pose_count;
      case 'type': return Object.keys(TYPE).length;
    }
  };

  const items = useMemo(() => {
    if (cat === 'card') {
      return Object.values(meta.cards).filter((c) => c.tier === 'injectable')
        .filter((c) => !q || c.slug.includes(q) || c.desc.includes(q))
        .filter((c) => !cardCat || (c as any).category3 === cardCat)
        .map((c) => ({id: c.slug, name: c.slug,
        desc: (c as any).category3 === 'visual' ? '运镜特效 · ' + c.desc : c.desc,
        dur: c.durationInFrames}));
    }
    if (cat === 'local') {
      return meta.shot_components.filter((n) => !q || n.toLowerCase().includes(q.toLowerCase()))
        .map((n) => ({id: n, name: n, desc: '自研镜头组件', dur: null as number | null}));
    }
    if (cat === 'overlay') {
      return meta.overlays.filter((n) => !q || n.includes(q)).map((n) => ({id: n, name: n, desc: '氛围叠层', dur: null as number | null}));
    }
    if (cat === 'presentation') {
      return meta.presentations.filter((n) => !q || n.includes(q)).map((n) => ({id: n, name: n, desc: '入场动效', dur: null as number | null}));
    }
    if (cat === 'sfx' && inv) {
      return inv.sfx.items.filter((x) => !q || x.name.includes(q) || x.family.includes(q))
        .map((x) => ({id: x.name, name: x.name, desc: x.family, dur: null as number | null}));
    }
    if (cat === 'style' && inv) {
      const out: {id: string; name: string; desc: string; dur: null}[] = [];
      for (const g of inv.image_styles) {
        for (const it of g.items) {
          if (q && !(it.name.includes(q) || it.num.includes(q))) continue;
          out.push({id: `${g.adapter}:${it.num}`, name: `${it.num} ${it.name}`, desc: g.adapter, dur: null});
        }
      }
      return out;
    }
    if (cat === 'method' && inv) {
      return inv.shotcraft.cards.filter((c) => !q || c.slug.includes(q) || c.category.includes(q))
        .map((c) => ({id: c.slug, name: c.slug, desc: `[${c.category}]`, dur: null as number | null}));
    }
    if (cat === 'theme') {
      return meta.themes.filter((t) => !q || t.id.includes(q)).map((t) => ({id: t.id, name: t.id, desc: t.description ?? '', dur: null as number | null}));
    }
    if (cat === 'ip' && inv) {
      return [...inv.ip_assets.poses].filter((n) => !q || n.includes(q))
        .map((n) => ({id: n, name: n.replace('.jpg', ''), desc: '姿态', dur: null as number | null}));
    }
    return [];
  }, [cat, q, meta, inv]);

  const current = picked?.cat === cat ? picked : null;
  const entry = current && current.cat === 'card' ? CARD_REGISTRY[current.id] : undefined;

  const seekComplete = (id?: string) => {
    const dur = CARD_REGISTRY[id ?? '']?.durationInFrames ?? 90;
    playerRef.current?.seekTo(Math.floor(dur * 0.7));
  };
  const select = (id: string) => {
    setPicked({cat, id});
    setDraftContent({});
    window.setTimeout(() => seekComplete(id), 900);
    window.setTimeout(() => seekComplete(id), 2600);
  };

  // 卡内容：草稿优先，否则从口播派生
  const content = useMemo(() => {
    if (!entry) return {};
    const nT = entry.arities?.TEXT ?? 0;
    const nS = entry.arities?.STEPS ?? 0;
    return {
      ...(nT > 0 ? {TEXT: draftContent.TEXT ?? (baseShot ? deriveTexts({vo: baseShot.vo, intent: baseShot.intent}, nT) : entry.jsxTexts ?? [])} : {}),
      ...(nS > 0 ? {STEPS: draftContent.STEPS ?? (baseShot ? deriveTexts({vo: baseShot.vo, intent: baseShot.intent}, nS) : [])} : {}),
      ...(draftContent.CONFIG !== undefined ? {CONFIG: draftContent.CONFIG} : {}),
    };
  }, [entry, draftContent, baseShot]);

  const tryShot: Shot | null = useMemo(() => {
    if (!baseShot || !current) return null;
    if (current.cat === 'card') return {...baseShot, recipe_ref: `card:${current.id}`};
    if (current.cat === 'local') return {...baseShot, recipe_ref: current.id};
    if (current.cat === 'overlay') return {...baseShot, overlay: [current.id]};
    if (current.cat === 'presentation') return {...baseShot, presentation: current.id};
    return null;
  }, [baseShot, cat, current]);

  const data = tryShot ? {
    job: {id: s.jobId ?? '', root: ''},
    project: s.projDraft,
    timing: s.snap!.artifacts.timing,
    storyboard: {...(s.sbDraft ?? {}), shots: [tryShot]},
    assets: s.stagedAssets ?? s.snap!.artifacts.manifest ?? {ip_images: {}},
  } : null;

  const apply = () => {
    if (!baseShot || !current) return;
    s.updateShot(baseShot.id, (sh) => {
      const patch: Partial<Shot> = {};
      if (current.cat === 'card') {
        patch.recipe_ref = `card:${current.id}`;
        const cfg: Record<string, unknown> = {...(sh.config ?? {})};
        if (content.TEXT) cfg.TEXT = content.TEXT;
        if (content.STEPS) cfg.STEPS = content.STEPS;
        if (content.CONFIG !== undefined) cfg.CONFIG = content.CONFIG;
        patch.config = cfg as any;
      } else if (current.cat === 'local') patch.recipe_ref = current.id;
      else if (current.cat === 'overlay') patch.overlay = [current.id];
      else if (current.cat === 'presentation') patch.presentation = current.id;
      return patch;
    });
    s.notify('ok', `${current.id} → ${baseShot.id} 主画面（未保存）`);
  };

  const applyAsLayer = () => {
    if (!baseShot || !current) return;
    if (!['card', 'overlay', 'presentation'].includes(current.cat)) {
      s.notify('err', '该类别仅支持主画面应用');
      return;
    }
    const id = `L${(baseShot.layers?.length ?? 0) + 1}-${Math.random().toString(36).slice(2, 5)}`;
    const layer: any = current.cat === 'card'
      ? {id, kind: 'card', ref: current.id, label: current.id, enabled: true, presentation: 'rise_fade', x: 0.72, y: 0.62, config: {...content}}
      : current.cat === 'overlay'
        ? {id, kind: 'overlay', ref: current.id, label: current.id, enabled: true}
        : {id, kind: 'text', label: `${current.id}（入场预设占位）`, enabled: true, in_ms: 0, config: {text: baseShot.intent.slice(0, 10) || '图层'}};
    s.updateShot(baseShot.id, (x) => ({layers: [...(x.layers ?? []), layer]} as any));
    s.notify('ok', `${current.id} → ${baseShot.id} 新图层（画布拖动/时间轴调窗）`);
  };

  const applySfx = (name: string) => {
    if (!baseShot) return;
    s.updateShot(baseShot.id, (sh) => ({sfx: [...(sh.sfx ?? []), {t_ms: 0, name, gain: 1}]}));
    s.notify('ok', `${name} cue → ${baseShot.id}`);
  };

  const applyTheme = (t: any) => {
    if (!s.projDraft) return;
    s.setProjDraft((p) => ({
      ...p,
      style: {...p.style, theme: t.id, b_roll: {...p.style.b_roll, palette: {bg: t.bg, anchor: t.anchor, text: t.text}}},
    }));
    s.notify('ok', `预览已切 ${t.id}（去主题页保存）`);
  };

  const styleItem = useMemo(() => {
    if (cat !== 'style' || !current) return null;
    const [adapter, num] = current.id.split(':');
    const g = inv?.image_styles.find((x) => x.adapter === adapter);
    return {group: g, item: g?.items.find((x) => x.num === num)};
  }, [cat, current, inv]);
  const methodItem = useMemo(() => (cat === 'method' && current ? inv?.shotcraft.cards.find((c) => c.slug === current.id) : null), [cat, current, inv]);
  const themeItem = useMemo(() => (cat === 'theme' && current ? meta.themes.find((t) => t.id === current.id) : null), [cat, current, meta]);
  const sfxItem = useMemo(() => (cat === 'sfx' && current ? inv?.sfx.items.find((x) => x.name === current.id) : null), [cat, current, inv]);

  return (
    <div style={{display: 'flex', flexDirection: 'column', minHeight: 0, height: '100%'}}>
      {/* 类别 + 搜索 */}
      <div style={{padding: '8px 10px 6px', borderBottom: '1px solid var(--hairline)'}}>
        <div style={{display: 'flex', gap: 3, flexWrap: 'wrap', marginBottom: 6}}>
          {CATS.map((c) => (
            <button key={c.id} className="small" onClick={() => {setCat(c.id); setPicked(null);}}
                    title={`${countOf(c.id)} 项`}
                    style={cat === c.id ? {background: 'var(--accent-soft)', borderColor: 'var(--accent)', color: 'var(--accent)'} : undefined}>
              {c.label}<span className="faint" style={{marginLeft: 3}}>{countOf(c.id)}</span>
            </button>
          ))}
        </div>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={`搜索${CATS.find((c) => c.id === cat)?.label ?? ''}…`} style={{width: '100%'}} />
      </div>

      {/* 列表 */}
      <div style={{maxHeight: '26vh', overflowY: 'auto', flexShrink: 0, borderBottom: '1px solid var(--hairline)'}}>
        {items.map((it) => (
          <div key={it.id} className={`lib-item ${current?.id === it.id ? 'on' : ''}`} onClick={() => select(it.id)}>
            <div className="name">{it.name}{it.dur ? ` · ${(it.dur / 30).toFixed(1)}s` : ''}</div>
            <div className="desc">{it.desc}</div>
          </div>
        ))}
        {items.length === 0 && <div className="empty" style={{padding: 14}}>无匹配项</div>}
      </div>

      {/* 预览 + 应用 */}
      <div style={{flex: 1, minHeight: 0, overflowY: 'auto', padding: 10}}>
        {!current && <div className="empty" style={{padding: 16}}>选一项资产 → 在此预览/编辑 → 应用到 <b>{baseShot?.id ?? '—'}</b></div>}

        {current && (cat === 'card' || cat === 'local' || cat === 'overlay' || cat === 'presentation') && (
          <>
            <div style={{width: '100%', aspectRatio: cat === 'card' ? '16/9' : `${s.projDraft.canvas.width}/${s.projDraft.canvas.height}`,
                         maxHeight: 300, borderRadius: 8, overflow: 'hidden', boxShadow: '0 6px 30px rgba(0,0,0,0.4)',
                         margin: '0 auto', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#000'}}>
              {cat === 'card' ? (
                <Player
                  ref={playerRef as any}
                  component={React.memo(function CardProbe() {
                    return (
                      <AbsoluteFill style={{background: '#0A0A0A'}}>
                        <div style={{position: 'absolute', inset: '-18%', background: `radial-gradient(circle at 40% 30%, ${tokens.anchor}2E, transparent 58%)`}} />
                        <StudioCardHost slug={current.id} shot={{vo: baseShot?.vo ?? '', intent: baseShot?.intent ?? '', config: {...content, CONFIG: content.CONFIG ?? undefined}}} tokens={tokens} />
                      </AbsoluteFill>
                    );
                  })}
                  durationInFrames={entry?.durationInFrames ?? 90}
                  fps={30}
                  compositionWidth={1920}
                  compositionHeight={1080}
                  loop
                  style={{width: '100%', height: '100%'}}
                />
              ) : data && tryShot ? (
                <StudioShotPlayer ref={playerRef} data={data} shotId={tryShot.id} />
              ) : null}
            </div>
            <div style={{display: 'flex', gap: 6, marginTop: 6, justifyContent: 'center'}}>
              <button className="small" onClick={() => playerRef.current?.play()}>▶</button>
              <button className="small" onClick={() => playerRef.current?.pause()}>⏸</button>
              <span className="chip mono">{current.id}</span>
            </div>
            {entry && (
              <div style={{marginTop: 8}}>
                {(entry.arities?.TEXT ?? 0) > 0 && (
                  <Row label={`TEXT(${entry.arities.TEXT})`}>
                    <TextListField value={content.TEXT ?? []} max={entry.arities.TEXT}
                                   onChange={(v) => setDraftContent((d) => ({...d, TEXT: v}))} />
                  </Row>
                )}
                {(entry.arities?.STEPS ?? 0) > 0 && (
                  <Row label={`STEPS(${entry.arities.STEPS})`}>
                    <TextListField value={content.STEPS ?? []} max={entry.arities.STEPS}
                                   onChange={(v) => setDraftContent((d) => ({...d, STEPS: v}))} />
                  </Row>
                )}
              </div>
            )}
            <div style={{display: 'flex', gap: 6, marginTop: 10}}>
              <button className="primary" style={{flex: 1}} onClick={apply}>⤴ 主画面 {baseShot?.id}</button>
              {(cat === 'card' || cat === 'overlay') && (
                <button style={{flex: 1}} onClick={applyAsLayer}>⊕ 加为图层</button>
              )}
            </div>
            <div className="faint" style={{fontSize: 11, marginTop: 8, lineHeight: 1.5}}>
              {cat === 'card' ? `试穿用 ${baseShot?.id} 口播；应用会连同 TEXT 内容一起写入配方。图层模式可在画布拖动/时间轴调窗。` :
               cat === 'overlay' ? '主画面氛围层同屏 ≤2；图层模式不限且可设时间窗。' :
               cat === 'presentation' ? '入场动效作用于整个镜头主画面。' : '组件预览 = 当前镜头口播/素材换配方。'}
            </div>
          </>
        )}

        {current && cat === 'sfx' && (
          <div style={{textAlign: 'center', padding: '8px 0'}}>
            <div style={{fontWeight: 800, marginBottom: 4}}>{current.id}</div>
            <span className="chip acc">{sfxItem?.family}</span>
            <audio controls src={`/sfx/${sfxItem?.file ?? current.id + '.mp3'}`} style={{width: '100%', marginTop: 12}} />
            <button className="primary" style={{width: '100%', marginTop: 10}} onClick={() => applySfx(current.id)}>♪ 给 {baseShot?.id} 加 cue</button>
          </div>
        )}

        {cat === 'style' && styleItem && 'item' in styleItem && styleItem.item && (
          <div style={{textAlign: 'center'}}>
            {styleItem.item.ref && <img src={`/api/external-file?root=handraw&path=${styleItem.item.ref}`}
                 style={{maxWidth: '100%', maxHeight: 260, borderRadius: 8, border: '1px solid var(--hairline-strong)'}} />}
            <div style={{fontWeight: 800, marginTop: 8}}>{styleItem.item.num} · {styleItem.item.name}</div>
            <div className="muted" style={{fontSize: 12, marginTop: 4, lineHeight: 1.6}}>{styleItem.item.desc}</div>
            <div className="faint" style={{fontSize: 11, marginTop: 6}}>在「素材 → 生成图任务单 / AI 生图」时选择画风生效</div>
          </div>
        )}

        {cat === 'method' && methodItem && (
          <div>
            <span className="chip acc">{methodItem.category}</span>
            <div style={{fontSize: 15, fontWeight: 800, margin: '8px 0'}}>{methodItem.slug}</div>
            <div className="muted" style={{fontSize: 12, lineHeight: 1.7}}>{methodItem.essence}</div>
            <div className="faint" style={{fontSize: 11, marginTop: 8}}>移植 backlog：想把它做成卡，按 import_cards 通道移植</div>
          </div>
        )}

        {cat === 'theme' && themeItem && (
          <div>
            <div style={{height: 90, borderRadius: 10, background: themeItem.bg, color: themeItem.text,
                         display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, border: '1px solid var(--hairline-strong)'}}>
              <span style={{fontSize: 26, fontWeight: 900, ...TIGHT}}>Aa 样张</span>
              <span style={{background: themeItem.anchor, color: themeItem.bg, borderRadius: 6, padding: '4px 10px', fontWeight: 800, fontSize: 12}}>强调</span>
            </div>
            <div style={{textAlign: 'center', marginTop: 8, fontWeight: 700}}>{themeItem.id}</div>
            <button className="primary" style={{width: '100%', marginTop: 8}} onClick={() => applyTheme(themeItem)}>应用（预览即时生效）</button>
          </div>
        )}

        {cat === 'ip' && current && (
          <img src={`/api/project-file/ip/${current.id}`}
               style={{maxWidth: '100%', maxHeight: 300, borderRadius: 8, border: '1px solid var(--hairline-strong)', display: 'block', margin: '0 auto'}} />
        )}

        {cat === 'type' && (
          <div style={{background: tokens.bg, color: tokens.text, borderRadius: 10, padding: '14px 16px', border: '1px solid var(--hairline-strong)'}}>
            {Object.entries(TYPE).map(([k, v]) => (
              <div key={k} style={{marginBottom: 6, whiteSpace: 'nowrap', overflow: 'hidden'}}>
                <span style={{fontSize: Math.min(v as number, 72), fontWeight: (v as number) >= 96 ? 500 : (v as number) >= 64 ? 700 : 900,
                             letterSpacing: TIGHT.letterSpacing, fontFamily: (s.projDraft?.style?.b_roll?.font_stack as string[])?.join(',') ?? undefined}}>
                  {k === 'display' ? '十年之约' : `字阶 ${k}`}
                </span>
                <span className="faint" style={{fontSize: 10, marginLeft: 8}}>{v}px</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
