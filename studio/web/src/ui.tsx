/** 共享控件：schema 驱动的参数行（仿 Overlay Studio ParamsPanel）+ 徽章/按钮组 */
import React, {useEffect, useRef, useState} from 'react';

export type Control =
  | {key: string; label: string; type: 'range'; min: number; max: number; step: number; unit?: string; help?: string}
  | {key: string; label: string; type: 'text'; help?: string}
  | {key: string; label: string; type: 'textarea'; rows?: number; help?: string}
  | {key: string; label: string; type: 'select'; options: {label: string; value: string}[]; help?: string}
  | {key: string; label: string; type: 'toggle'; help?: string}
  | {key: string; label: string; type: 'color'; help?: string}
  | {key: string; label: string; type: 'textlist'; max?: number; cap?: number; help?: string}
  | {key: string; label: string; type: 'json'; help?: string};

export function StatusChip({status, fresh}: {status?: string; fresh?: boolean}) {
  if (!status) return <span className="chip">未开始</span>;
  const map: Record<string, string> = {done: 'ok', failed: 'err', running: 'acc', blocked: 'warn', pending: ''};
  const cls = map[status] ?? '';
  const label: Record<string, string> = {done: '完成', failed: '失败', running: '运行中', blocked: '待闸门', pending: '待执行'};
  return (
    <>
      <span className={`chip ${cls}`}>{label[status] ?? status}</span>
      {status === 'done' && fresh === false && <span className="chip warn" title="产物或输入已变更，建议重跑">stale</span>}
      {status === 'done' && fresh === true && <span className="chip" title="指纹校验一致">fresh</span>}
    </>
  );
}

export function Section({title, extra, children, sectionId}: {title: string; extra?: React.ReactNode; children: React.ReactNode; sectionId?: string}) {
  return (
    <div id={sectionId} style={{borderBottom: '1px solid var(--hairline)', padding: '10px 14px'}}>
      <div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8}}>
        <div style={{fontSize: 11, letterSpacing: 1, color: 'var(--ink-faint)', fontWeight: 700}}>{title}</div>
        {extra}
      </div>
      {children}
    </div>
  );
}

export function Row({label, children, help}: {label: string; children: React.ReactNode; help?: string}) {
  return (
    <div style={{display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 7}}>
      <div style={{width: 72, flexShrink: 0, color: 'var(--ink-muted)', fontSize: 12, paddingTop: 4}} title={help}>{label}</div>
      <div style={{flex: 1, minWidth: 0}}>{children}</div>
    </div>
  );
}

/** textlist：字符串数组编辑（TEXT/STEPS），带条数上限与超长提示 */
export function TextListField({value, onChange, max, cap}: {
  value: string[]; onChange: (v: string[]) => void; max?: number; cap?: number;
}) {
  const list = value ?? [];
  const set = (i: number, v: string) => {
    const next = [...list];
    next[i] = v;
    onChange(next);
  };
  return (
    <div style={{display: 'flex', flexDirection: 'column', gap: 5}}>
      {list.map((t, i) => (
        <div key={i} style={{display: 'flex', gap: 4, alignItems: 'center'}}>
          <span className="faint mono" style={{fontSize: 11, width: 16}}>{i + 1}</span>
          <input
            value={t}
            onChange={(e) => set(i, e.target.value)}
            style={{flex: 1, borderColor: cap && t.length > cap ? 'var(--warn)' : undefined}}
          />
          {cap && t.length > cap && <span className="chip warn" title={`建议 ≤${cap} 字（渲染会截断）`}>{t.length}</span>}
          <button className="ghost small" title="删除此条" onClick={() => onChange(list.filter((_, j) => j !== i))}>✕</button>
        </div>
      ))}
      <div>
        {(!max || list.length < max) && (
          <button className="small" onClick={() => onChange([...list, ''])}>＋ 加一条{max ? `（≤${max}）` : ''}</button>
        )}
      </div>
    </div>
  );
}

export function JsonField({value, onChange, rows = 5}: {value: unknown; onChange: (v: unknown) => void; rows?: number}) {
  const [text, setText] = useState(() => JSON.stringify(value ?? null, null, 2));
  const [err, setErr] = useState<string | null>(null);
  const [dirtyLocal, setDirtyLocal] = useState(false);
  useEffect(() => {
    if (!dirtyLocal) setText(JSON.stringify(value ?? null, null, 2));
  }, [value]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div>
      <textarea
        rows={rows}
        value={text}
        spellCheck={false}
        onChange={(e) => {
          setText(e.target.value);
          setDirtyLocal(true);
          try {
            onChange(JSON.parse(e.target.value));
            setErr(null);
          } catch (ex: any) {
            setErr(ex.message);
          }
        }}
        style={{width: '100%', borderColor: err ? 'var(--danger)' : undefined}}
      />
      {err && <div className="chip err" style={{marginTop: 3}}>JSON 解析失败: {err}</div>}
    </div>
  );
}

