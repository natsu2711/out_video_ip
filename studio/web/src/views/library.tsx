/** 资产库（独立页）：两大职责
 * ① 盘点浏览：全项目资产实时扫描（总览 + 分类浏览，同编排右侧页签的数据源）
 * ② 蒸馏/新增：扫描外部项目候选资产 → 勾选吸收（存档 + 移植 backlog 登记），新增自有资产导入
 */
import React, {useEffect, useMemo, useState} from 'react';
import {useStore} from '../store';
import {AssetPanel} from './AssetPanel';

interface DistillSource {
  name: string;
  desc: string;
  root: string;
  exists: boolean;
  patterns: Array<{kind: string; glob: string; desc: string}>;
}
interface ScanItem {
  kind: string;
  kind_desc: string;
  path: string;
  size: number;
  mtime: number;
}
interface Backlog {
  items: Array<{source: string; path: string; kind: string; as: string; note: string; local: string; ts: number}>;
}

function human(n: number): string {
  if (n > 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n > 1e3) return `${(n / 1e3).toFixed(0)}K`;
  return String(n);
}

export function LibraryView() {
  const s = useStore();
  const [tab, setTab] = useState<'browse' | 'distill'>('browse');
  return (
    <div className="pane">
      <div style={{display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14}}>
        <h2 style={{margin: 0}}>资产库</h2>
        <div style={{display: 'flex', gap: 4}}>
          <button className={tab === 'browse' ? 'small' : 'small ghost'} style={tab === 'browse' ? {background: 'var(--accent-soft)', borderColor: 'var(--accent)', color: 'var(--accent)'} : undefined}
                  onClick={() => setTab('browse')}>浏览与试穿</button>
          <button className={tab === 'distill' ? 'small' : 'small ghost'} style={tab === 'distill' ? {background: 'var(--accent-soft)', borderColor: 'var(--accent)', color: 'var(--accent)'} : undefined}
                  onClick={() => setTab('distill')}>蒸馏外部项目 / 新增</button>
        </div>
        <div style={{flex: 1}} />
        <span className="muted" style={{fontSize: 12}}>应用资产请到「编排」右侧的资产库页签（随选随用）</span>
      </div>
      {tab === 'browse' ? (
        <div className="lib">
          <AssetPanel />
        </div>
      ) : (
        <DistillTab />
      )}
    </div>
  );
}

