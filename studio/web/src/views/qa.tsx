/** S6 验收视图：QA 规则结果 + 联络表 + 帧指标 + 成片播放 */
import React from 'react';
import {useStore} from '../store';
import {api} from '../api';

export function QaView() {
  const s = useStore();
  const qa = s.snap!.artifacts.qa;
  const metrics = s.snap!.artifacts.frame_metrics;

  if (!qa) return <div className="pane"><div className="empty">还没有 qa/report.json（先跑 S6）</div></div>;

  return (
    <div className="pane">
      <h2>
        机器验收
        <span className={`chip ${qa.passed ? 'ok' : 'err'}`} style={{marginLeft: 10}}>{qa.passed ? '全部通过' : '存在失败'}</span>
        <span className="chip mono" style={{marginLeft: 6}}>时长 {qa.duration_s?.toFixed?.(1)}s</span>
        {qa.freeze_seconds != null && <span className="chip mono" style={{marginLeft: 6}}>冻结 {qa.freeze_seconds?.toFixed?.(1)}s</span>}
      </h2>
      <div className="sub">R1 冻结 / R2 音频 / R3 时长 / R4 A-roll 画面 / R5 字幕带 —— 任一硬闸失败挡发布。</div>

      <div className="card">
        <table className="tbl">
          <thead><tr><th>规则</th><th>结果</th><th>值</th><th>期望</th></tr></thead>
          <tbody>
            {(qa.rules ?? []).map((r: any, i: number) => (
              <tr key={i}>
                <td className="mono">{r.rule}</td>
                <td><span className={`chip ${r.pass ? 'ok' : 'err'}`}>{r.pass ? 'PASS' : 'FAIL'}</span></td>
                <td className="mono">{String(r.value)}</td>
                <td className="muted mono">{String(r.expect)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {qa.sfx && (
          <div style={{marginTop: 10, display: 'flex', gap: 6}}>
            <span className="chip">音效可听度</span>
            <span className="chip ok">可听 {qa.sfx.audible ?? '—'}</span>
            <span className="chip warn">被掩蔽 {qa.sfx.masked ?? '—'}</span>
            <span className="chip err">未掩蔽 {qa.sfx.unmasked ?? '—'}</span>
          </div>
        )}
      </div>

      <div className="grid2">
        <div className="card">
          <div className="muted" style={{fontSize: 11, marginBottom: 8}}>联络表（contact-sheet）</div>
          {qa.contact_sheet
            ? <img src={api.fileUrl(s.jobId!, qa.contact_sheet)} style={{width: '100%', borderRadius: 8}} loading="lazy" />
            : <span className="faint">无</span>}
          {qa.contact_sheet_html && (
            <div style={{marginTop: 6}}>
              <a href={api.fileUrl(s.jobId!, qa.contact_sheet_html)} target="_blank" rel="noreferrer">
                <button className="small">打开逐帧 HTML 联络表</button>
              </a>
            </div>
          )}
        </div>
        <div className="card">
          <div className="muted" style={{fontSize: 11, marginBottom: 8}}>成片（video-final.mp4）</div>
          <video controls style={{width: '100%', maxHeight: 480, borderRadius: 8}}
                 src={api.fileUrl(s.jobId!, 'out/video-final.mp4')} />
          <div style={{marginTop: 8}}>
            <a href={api.fileUrl(s.jobId!, 'out/video-final.mp4')} download><button className="small">⬇ 下载成片</button></a>
          </div>
        </div>
      </div>

      {metrics && (
        <div className="card">
          <div className="muted" style={{fontSize: 11, marginBottom: 8}}>帧指标（建议级 · frame-metrics）</div>
          <table className="tbl">
            <thead><tr><th>镜头</th><th>hero_px</th><th>对象数</th><th>杂乱度</th><th>静态秒</th><th>标记</th></tr></thead>
            <tbody>
              {Object.entries(metrics.shots ?? metrics.frames ?? {}).map(([shot, m]: [string, any]) => (
                <tr key={shot}>
                  <td className="mono">{shot}</td>
                  <td className="mono">{m.hero_px ?? m.hero_px_ratio ?? '—'}</td>
                  <td className="mono">{m.object_count ?? '—'}</td>
                  <td className="mono">{m.clutter ?? '—'}</td>
                  <td className="mono">{m.static_seconds ?? '—'}</td>
                  <td>{(m.flags ?? []).map((f: string) => <span key={f} className="chip warn" style={{marginRight: 4}}>{f}</span>)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
