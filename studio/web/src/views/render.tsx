/** S5 渲染视图：preflight / 逐镜重渲 / 整体渲染 / 产物下载 */
import React, {useEffect, useState} from 'react';
import {useStore} from '../store';
import {api} from '../api';
import {Section} from '../ui';

function humanSize(n: number): string {
  if (n > 1e9) return `${(n / 1e9).toFixed(2)} GB`;
  if (n > 1e6) return `${(n / 1e6).toFixed(1)} MB`;
  return `${(n / 1e3).toFixed(0)} KB`;
}

export function RenderView() {
  const s = useStore();
  const sb = s.sbDraft;
  const [status, setStatus] = useState<{segments: Record<string, any>; props: Record<string, any>; outputs: Record<string, any>} | null>(null);

  const load = () => {
    fetch(`/api/job/${s.jobId}/render-status`).then((r) => r.json()).then(setStatus).catch(() => undefined);
  };
  useEffect(load, [s.jobId, s.activeRun?.status]);

  if (!sb) return <div className="pane"><div className="empty">无 storyboard</div></div>;

  const segs = status?.segments ?? {};
  const outputs = status?.outputs ?? {};

  return (
    <div className="pane">
      <h2>渲染合成</h2>
      <div className="sub">preflight 通过后逐镜渲染（Remotion）→ concat。改过编排后可只重渲单个镜头。</div>

      <div className="card">
        <div style={{display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center'}}>
          <button className="small" onClick={() => s.startRun('preflight', () => api.tool(s.jobId!, 'preflight'))}>▶ Preflight（9 组断言）</button>
          <button className="primary small" onClick={() => s.startRun('run s5（全量渲染）', () => api.run(s.jobId!, 's5', true))}>▶ 全量渲染 s5 --force</button>
          <button className="small" onClick={load}>↻ 刷新产物状态</button>
          {Object.entries(outputs).map(([name, o]) => (
            <a key={name} href={api.fileUrl(s.jobId!, o.path)} target="_blank" rel="noreferrer">
              <button className="small">⬇ {name}（{humanSize(o.size)}）</button>
            </a>
          ))}
        </div>
      </div>

      <div className="card">
        <table className="tbl">
          <thead><tr><th>镜头</th><th>配方</th><th>时长</th><th>props</th><th>segment.mp4</th><th>操作</th></tr></thead>
          <tbody>
            {sb.shots.map((sh: any) => {
              const fps = s.projDraft?.canvas?.fps ?? 30;
              const dur = ((sh.time.end_ms - sh.time.start_ms) / 1000).toFixed(1);
              const hasSeg = !!segs[sh.id];
              return (
                <tr key={sh.id}>
                  <td className="mono">{sh.id}</td>
                  <td>{sh.recipe_ref}</td>
                  <td className="mono">{dur}s</td>
                  <td>{status?.props?.[sh.id]
                    ? <a href={api.fileUrl(s.jobId!, status.props[sh.id].path)} target="_blank" rel="noreferrer" className="mono faint">props-{sh.id}.json</a>
                    : <span className="faint">未生成</span>}</td>
                  <td>{hasSeg ? <span className="chip ok">{humanSize(segs[sh.id].size)}</span> : <span className="chip">未渲染</span>}</td>
                  <td>
                    <button className="small" onClick={() => s.startRun(`render ${sh.id}`, () => api.renderShot(s.jobId!, sh.id))}>单镜重渲</button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {outputs['video-silent.mp4'] && (
        <div className="card">
          <Section title="合成结果（无音频）">
            <video controls style={{width: '100%', maxHeight: 420, borderRadius: 8}}
                   src={api.fileUrl(s.jobId!, 'out/video-silent.mp4')} />
          </Section>
        </div>
      )}
    </div>
  );
}
