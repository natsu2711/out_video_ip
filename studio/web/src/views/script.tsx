/** S1 脚本视图：分段编辑（beat/visual_hint/text），保护 token 只读展示 */
import React, {useEffect, useState} from 'react';
import {useStore} from '../store';
import {api, fmtClock} from '../api';

export function ScriptView() {
  const s = useStore();
  const script = s.snap!.artifacts.script;
  const timing = s.snap!.artifacts.timing;
  const meta = s.snap!.meta;

  if (!script) return <div className="pane"><div className="empty">还没有 script.json（先跑 S1）</div></div>;
  return <ScriptEditor script={script} timing={timing} meta={meta} />;
}

function ScriptEditor({script, timing, meta}: {script: any; timing: any; meta: any}) {
  const s = useStore();
  const [local, setLocal] = useState(script);
  useEffect(() => setLocal(script), [script]);

  const dirty = JSON.stringify(local) !== JSON.stringify(script);

  const segStart = (segId: string) => {
    const t = timing?.segments.find((x) => x.seg_ref === segId);
    return t ? fmtClock(t.start_ms) : null;
  };

  const save = async () => {
    try {
      await api.saveArtifact(s.jobId!, 'script', local);
      s.notify('ok', '已保存 script.json（注意：下游 S2/S3 将标记 stale）');
      s.refreshSummary();
    } catch (e: any) {
      s.notify('err', `保存失败: ${e.message}`);
    }
  };

  return (
    <div className="pane">
      <h2>脚本 · {script.meta?.char_count ?? '—'} 字 · 预估 {script.meta?.est_duration_sec ?? '—'}s</h2>
      <div className="sub">
        保护 token（数字/型号不被转换）：
        {(script.meta?.protected_tokens as any[])?.slice(0, 10).map((t: any, i: number) => (
          <span key={i} className="chip" style={{marginRight: 4}}>{t.token ?? t}</span>
        ))}
        <div style={{flex: 1}} />
        {dirty && <span className="chip warn">未保存</span>}
        <button className="primary small" disabled={!dirty} onClick={save}>保存 script.json</button>
      </div>
      <div className="card">
        <table className="tbl">
          <thead><tr><th style={{width: 64}}>id</th><th style={{width: 90}}>beat</th><th style={{width: 90}}>画面</th><th>文本</th><th style={{width: 90}}>保护</th><th style={{width: 70}}>起点</th></tr></thead>
          <tbody>
            {local.segments.map((seg: any, i: number) => {
              const prot = seg.protected_tokens ?? [];
              return (
                <tr key={seg.id}>
                  <td className="mono faint">{seg.id}</td>
                  <td>
                    <select value={seg.beat} onChange={(e) => {
                      const next = {...local, segments: local.segments.map((x: any, j: number) => j === i ? {...x, beat: e.target.value} : x)};
                      setLocal(next);
                    }}>
                      {meta.beats.map((b) => <option key={b} value={b}>{b}</option>)}
                    </select>
                  </td>
                  <td>
                    <select value={seg.visual_hint} onChange={(e) => {
                      const next = {...local, segments: local.segments.map((x: any, j: number) => j === i ? {...x, visual_hint: e.target.value} : x)};
                      setLocal(next);
                    }}>
                      {meta.visual_hints.map((b) => <option key={b} value={b}>{b}</option>)}
                    </select>
                  </td>
                  <td>
                    <textarea rows={1} value={seg.text} style={{width: '100%', minHeight: 30}}
                      onChange={(e) => {
                        const next = {...local, segments: local.segments.map((x: any, j: number) => j === i ? {...x, text: e.target.value} : x)};
                        setLocal(next);
                      }} />
                  </td>
                  <td>{prot.length > 0 ? prot.map((p: any, k: number) => <span key={k} className="chip" style={{marginRight: 3}}>{p.token ?? p}</span>) : <span className="faint">—</span>}</td>
                  <td className="mono faint">{segStart(seg.id) ?? '—'}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