/** 蒸馏页：源清单 → 扫描候选 → 勾选吸收 → backlog */
function DistillTab() {
  const s = useStore();
  const [sources, setSources] = useState<DistillSource[]>([]);
  const [src, setSrc] = useState('');
  const [q, setQ] = useState('');
  const [scan, setScan] = useState<{available: boolean; count: number; items: ScanItem[]; note?: string} | null>(null);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [backlog, setBacklog] = useState<Backlog | null>(null);
  const [busy, setBusy] = useState(false);

  const loadBacklog = () => fetch('/api/distill/backlog').then((r) => r.json()).then(setBacklog).catch(() => undefined);

  useEffect(() => {
    fetch('/api/distill/sources').then((r) => r.json()).then((list: DistillSource[]) => {
      setSources(list);
      const first = list.find((x) => x.exists);
      if (first) setSrc(first.name);
    }).catch(() => undefined);
    loadBacklog();
  }, []);

  const doScan = () => {
    if (!src) return;
    setScan(null);
    fetch(`/api/distill/scan?source=${encodeURIComponent(src)}&q=${encodeURIComponent(q)}`)
      .then((r) => r.json()).then(setScan).catch((e) => s.notify('err', String(e)));
  };
  useEffect(doScan, [src]); // eslint-disable-line react-hooks/exhaustive-deps

  const absorb = async () => {
    if (checked.size === 0) return;
    setBusy(true);
    try {
      const kinds = new Map<string, string>();
      (scan?.items ?? []).forEach((it) => kinds.set(it.path, it.kind));
      const r = await fetch('/api/distill/absorb', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({source: src, paths: [...checked], as_: 'card_backlog'}),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail));
      s.notify('ok', `已吸收 ${d.imported} 项（backlog 登记）`);
      setChecked(new Set());
      loadBacklog();
    } catch (e: any) {
      s.notify('err', `吸收失败: ${e.message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid2" style={{alignItems: 'start'}}>
      <div className="card">
        <div className="muted" style={{fontSize: 11, marginBottom: 8}}>蒸馏源（白名单登记的外部项目）</div>
        <div style={{display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10}}>
          {sources.map((x) => (
            <button key={x.name} className="small" disabled={!x.exists} title={x.desc}
                    onClick={() => {setSrc(x.name); setChecked(new Set());}}
                    style={src === x.name ? {background: 'var(--accent-soft)', borderColor: 'var(--accent)', color: 'var(--accent)'} : undefined}>
              {x.name}{x.exists ? '' : '（不存在）'}
            </button>
          ))}
        </div>
        <div style={{display: 'flex', gap: 6, marginBottom: 10}}>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="按文件名/路径过滤…" style={{flex: 1}}
                 onKeyDown={(e) => e.key === 'Enter' && doScan()} />
          <button className="small" onClick={doScan}>扫描</button>
        </div>

        {scan && !scan.available && <div className="empty">{scan.note}</div>}
        {scan?.available && (
          <>
            <div style={{display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6}}>
              <span className="chip">{scan.count} 个候选</span>
              <button className="ghost small" onClick={() => setChecked(new Set(scan.items.map((i) => i.path)))}>全选</button>
              <button className="ghost small" onClick={() => setChecked(new Set())}>清空</button>
              <div style={{flex: 1}} />
              <button className="primary small" disabled={checked.size === 0 || busy} onClick={absorb}>
                {busy ? '吸收中…' : `⤓ 吸收选中 ${checked.size || ''}`}
              </button>
            </div>
            <div style={{maxHeight: 380, overflowY: 'auto', border: '1px solid var(--hairline)', borderRadius: 8}}>
              {scan.items.map((it) => (
                <label key={it.path} style={{display: 'flex', alignItems: 'center', gap: 8, padding: '5px 10px',
                                              borderBottom: '1px solid var(--hairline)', cursor: 'pointer', fontSize: 12}}>
                  <input type="checkbox" checked={checked.has(it.path)}
                         onChange={(e) => {
                           const next = new Set(checked);
                           if (e.target.checked) next.add(it.path);
                           else next.delete(it.path);
                           setChecked(next);
                         }} />
                  <span className="chip" style={{minWidth: 70, justifyContent: 'center'}}>{it.kind}</span>
                  <span style={{flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}} title={it.path}>{it.path}</span>
                  <span className="faint mono">{human(it.size)}B</span>
                </label>
              ))}
            </div>
            <div className="faint" style={{fontSize: 11, marginTop: 6}}>
              吸收 = 复制进 assets/distill/{src}/ 存档 + 登记 docs/distill-backlog.json（tsx 卡进入
              import_cards 移植素材区；方法论 md 进知识库 backlog）。全程文件操作，无 LLM。
            </div>
          </>
        )}
      </div>

      <div className="card">
        <div style={{display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8}}>
          <div className="muted" style={{fontSize: 11}}>蒸馏 backlog（{backlog?.items.length ?? 0}）</div>
          <div style={{flex: 1}} />
          <button className="ghost small" onClick={loadBacklog}>↻</button>
        </div>
        {(backlog?.items ?? []).length === 0 && <div className="faint" style={{fontSize: 12}}>还没有吸收记录。左侧扫描外部项目并勾选吸收。</div>}
        <div style={{maxHeight: 420, overflowY: 'auto'}}>
          {[...(backlog?.items ?? [])].reverse().map((it, i) => (
            <div key={i} style={{padding: '6px 8px', borderBottom: '1px solid var(--hairline)', fontSize: 12}}>
              <div style={{display: 'flex', gap: 6, alignItems: 'center'}}>
                <span className="chip">{it.source}</span>
                <span className="chip">{it.kind}</span>
                <span style={{flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}>{it.path}</span>
              </div>
              <div className="faint mono" style={{fontSize: 10, marginTop: 2}}>{it.local}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
