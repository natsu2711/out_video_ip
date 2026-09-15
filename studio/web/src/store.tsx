/** 全局状态：作业选择 + 产物草稿 + 撤销重做 + 保存 + 运行器轮询。
 * 纯 React context（与 Overlay Studio 同思路，不引第三方 store）。 */
import React, {createContext, useCallback, useContext, useEffect, useMemo, useRef, useState} from 'react';
import {api, type JobSummary, type RunInfo, type Shot, type Snapshot} from './api';

export type View = 'pipeline' | 'storyboard' | 'library' | 'recall' | 'script' | 'assets' | 'render' | 'qa' | 'theme';

interface Draft {
  sb: any | null;
  proj: any | null;
}

interface Store {
  jobs: JobSummary[];
  jobId: string | null;
  snap: Snapshot | null;
  loading: boolean;
  error: string | null;
  view: View;
  selectedShotId: string | null;
  sbDraft: any | null;
  projDraft: any | null;
  dirtySb: boolean;
  dirtyProj: boolean;
  stagedAssets: any | null;
  activeRun: RunInfo | null;
  toast: {kind: 'ok' | 'err' | 'info'; text: string} | null;
  canUndo: boolean;
  canRedo: boolean;
  // actions
  setView: (v: View) => void;
  selectJob: (id: string) => void;
  selectShot: (id: string | null) => void;
  refreshSummary: () => void;
  updateShot: (shotId: string, patch: Partial<Shot> | ((s: Shot) => Partial<Shot>), coalesce?: boolean) => void;
  setSbDraft: (updater: (sb: any) => any, coalesce?: boolean) => void;
  setProjDraft: (updater: (p: any) => any, coalesce?: boolean) => void;
  saveSb: () => Promise<void>;
  saveProj: () => Promise<void>;
  undo: () => void;
  redo: () => void;
  startRun: (label: string, fn: () => Promise<{run_id: string}>, onDone?: (run: RunInfo | null) => void) => void;
  reloadStaged: () => void;
  notify: (kind: 'ok' | 'err' | 'info', text: string) => void;
}

const Ctx = createContext<Store>(null as any);
export const useStore = () => useContext(Ctx);

