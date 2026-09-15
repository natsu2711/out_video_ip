/** 效果选择器：把全项目资产（图卡/组件/叠层/图表/生图/图库/上传/白板/实拍）
 * 挂到「主画面」或「新图层」上。素材类走 /apply-effect → 确定性脚本（无 LLM）。 */
import React, { useEffect, useMemo, useState } from 'react';
import { useStore } from '../store';
import { api } from '../api';
import { CARD_REGISTRY } from '../preview/StudioCardHost';
import { deriveTexts } from '../../../../render-engine/src/cards/content';
import type { Shot } from '../api';

interface Inventory {
  image_styles: Array<{ adapter: string; kind: string; count: number; items: Array<{ num: string; name: string; desc: string }> }>;
  prompt_packs: Array<{ name: string; desc: string }>;
}

const GROUPS = [
  { id: 'all', label: '全部资产卡', hint: '所有卡（可改文字/图片）' },
  { id: 'narrative', label: '叙事与展示', hint: '讲内容：数据/金句/步骤/开场' },
  { id: 'visual', label: '运镜与视觉特效', hint: '转场/运镜/强调动效' },
] as const;

type GroupId = typeof GROUPS[number]['id'];
type FontId = 'font';

export function EffectPicker({ open, onClose, shot, defaultLayer }: {
  open: boolean;
  onClose: () => void;
  shot?: Shot;
  defaultLayer?: boolean;
}) {
  const s = useStore();
  const meta = s.snap!.meta;
  const [group, setGroup] = useState<GroupId>('all');
  const [q, setQ] = useState('');
  const [asLayer, setAsLayer] = useState(defaultLayer ?? false);
  const [inv, setInv] = useState<Inventory | null>(null);
  const [genAdapter, setGenAdapter] = useState('handraw-style-216');
  const [genStyle, setGenStyle] = useState('');
  const [keywords, setKeywords] = useState('');
  const [dryRun, setDryRun] = useState(false);
  const [chartType, setChartType] = useState('workflow');
  const [chartTitle, setChartTitle] = useState('');
  const [steps, setSteps] = useState<Array<{ label: string; note: string }>>([
    { label: '', note: '' }, { label: '', note: '' }, { label: '', note: '' },
  ]);
  const [capUrl, setCapUrl] = useState('');
  const [capMode, setCapMode] = useState('screenshot');
  const [capSeconds, setCapSeconds] = useState(8);
  const [rawIr, setRawIr] = useState('{"type": "architecture", "ir": {}}');
  const [rawExcal, setRawExcal] = useState('[]');
  const [cardCat, setCardCat] = useState('');

  // 组件常驻挂载：每次打开时同步目标模式（useState 初始值只在首次生效）
  useEffect(() => {
    if (open) setAsLayer(defaultLayer ?? false);
  }, [open, defaultLayer]);

  const safeJson = (t: string): any => {
    try { return JSON.parse(t); } catch { return { type: 'architecture', ir: {} }; }
  };

  useEffect(() => {
    if (open && !inv) {
      fetch('/api/inventory').then((r) => r.json()).then(setInv).catch(() => undefined);
    }
  }, [open, inv]);

  const apply = (payload: Record<string, unknown>, label: string) => {
    s.startRun(label, async () => {
      const r = await api.applyEffect(s.jobId!, payload as any);
      if (!r.run_id) return { run_id: '' };
      return { run_id: r.run_id };
    }, () => {
      s.reloadStaged();
      s.refreshSummary();
    });
    onClose();
  };

  const addLayer = (layer: any) => {
    if (!shot) return;
    const id = `L${(shot.layers?.length ?? 0) + 1}-${Math.random().toString(36).slice(2, 5)}`;
    s.updateShot(shot.id, (x) => ({ layers: [...(x.layers ?? []), { id, enabled: true, ...layer }] } as any));
    s.notify('ok', '已加图层（时间窗/位置在右侧图层区调）');
    onClose();
  };

  const setRecipe = (patch: Partial<Shot> | ((x: Shot) => Partial<Shot>), msg: string) => {
    if (!shot) return;
    s.updateShot(shot.id, patch as any);
    s.notify('ok', msg);
    onClose();
  };

  const cards = useMemo(() => Object.values(meta.cards)
    .filter((c) => c.tier === 'injectable' || c.slug.startsWith('sc-'))
    .filter((c) => !q || c.slug.includes(q) || c.desc.includes(q))
    .filter((c) => !cardCat || (c as any).category3 === cardCat)
    .filter((c) => group === 'all' ? true : (c as any).category3 === group), [meta, q, cardCat, group]);

  if (!open) return null;

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 100, background: 'rgba(0,0,0,0.55)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
         onClick={onClose}>
      <div style={{ width: 720, maxHeight: '86vh', overflow: 'hidden', background: 'var(--bg-panel)', border: '1px solid var(--hairline-strong)', borderRadius: 14, display: 'flex', flexDirection: 'column' }}
           onClick={(e) => e.stopPropagation()}>
        <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--hairline)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <b>换效果 · {shot?.id}</b>
          <span className="muted" style={{ fontSize: 12 }}>目标：</span>
          <button className="small" onClick={() => setAsLayer(false)}
                  style={!asLayer ? { background: 'var(--accent-soft)', borderColor: 'var(--accent)', color: 'var(--accent)' } : undefined}>主画面</button>
          <button className="small" onClick={() => setAsLayer(true)}
                  style={asLayer ? { background: 'var(--accent-soft)', borderColor: 'var(--accent)', color: 'var(--accent)' } : undefined}>新图层（可叠加）</button>
          <div style={{ flex: 1 }} />
          <button className="ghost small" onClick={onClose}>✕</button>
        </div>

        <div style={{ display: 'flex', gap: 6, padding: '10px 16px 0', flexWrap: 'wrap' }}>
          {GROUPS.map((g) => (
            <button key={g.id} className="small" title={g.hint} onClick={() => setGroup(g.id)}
                    style={group === g.id ? { background: 'var(--accent-soft)', borderColor: 'var(--accent)', color: 'var(--accent)' } : undefined}>
              {g.label}
            </button>
          ))}
        </div>

        <div style={{ padding: 16, overflow: 'auto' }}>
          {(group === 'all' || group === 'narrative' || group === 'visual') && (
            <>
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="搜索卡…" style={{ width: '100%', marginBottom: 8 }} />

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, maxHeight: 380, overflow: 'auto' }}>
                {cards.map((c) => (
                  <div key={c.slug} className="lib-item" style={{ borderRadius: 8, border: '1px solid var(--hairline)' }}
                       onClick={() => {
                         const nT = c.arities?.TEXT ?? 0;
                         const cfg: any = { ...(shot?.config ?? {}) };
                         if (nT > 0 && shot) cfg.TEXT = deriveTexts({ vo: shot.vo, intent: shot.intent }, nT);
                         if (asLayer) {
                           addLayer({ kind: 'card', ref: c.slug, label: c.slug, presentation: 'rise_fade', x: 0.72, y: 0.35, config: cfg });
                         } else {
                           setRecipe({ recipe_ref: `card:${c.slug}`, config: cfg }, `已换配方 card:${c.slug}`);
                         }
                       }}>
                    <div className="name">{c.slug}{c.durationInFrames ? ` · ${(c.durationInFrames / 30).toFixed(1)}s` : ''}{c.tier !== 'injectable' ? ' · raw' : ''}</div>
                    <div className="desc">{c.desc.slice(0, 44)}</div>
                  </div>
                ))}
              </div>
            </>
          )}



          <div style={{marginTop: 10, borderTop: '1px solid var(--hairline)', paddingTop: 8}}>
            <div className="muted" style={{fontSize: 11, marginBottom: 6}}>氛围叠层（叠在卡上面，最多 2 层）：</div>
            <div style={{display: 'flex', gap: 6, flexWrap: 'wrap'}}>
              {meta.overlays.map((n) => (
                <button key={n} className="small" onClick={() => {
                  if (asLayer) addLayer({kind: 'overlay', ref: n, label: n});
                  else setRecipe((x) => ({overlay: [...(x.overlay ?? []), n].slice(-2)}), `已加氛围层 ${n}`);
                }}>{n}</button>
              ))}
            </div>
          </div>













        </div>
      </div>
    </div>
  );
}