/** 通用 ControlRow：按 control.type 渲染编辑器 */
export function ControlRow({control, value, onChange}: {
  control: Control; value: unknown; onChange: (v: unknown) => void;
}) {
  const c = control;
  if (c.type === 'range') {
    const v = typeof value === 'number' ? value : (c.min ?? 0);
    return (
      <Row label={c.label} help={c.help}>
        <div style={{display: 'flex', alignItems: 'center', gap: 8}}>
          <input type="range" min={c.min} max={c.max} step={c.step} value={v}
                 onChange={(e) => onChange(parseFloat(e.target.value))} style={{flex: 1}} />
          <span className="mono" style={{fontSize: 12, width: 52, textAlign: 'right'}}>{v}{c.unit ?? ''}</span>
        </div>
      </Row>
    );
  }
  if (c.type === 'select') {
    return (
      <Row label={c.label} help={c.help}>
        <select value={String(value ?? '')} onChange={(e) => onChange(e.target.value)} style={{width: '100%'}}>
          {c.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </Row>
    );
  }
  if (c.type === 'toggle') {
    return (
      <Row label={c.label} help={c.help}>
        <button
          role="switch"
          aria-checked={!!value}
          onClick={() => onChange(!value)}
          style={{background: value ? 'var(--accent)' : 'var(--fill-subtle)', borderColor: value ? 'var(--accent)' : 'var(--hairline-strong)', color: value ? '#fff' : 'var(--ink-muted)', width: 40, borderRadius: 999, position: 'relative', height: 20, padding: 0}}
        >
          <span style={{position: 'absolute', top: 2, left: value ? 22 : 2, width: 14, height: 14, borderRadius: '50%', background: '#fff', transition: 'left 0.15s'}} />
        </button>
      </Row>
    );
  }
  if (c.type === 'color') {
    return (
      <Row label={c.label} help={c.help}>
        <div style={{display: 'flex', gap: 6, alignItems: 'center'}}>
          <input type="color" value={String(value ?? '#000000')} onChange={(e) => onChange(e.target.value)}
                 style={{width: 40, height: 26, padding: 1}} />
          <input value={String(value ?? '')} onChange={(e) => onChange(e.target.value)} className="mono" style={{flex: 1, fontSize: 12}} />
        </div>
      </Row>
    );
  }
  if (c.type === 'textlist') {
    return (
      <Row label={c.label} help={c.help}>
        <TextListField value={(value as string[]) ?? []} onChange={onChange} max={c.max} cap={c.cap ?? 16} />
      </Row>
    );
  }
  if (c.type === 'json') {
    return (
      <Row label={c.label} help={c.help}>
        <JsonField value={value} onChange={onChange} rows={6} />
      </Row>
    );
  }
  if (c.type === 'textarea') {
    return (
      <Row label={c.label} help={c.help}>
        <textarea rows={c.rows ?? 3} value={String(value ?? '')} onChange={(e) => onChange(e.target.value)} style={{width: '100%'}} />
      </Row>
    );
  }
  return (
    <Row label={c.label} help={c.help}>
      <input value={String(value ?? '')} onChange={(e) => onChange(e.target.value)} style={{width: '100%'}} />
    </Row>
  );
}

/** 多选胶囊（overlay ≤2 之类） */
export function MultiCapsule({options, value, onChange, max}: {
  options: string[]; value: string[]; onChange: (v: string[]) => void; max?: number;
}) {
  const cur = value ?? [];
  const toggle = (o: string) => {
    if (cur.includes(o)) onChange(cur.filter((x) => x !== o));
    else if (!max || cur.length < max) onChange([...cur, o]);
  };
  return (
    <div style={{display: 'flex', flexWrap: 'wrap', gap: 5}}>
      {options.map((o) => {
        const on = cur.includes(o);
        return (
          <button key={o} className="small" onClick={() => toggle(o)}
                  style={on ? {background: 'var(--accent-soft)', borderColor: 'var(--accent)', color: 'var(--accent)'} : undefined}>
            {o}{on ? ' ✓' : ''}
          </button>
        );
      })}
    </div>
  );
}

/** 自动刷新的日志尾部 */
export function LogTail({lines, height = 220}: {lines: string[]; height?: number}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [lines.length]);
  return (
    <div ref={ref} className="mono"
         style={{background: '#0b0b0f', border: '1px solid var(--hairline)', borderRadius: 8, padding: 10,
                 fontSize: 11, lineHeight: 1.6, overflow: 'auto', height, whiteSpace: 'pre-wrap'}}>
      {lines.length === 0 ? <span className="faint">等待输出…</span> : lines.map((l, i) => (
        <div key={i} style={{color: l.includes('✗') || l.toLowerCase().includes('fail') || l.includes('Error') ? 'var(--danger)'
                               : l.includes('✔') || l.toLowerCase().includes('ok') ? 'var(--ok)' : 'var(--ink-muted)'}}>{l}</div>
      ))}
    </div>
  );
}