export function StoreProvider({children}: {children: React.ReactNode}) {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [jobId, setJobId] = useState<string | null>(null);
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<View>('pipeline');
  const [selectedShotId, setSelectedShotId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft>({sb: null, proj: null});
  const [dirty, setDirty] = useState<{sb: boolean; proj: boolean}>({sb: false, proj: false});
  const [stagedAssets, setStagedAssets] = useState<any | null>(null);
  const [activeRun, setActiveRun] = useState<RunInfo | null>(null);
  const [toast, setToast] = useState<Store['toast']>(null);
  const undoRef = useRef<Draft[]>([]);
  const redoRef = useRef<Draft[]>([]);
  const lastPushRef = useRef(0);
  const [, forceRender] = useState(0);

  const notify = useCallback((kind: 'ok' | 'err' | 'info', text: string) => {
    setToast({kind, text});
    window.setTimeout(() => setToast((t) => (t?.text === text ? null : t)), kind === 'err' ? 6000 : 2600);
  }, []);

  const loadJobs = useCallback(async () => {
    try {
      const list = await api.jobs();
      setJobs(list);
      return list;
    } catch (e: any) {
      notify('err', `作业列表加载失败: ${e.message}`);
      return [];
    }
  }, [notify]);

  const selectJob = useCallback((id: string) => {
    setJobId(id);
    setSnap(null);
    setSelectedShotId(null);
    setDraft({sb: null, proj: null});
    setDirty({sb: false, proj: false});
    undoRef.current = [];
    redoRef.current = [];
    try {
      window.localStorage.setItem('ipStudioJob', id);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    loadJobs().then((list) => {
      let saved: string | null = null;
      try {
        saved = window.localStorage.getItem('ipStudioJob');
      } catch { /* ignore */ }
      const target = list.find((j) => j.id === saved && !j.error) ? saved : list.find((j) => !j.error)?.id ?? null;
      if (target) selectJob(target);
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // 作业快照加载
  useEffect(() => {
    if (!jobId) return;
    let alive = true;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const s = await api.snapshot(jobId);
        if (!alive) return;
        setSnap(s);
        setDraft({sb: s.artifacts.storyboard ?? null, proj: s.artifacts.project ?? null});
        setDirty({sb: false, proj: false});
        setSelectedShotId(s.artifacts.storyboard?.shots?.[0]?.id ?? null);
        try {
          const staged = await api.stageAssets(jobId);
          if (alive) setStagedAssets(staged.assets);
        } catch { /* staging 失败不阻塞 */ }
      } catch (e: any) {
        if (alive) setError(e.message);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [jobId]);

  const reloadStaged = useCallback(() => {
    if (!jobId) return;
    api.stageAssets(jobId).then((r) => setStagedAssets(r.assets)).catch(() => undefined);
  }, [jobId]);

  const refreshSummary = useCallback(() => {
    if (!jobId) return;
    api.job(jobId).then((s) => {
      setSnap((old) => (old ? {...old, summary: s} : old));
    }).catch(() => undefined);
    loadJobs().then((list) => {
      setJobs(list);
    });
  }, [jobId, loadJobs]);

  // ---- 草稿编辑 + 历史 ----
  const pushHistory = useCallback((force = false) => {
    const now = Date.now();
    if (!force && now - lastPushRef.current < 400) return; // 拖动/滑杆合并
    lastPushRef.current = now;
    undoRef.current = [...undoRef.current.slice(-49), {sb: draft.sb, proj: draft.proj}];
    redoRef.current = [];
    forceRender((n) => n + 1);
  }, [draft]);

  const setSbDraft = useCallback((updater: (sb: any) => any, coalesce = false) => {
    pushHistory(!coalesce);
    setDraft((d) => (d.sb ? {...d, sb: updater(d.sb)} : d));
    setDirty((x) => ({...x, sb: true}));
  }, [pushHistory]);

  const updateShot = useCallback((shotId: string, patch: Partial<Shot> | ((s: Shot) => Partial<Shot>), coalesce = false) => {
    setSbDraft((sb) => ({
      ...sb,
      shots: sb.shots.map((s: Shot) => (s.id === shotId ? {...s, ...(typeof patch === 'function' ? patch(s) : patch)} : s)),
    }), coalesce);
  }, [setSbDraft]);

  const setProjDraft = useCallback((updater: (p: any) => any) => {
    pushHistory(true);
    setDraft((d) => (d.proj ? {...d, proj: updater(d.proj)} : d));
    setDirty((x) => ({...x, proj: true}));
  }, [pushHistory]);

  const undo = useCallback(() => {
    const prev = undoRef.current.pop();
    if (!prev) return;
    redoRef.current.push({sb: draft.sb, proj: draft.proj});
    setDraft(prev);
    setDirty({sb: true, proj: true});
    forceRender((n) => n + 1);
  }, [draft]);

  const redo = useCallback(() => {
    const next = redoRef.current.pop();
    if (!next) return;
    undoRef.current.push({sb: draft.sb, proj: draft.proj});
    setDraft(next);
    setDirty({sb: true, proj: true});
    forceRender((n) => n + 1);
  }, [draft]);

  // ---- 保存 ----
  const saveArtifact = useCallback(async (name: 'storyboard' | 'project', content: any, mark: 'sb' | 'proj') => {
    if (!jobId) return;
    try {
      await api.saveArtifact(jobId, name, content);
      setDirty((x) => ({...x, [mark]: false}));
      notify('ok', `已保存 ${name}.json（schema 校验通过）`);
      refreshSummary();
    } catch (e: any) {
      notify('err', `保存失败: ${e.message}`);
    }
  }, [jobId, notify, refreshSummary]);

  const saveSb = useCallback(() => saveArtifact('storyboard', draft.sb, 'sb'), [draft.sb, saveArtifact]);
  const saveProj = useCallback(() => saveArtifact('project', draft.proj, 'proj'), [draft.proj, saveArtifact]);

  // ---- 运行器 ----
  const pollRef = useRef<number | null>(null);
  const startRun = useCallback((label: string, fn: () => Promise<{run_id: string}>, onDone?: (run: RunInfo | null) => void) => {
    fn().then(({run_id}) => {
      if (!run_id) {
        notify('ok', `${label} 完成`);
        onDone?.(null);
        return;
      }
      setActiveRun({id: run_id, job: jobId ?? '', label, status: 'running', started: Date.now()});
      notify('info', `已启动: ${label}`);
      if (pollRef.current) window.clearInterval(pollRef.current);
      pollRef.current = window.setInterval(async () => {
        try {
          const d = await api.runDetail(run_id);
          setActiveRun(d);
          if (d.status !== 'running') {
            window.clearInterval(pollRef.current!);
            pollRef.current = null;
            notify(d.status === 'done' ? 'ok' : 'err',
              `${label} ${d.status === 'done' ? '完成' : `失败(code ${d.returncode})`} —— 见日志`);
            refreshSummary();
            onDone?.(d);
          }
        } catch { /* 轮询失败忽略 */ }
      }, 1000);
    }).catch((e) => notify('err', `启动失败: ${e.message}`));
  }, [jobId, notify, refreshSummary]);

  useEffect(() => () => {
    if (pollRef.current) window.clearInterval(pollRef.current);
  }, []);

  // 快捷键：⌘Z / ⇧⌘Z / ⌘S
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      if (!mod) return;
      if (e.key.toLowerCase() === 'z') {
        e.preventDefault();
        if (e.shiftKey) redo();
        else undo();
      } else if (e.key.toLowerCase() === 's') {
        e.preventDefault();
        if (dirty.sb) saveSb();
        if (dirty.proj) saveProj();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [undo, redo, saveSb, saveProj, dirty.sb, dirty.proj]);

  const value = useMemo<Store>(() => ({
    jobs, jobId, snap, loading, error, view, selectedShotId,
    sbDraft: draft.sb, projDraft: draft.proj,
    dirtySb: dirty.sb, dirtyProj: dirty.proj,
    stagedAssets, activeRun, toast,
    canUndo: undoRef.current.length > 0,
    canRedo: redoRef.current.length > 0,
    setView, selectJob, selectShot: setSelectedShotId,
    refreshSummary, updateShot, setSbDraft, setProjDraft,
    saveSb, saveProj, undo, redo, startRun, reloadStaged, notify,
  }), [jobs, jobId, snap, loading, error, view, selectedShotId, draft, dirty, stagedAssets, activeRun, toast,
       setView, selectJob, refreshSummary, updateShot, setSbDraft, setProjDraft, saveSb, saveProj, undo, redo,
       startRun, reloadStaged, notify]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
