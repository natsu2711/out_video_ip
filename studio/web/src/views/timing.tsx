/** S2 配音视图：vo.wav 播放 + 分段对齐检查（置信度着色、词级详情） */
import React, {useEffect, useRef, useState} from 'react';
import {useStore} from '../store';
import {api, fmtClock, type TimingSegment} from '../api';

const CONF_COLOR: Record<string, string> = {high: 'var(--ok)', medium: 'var(--warn)', low: 'var(--danger)'};

export function TimingView() {
  const s = useStore();
  const timing = s.snap!.artifacts.timing;
  const audioRef = useRef<HTMLAudioElement>(null);
  const [curMs, setCurMs] = useState(0);
  const [sel, setSel] = useState<string | null>(null);

  if (!timing) return <div className="pane"><div className="empty">还没有 timing.json（先跑 S2）</div></div>;

  const curSeg = timing.segments.find((t: TimingSegment) => curMs >= t.start_ms && curMs < t.end_ms);
  const selSeg = timing.segments.find((t: TimingSegment) => t.id === (sel ?? curSeg?.id));

  const seek = (ms: number) => {
    if (audioRef.current) audioRef.current.currentTime = ms / 1000;
    setCurMs(ms);
  };

  const gaps: number[] = [];
  for (let i = 1; i < timing.segments.length; i++) {
    gaps.push(timing.segments[i].start_ms - timing.segments[i - 1].end_ms);
  }
  const maxGap = Math.max(0, ...gaps);

  return (
    <div className="pane">
      <h2>配音与对齐 <span className="chip mono" style={{marginLeft: 8}}>{timing.backend}</span></h2>
      <div className="sub">
        总长 {fmtClock(timing.duration_ms)} · {timing.segments.length} 段 · 最大间隙 {maxGap}ms
        {timing.invariants && <span className="chip" style={{marginLeft: 8}}>{JSON.stringify(timing.invariants)}</span>}
      </div>

      <div className="card">
        <audio ref={audioRef} controls style={{width: '100%'}}
               src={api.fileUrl(s.jobId!, timing.audio || 'audio/vo.wav')}
               onTimeUpdate={(e) => setCurMs((e.target as HTMLAudioElement).currentTime * 1000)} />
        <div style={{marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap'}}>
          <button className="small" onClick={() => seek(curSeg?.start_ms ?? 0)}>◀ 回到当前段头</button>
          <span className="chip mono">{fmtClock(curMs)}</span>
          {curSeg && <span className="chip acc">{curSeg.id}</span>}
        </div>
      </div>

      <div className="card">
        <table className="tbl">
          <thead><tr><th>id</th><th>区间</th><th>置信度</th><th>匹配</th><th>词数</th><th>文本</th></tr></thead>
          <tbody>
            {timing.segments.map((t: TimingSegment) => {
              const on = t.id === selSeg?.id;
              return (
                <tr key={t.id} className={`click ${on ? 'on' : ''}`} onClick={() => {setSel(t.id); seek(t.start_ms);}}>
                  <td className="mono faint">{t.id}</td>
                  <td className="mono">{fmtClock(t.start_ms)}–{fmtClock(t.end_ms)}</td>
                  <td><span style={{color: CONF_COLOR[t.align_confidence ?? 'high'], fontWeight: 700}}>{t.align_confidence ?? 'high'}</span></td>
                  <td className="mono">{t.match != null ? t.match.toFixed(2) : '—'}</td>
                  <td className="mono">{t.words?.length ?? 0}</td>
                  <td>{t.text}{t.ok === false && <span className="chip err" style={{marginLeft: 6}}>校验未过</span>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {selSeg?.words && (
        <div className="card">
          <div className="muted" style={{fontSize: 11, marginBottom: 6}}>词级时间轴（{selSeg.id}）· 保护词高亮</div>
          <div style={{display: 'flex', flexWrap: 'wrap', gap: 4}}>
            {selSeg.words.map((w, i) => (
              <span key={i} className={`chip ${w.protected ? 'acc' : ''}`} title={`${w.start_ms}–${w.end_ms}ms`}
                    onClick={() => seek(w.start_ms)} style={{cursor: 'pointer'}}>
                {w.text}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
