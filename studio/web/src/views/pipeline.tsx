/** 流水线总览：s0-s6 状态卡 + 运行/闸门 + 新建作业 */
import React, {useState} from 'react';
import {useStore} from '../store';
import {api} from '../api';
import {StatusChip} from '../ui';

const STAGE_INFO: Record<string, {name: string; desc: string}> = {
  s0: {name: 'S0 初始化', desc: '建目录、写 project.json、拷贝 IP 占位'},
  s1: {name: 'S1 脚本', desc: 'story.md → 结构化分段（LLM 可选，规则兜底）'},
  s2: {name: 'S2 配音对齐', desc: '本地 TTS + whisper 字级对齐 → timing.json'},
  s3: {name: 'S3 编排', desc: '分组选配方 → storyboard.json（人工闸门①）'},
  s4: {name: 'S4 素材', desc: 'manifest 登记 + 生图/实拍/图库素材'},
  s5: {name: 'S5 渲染', desc: 'preflight + Remotion 逐镜渲染 + concat（闸门②）'},
  s6: {name: 'S6 混音验收', desc: 'BGM/音效混音 + 机器 QA 规则'},
};

export function PipelineView() {
  const s = useStore();
  const snap = s.snap!;
  const sum = snap.summary;
  const [creating, setCreating] = useState(false);
  const [slug, setSlug] = useState('');
  const [title, setTitle] = useState('');
  const [story, setStory] = useState('');

  const run = (stage: string | null, force = false) => s.startRun(`run ${stage ?? 'all'}${force ? ' --force' : ''}`, () => api.run(s.jobId!, stage, force));
  const produce = () => s.startRun('一键成片 s1→s6（闸门自动放行）', () => api.produce(s.jobId!), (r) => {
    if (r?.status === 'done') s.notify('ok', '成片完成 → 验收页可看 video-final.mp4');
  });
  const gate = async (stage: string, approve: boolean) => {
    try {
      await api.gate(s.jobId!, stage, approve);
      s.notify('ok', approve ? `闸门 ${stage} 已放行` : `闸门 ${stage} 已驳回`);
      s.refreshSummary();
    } catch (e: any) {
      s.notify('err', e.message);
    }
  };

  const create = async () => {
    try {
      const j = await api.createJob(slug, title, story || null);
      s.notify('ok', `已创建 ${j.id}`);
      setCreating(false);
      s.selectJob(j.id);
      s.setView('pipeline');
    } catch (e: any) {
      s.notify('err', `创建失败: ${e.message}`);
    }
  };

  return (
    <div className="pipe">
      <div className="pipe-head">
        <div className="pipe-title">{sum.title}</div>
        <span className="chip mono">{sum.id}</span>
        {sum.canvas && <span className="kv"><span>画幅</span><b className="mono">{sum.canvas.width}×{sum.canvas.height}@{sum.canvas.fps}</b></span>}
        {sum.theme && <span className="kv"><span>主题</span><b className="mono">{sum.theme}</b></span>}
        {sum.next_runnable && <span className="chip acc">下一步: {sum.next_runnable}</span>}
        <div style={{flex: 1}} />
        <button onClick={() => setCreating(!creating)}>{creating ? '收起' : '＋ 新建作业'}</button>
        <button className="primary" onClick={() => run(null)}>▶ 运行到下一闸门</button>
        <button onClick={produce} title="全自动跑完 s1→s6，闸门自动放行，产出 out/video-final.mp4（90% 初稿）">⚡ 一键成片</button>
      </div>

      {creating && (
        <div className="card">
          <div className="grid3" style={{alignItems: 'end'}}>
            <div>
              <div className="muted" style={{fontSize: 11, marginBottom: 4}}>slug（小写字母/数字/连字符）</div>
              <input value={slug} onChange={(e) => setSlug(e.target.value)} placeholder="my-first-video" style={{width: '100%'}} />
            </div>
            <div>
              <div className="muted" style={{fontSize: 11, marginBottom: 4}}>标题</div>
              <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="视频标题" style={{width: '100%'}} />
            </div>
            <div>
              <div className="muted" style={{fontSize: 11, marginBottom: 4}}>story.md 内容（可留空后补）</div>
              <textarea rows={2} value={story} onChange={(e) => setStory(e.target.value)} placeholder="# 故事文稿…" style={{width: '100%'}} />
            </div>
          </div>
          <div style={{marginTop: 10}}>
            <button className="primary" disabled={!slug || !title} onClick={create}>初始化 S0</button>
          </div>
        </div>
      )}

      <div className="pipe-stages">
        {Object.keys(STAGE_INFO).map((st) => {
          const rec = sum.stages[st] ?? {status: 'pending'};
          const arts = sum.stage_artifacts?.[st] ?? [];
          const isGate = !!sum.gates?.[st];
          const blocked = rec.status === 'blocked';
          return (
            <div key={st} className={`stage-card ${rec.status === 'running' ? 'running' : ''}`}>
              <h3>{STAGE_INFO[st].name}</h3>
              <div className="stage-chips">
                <StatusChip status={rec.status} fresh={rec.fresh} />
                {isGate && <span className="chip">闸门</span>}
              </div>
              <div className="muted" style={{fontSize: 11}}>{STAGE_INFO[st].desc}</div>
              <div className="stage-note">{rec.note || '—'}</div>
              <div className="stage-arts">
                {arts.map((a) => (
                  <div key={a.rel} className={a.exists ? '' : 'missing'}>
                    {a.exists ? '●' : '○'} {a.rel}{a.count ? ` (${a.count})` : ''}
                  </div>
                ))}
              </div>
              <div className="stage-actions">
                {blocked ? (
                  <>
                    <button className="primary small" onClick={() => gate(st, true)}>✓ 放行</button>
                    <button className="danger small" onClick={() => gate(st, false)}>✕ 驳回</button>
                  </>
                ) : (
                  <>
                    <button className="small" disabled={rec.status === 'running'} onClick={() => run(st)}>▶ 运行</button>
                    <button className="small" disabled={rec.status === 'running'} onClick={() => run(st, true)} title="强制重跑（含 done）">↻ 强制</button>
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="card" style={{marginTop: 14}}>
        <div style={{display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'center'}}>
          <span className="muted" style={{fontSize: 12}}>快捷入口：</span>
          <button className="small" onClick={() => s.setView('storyboard')}>编排编辑 + 资产库页签（闸门①审阅对象）</button>
          <button className="small" onClick={() => s.setView('library')}>资产库（蒸馏外部项目/新增）</button>
          <button className="small" onClick={() => s.setView('theme')}>换主题/调色板</button>
          <a href={api.fileUrl(s.jobId!, 'docs/storyboard-table.md')} target="_blank" rel="noreferrer">
            <button className="small">编排表 story-board-table.md</button>
          </a>
        </div>
      </div>
    </div>
  );
}
