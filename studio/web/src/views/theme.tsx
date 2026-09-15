/** 主题视图：46 套主题一键应用 + 调色板手动微调（bg/anchor/text 即渲染端 tokens） */
import React, {useState} from 'react';
import {useStore} from '../store';
import {api, type ThemeDef} from '../api';

export function ThemeView() {
  const s = useStore();
  const themes: ThemeDef[] = s.snap!.meta.themes;
  const proj = s.projDraft;
  const [q, setQ] = useState('');
  const palette = proj?.style?.b_roll?.palette ?? {bg: '#F6F5EF', anchor: '#E4572E', text: '#1A1A1A'};
  const currentTheme = (proj?.style?.theme as string) ?? '';

  const filtered = themes.filter((t) => !q || t.id.includes(q) || (t.description ?? '').includes(q) || (t.name ?? '').includes(q));

  const applyTheme = async (t: ThemeDef) => {
    if (!proj) return;
    s.setProjDraft((p) => ({
      ...p,
      style: {...p.style, theme: t.id, b_roll: {...p.style.b_roll, palette: {bg: t.bg, anchor: t.anchor, text: t.text}}},
    }));
    s.notify('info', `已切换预览到 ${t.id}，点「保存并应用」落盘`);
  };

  const saveAndApply = async () => {
    await s.saveProj();
    s.startRun('apply_theme', () => api.tool(s.jobId!, 'apply_theme'));
  };

  return (
    <div className="pane">
      <h2>主题与调色板 <span className="chip mono" style={{marginLeft: 8}}>{themes.length} 套</span></h2>
      <div className="sub">
        tokens = project.style.b_roll.palette {'{bg, anchor, text}'}，渲染端全局消费。
        切换主题立即反映在「编排」画布预览；「保存并应用」会跑 apply_theme.py 重写 project.json。
      </div>

      <div className="card">
        <div style={{display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap'}}>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="搜索主题…" style={{width: 220}} />
          {(['bg', 'anchor', 'text'] as const).map((k) => (
            <label key={k} style={{display: 'flex', alignItems: 'center', gap: 5, fontSize: 12}}>
              <span className="muted">{k}</span>
              <input type="color" value={ensureHex(palette[k])}
                     onChange={(e) => s.setProjDraft((p) => ({
                       ...p,
                       style: {...p.style, b_roll: {...p.style.b_roll, palette: {...p.style.b_roll.palette, [k]: e.target.value}}},
                     }))} style={{width: 36, height: 26, padding: 1}} />
              <span className="mono faint">{palette[k]}</span>
            </label>
          ))}
          <div style={{flex: 1}} />
          <span className="chip">当前: {currentTheme || '（自定义）'}</span>
          <button className="primary small" disabled={!s.dirtyProj} onClick={saveAndApply}>保存并应用</button>
        </div>
        <div style={{marginTop: 10, height: 54, borderRadius: 10, background: palette.bg, color: palette.text,
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12, overflow: 'hidden'}}>
          <span style={{fontSize: 22, fontWeight: 900, letterSpacing: '-0.02em'}}>标题样张 十年之约</span>
          <span style={{background: palette.anchor, color: palette.bg, borderRadius: 6, padding: '3px 10px', fontWeight: 800, fontSize: 13}}>强调色</span>
        </div>
      </div>

      <div className="theme-grid">
        {filtered.map((t) => (
          <div key={t.id} className={`theme-card ${t.id === currentTheme ? 'on' : ''}`} onClick={() => applyTheme(t)}
               title={t.description}>
            <div className="swatch" style={{background: t.bg}}>
              <div className="a" style={{background: t.anchor}} />
              <div style={{fontSize: 26, fontWeight: 900, color: t.text, letterSpacing: '-0.03em'}}>Aa 字</div>
              <div className="a" style={{background: t.text, width: 20, height: 20, borderRadius: 5}} />
            </div>
            <div className="info">
              <div className="nm">{t.id}{t.id === currentTheme ? ' ·当前' : ''}</div>
              <div className="ds">{(t.description ?? '').slice(0, 40)}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ensureHex(c: string | undefined): string {
  if (!c) return '#000000';
  if (/^#[0-9a-fA-F]{6}$/.test(c)) return c;
  return '#000000';
}
