import React from 'react';
import {createRoot} from 'react-dom/client';
import './index.css';
import './App.css';
import {StoreProvider, useStore, type View} from './store';
import {PipelineView} from './views/pipeline';
import {StoryboardView} from './views/storyboard';
import {LibraryView} from './views/library';
import {ScriptView} from './views/script';
import {AssetsView} from './views/assets';
import {RenderView} from './views/render';
import {QaView} from './views/qa';
import {RecallView} from './views/recall';
import {ThemeView} from './views/theme';
import {LogTail} from './ui';
import {fmtClock} from './api';

const TABS: {id: View; label: string}[] = [
  {id: 'pipeline', label: '流水线'},
  {id: 'storyboard', label: '编排'},
  {id: 'library', label: '资产库'},
  {id: 'recall', label: '召回调试'},
  {id: 'script', label: '脚本'},
  {id: 'assets', label: '素材'},
  {id: 'render', label: '渲染'},
  {id: 'qa', label: '验收'},
];

function TopBar() {
  const s = useStore();
  return (
    <div className="topbar">
      <div className="brand"><span className="logo">IP</span>Studio<span className="faint" style={{fontWeight: 400, fontSize: 11}}>· out_video-ip</span></div>
      <select value={s.jobId ?? ''} onChange={(e) => s.selectJob(e.target.value)} style={{maxWidth: 260}}
              title="选择作业">
        {s.jobs.map((j) => <option key={j.id} value={j.id}>{j.id} · {j.title}</option>)}
      </select>
      <div className="tabs">
        {TABS.map((t) => (
          <button key={t.id} className={s.view === t.id ? 'on' : ''} onClick={() => s.setView(t.id)}>{t.label}</button>
        ))}
      </div>
      <div style={{flex: 1}} />
      {(s.dirtySb || s.dirtyProj) && (
        <>
          <span className="chip warn">未保存</span>
          <button className="primary small" onClick={() => {
            if (s.dirtySb) s.saveSb();
            if (s.dirtyProj) s.saveProj();
          }}>保存 ⌘S</button>
        </>
      )}
      <button className="ghost small" disabled={!s.canUndo} onClick={s.undo} title="撤销 ⌘Z">↩</button>
      <button className="ghost small" disabled={!s.canRedo} onClick={s.redo} title="重做 ⇧⌘Z">↪</button>
      {s.activeRun?.status === 'running' && <span className="chip acc"><span className="spin" /> {s.activeRun.label}</span>}
    </div>
  );
}

function RunLogPanel() {
  const s = useStore();
  const [open, setOpen] = React.useState(true);
  const run = s.activeRun;
  if (!run) return null;
  return (
    <div className="runlog">
      <header>
        <span className="title">{run.label}</span>
        {run.status === 'running' && <span className="chip acc"><span className="spin" />运行中</span>}
        {run.status === 'done' && <span className="chip ok">完成</span>}
        {run.status === 'failed' && <span className="chip err">失败</span>}
        <button className="ghost small" onClick={() => setOpen(!open)}>{open ? '收起' : '展开'}</button>
      </header>
      {open && <LogTail lines={run.log ?? []} height={200} />}
    </div>
  );
}

function Toast() {
  const t = useStore().toast;
  if (!t) return null;
  return <div className={`toast ${t.kind}`}>{t.text}</div>;
}

function Clock() {
  const s = useStore();
  const run = s.activeRun;
  const [, tick] = React.useState(0);
  React.useEffect(() => {
    if (run?.status !== 'running') return;
    const iv = window.setInterval(() => tick((n) => n + 1), 500);
    return () => window.clearInterval(iv);
  }, [run?.status]);
  if (!run || run.status !== 'running') return null;
  return <span className="chip mono">{fmtClock((Date.now() - run.started))}</span>;
}

function Body() {
  const s = useStore();
  if (s.loading) return <div className="empty" style={{marginTop: 80}}><span className="spin" /> 加载作业数据…</div>;
  if (s.error) return <div className="empty" style={{marginTop: 80, color: 'var(--danger)'}}>加载失败: {s.error}</div>;
  if (!s.snap) return <div className="empty" style={{marginTop: 80}}>左侧选择或新建一个作业</div>;
  switch (s.view) {
    case 'pipeline': return <PipelineView />;
    case 'storyboard': return <StoryboardView />;
    case 'library': return <LibraryView />;
    case 'recall': return <RecallView />;
    case 'script': return <ScriptView />;
    case 'assets': return <AssetsView />;
    case 'render': return <RenderView />;
    case 'qa': return <QaView />;
    case 'theme': return <ThemeView />;
    default: return null;
  }
}

function App() {
  return (
    <StoreProvider>
      <div className="app">
        <TopBar />
        <div className="app-body" style={{gridTemplateColumns: '1fr'}}>
          <Body />
        </div>
        <Toast />
        <RunLogPanel />
        <Clock />
      </div>
    </StoreProvider>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
