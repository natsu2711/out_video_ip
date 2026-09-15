/** 编排编辑器：左镜头列表 / 中实时画布+时间轴 / 右参数面板。
 * 时间轴拖拽边界 = 重新分配 seg_ids（timing 段在镜头间的分组），保存后 s3_check 会重算时间。
 * 游标（任意秒定位）→ 检查器：此刻的画面上下文 + 拆分 + 加音效 + 换效果/加图层。 */
import React, {useEffect, useMemo, useRef, useState} from 'react';
import type {PlayerRef} from '@remotion/player';
import {useStore} from '../store';
import {api, type Shot, fmtClock} from '../api';
import {StudioShotPlayer} from '../preview/StudioPlayer';
import {CARD_REGISTRY} from '../preview/StudioCardHost';
import {deriveTexts} from '../../../../render-engine/src/cards/content';
import {MultiCapsule, Row, Section, TextListField, JsonField} from '../ui';
import {EffectPicker} from './EffectPicker';
import {AssetPanel} from './AssetPanel';

const A_ROLL_COLOR = '#ff4b1f';
const B_ROLL_COLOR = '#5fa0fa';
const CARD_COLOR = '#f3a712';

function recipeColor(shot: Shot): string {
  if (shot.roll === 'A') return A_ROLL_COLOR;
  if (shot.recipe_ref?.startsWith('card:')) return CARD_COLOR;
  return B_ROLL_COLOR;
}

/** 用 timing 段重算镜头的 time/vo（与 s3_check 同口径：start=min, end=max） */
function recomputeShotFromSegs(shot: Shot, timing: any): Shot {
  const segs = (shot.time.seg_ids ?? [])
    .map((sid: string) => timing.segments.find((t: any) => t.id === sid))
    .filter(Boolean)
    .sort((a: any, b: any) => a.start_ms - b.start_ms);
  if (segs.length === 0) return shot;
  return {
    ...shot,
    time: {...shot.time, start_ms: segs[0].start_ms, end_ms: segs[segs.length - 1].end_ms},
    vo: segs.map((t: any) => t.text).join(''),
  };
}

export function StoryboardView() {
  const s = useStore();
  const sb = s.sbDraft;
  const timing = s.snap!.artifacts.timing;
  const proj = s.projDraft;
  const playerRef = useRef<PlayerRef>(null);
  const [curFrame, setCurFrame] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [cursorMs, setCursorMs] = useState<number | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerLayer, setPickerLayer] = useState(false);
  const [selLayerId, setSelLayerId] = useState<string | null>(null);
  const [rightTab, setRightTab] = useState<'props' | 'assets'>('props');
  const [routeMode, setRouteMode] = useState<'auto' | 'llm'>('llm');
  const changeRouteMode = (m: 'auto' | 'llm') => {
    setRouteMode(m);
    api.setRouteMode(s.jobId!, m).then((r) => s.notify('ok', r.note ?? `已切 ${m}`)).catch((e) => s.notify('err', e.message));
  };
  useEffect(() => {
    if (s.jobId) api.getRouteMode(s.jobId).then((r) => setRouteMode(r.route_mode)).catch(() => undefined);
  }, [s.jobId]);

  // 全局 JobData（与 s5 props 同构）：storyboard/project 用草稿 → 改动即时反映到预览
  const data = useMemo(() => {
    if (!sb || !proj || !timing) return null;
    return {
      job: {id: s.jobId ?? '', root: ''},
      project: proj,
      timing,
      storyboard: sb,
      assets: s.stagedAssets ?? s.snap!.artifacts.manifest ?? {ip_images: {}},
    };
  }, [sb, proj, timing, s.jobId, s.stagedAssets, s.snap]);

  const shot = sb?.shots?.find((x: Shot) => x.id === s.selectedShotId) ?? sb?.shots?.[0];

  // Player 帧 → 播放状态同步
  useEffect(() => {
    const ref = playerRef.current;
    if (!ref) return;
    const onFrame = () => setCurFrame(ref.getCurrentFrame());
    const onPlay = () => setPlaying(true);
    const onPause = () => setPlaying(false);
    ref.addEventListener('frameupdate', onFrame);
    ref.addEventListener('play', onPlay);
    ref.addEventListener('pause', onPause);
    return () => {
      ref.removeEventListener('frameupdate', onFrame);
      ref.removeEventListener('play', onPlay);
      ref.removeEventListener('pause', onPause);
    };
  }, [shot?.id, data]);

  // 键盘 scrub（借鉴 Overlay Studio）：空格播放/暂停，←/→ 单帧，Shift ±10 帧
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      if (!playerRef.current) return;
      const step = e.shiftKey ? 10 : 1;
      if (e.code === 'Space') {
        e.preventDefault();
        const ref = playerRef.current;
        if (ref.isPlaying()) ref.pause();
        else ref.play();
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        playerRef.current.seekTo(Math.max(0, playerRef.current.getCurrentFrame() - step));
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        playerRef.current.seekTo(playerRef.current.getCurrentFrame() + step);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  if (!sb || !timing || !proj || !data) {
    return <div className="empty" style={{marginTop: 80}}>该作业缺少 storyboard.json / timing.json / project.json（先跑 S2/S3）</div>;
  }

  const fps = proj.canvas.fps;
  const totalMs = sb.shots.reduce((m: number, x: Shot) => Math.max(m, x.time.end_ms), 0);

  const seekLocalMs = (localMs: number) => {
    if (!playerRef.current) return;
    playerRef.current.seekTo(Math.floor(localMs / 1000 * fps));
  };
  // 选镜后跳到代表性帧（35% 处）：卡是冲击式入场，f0 往往近乎空白，misleading
  const selectAndFrame = (id: string) => {
    s.selectShot(id);
    const sh = sb.shots.find((x: Shot) => x.id === id);
    if (sh) {
      const dur = sh.time.end_ms - sh.time.start_ms;
      window.setTimeout(() => seekLocalMs(dur * 0.35), 60);
    }
  };
  const togglePlay = () => {
    const ref = playerRef.current;
    if (!ref) return;
    if (ref.isPlaying()) ref.pause();
    else ref.play();
  };

  // ---- 游标（任意秒定位）：上下文推导 ----
  const cursorCtx = useMemo(() => {
    if (cursorMs == null) return null;
    const cShot = sb.shots.find((x: Shot) => cursorMs >= x.time.start_ms && cursorMs < x.time.end_ms) ?? null;
    const seg = timing.segments.find((t: any) => cursorMs >= t.start_ms && cursorMs < t.end_ms) ?? null;
    const word = seg?.words?.find((w: any) => cursorMs >= w.start_ms && cursorMs < w.end_ms) ?? null;
    const localMs = cShot ? cursorMs - cShot.time.start_ms : 0;
    const activeLayers = (cShot?.layers ?? []).filter((l: any) =>
      l.enabled !== false && localMs >= (l.in_ms ?? 0) && (l.out_ms == null || localMs < l.out_ms));
    const nearSfx = (cShot?.sfx ?? []).filter((c: any) => Math.abs(cShot.time.start_ms + c.t_ms - cursorMs) < 900);
    return { cShot, seg, word, localMs, activeLayers, nearSfx };
  }, [cursorMs, sb, timing]);

  // ---- 光标处拆分镜头（确定性：seg_ids 重分组 + 新镜号）----
  const splitAtCursor = () => {
    if (cursorCtx?.cShot !== shot || cursorMs == null || !shot) return;
    const segs = (shot.time.seg_ids ?? [])
      .map((sid: string) => timing.segments.find((t: any) => t.id === sid))
      .filter(Boolean)
      .sort((a: any, b: any) => a.start_ms - b.start_ms);
    const idx = segs.findIndex((t: any) => t.start_ms >= cursorMs);
    if (idx <= 0) {
      s.notify('err', segs.length <= 1 ? '该镜头只含 1 个 timing 段，无法拆分（相邻镜头边界可直接拖动重分组）' : '光标落在首段内：请把光标移到第二段起点之后再拆');
      return;
    }
    const left = segs.slice(0, idx).map((t: any) => t.id);
    const right = segs.slice(idx).map((t: any) => t.id);
    const maxNum = Math.max(...sb.shots.map((x: Shot) => parseInt(x.id.replace(/\D/g, ''), 10) || 0));
    const newId = `S${String(maxNum + 1).padStart(3, '0')}`;
    s.setSbDraft((draft) => {
      const shots = [...draft.shots];
      const i = shots.findIndex((x: Shot) => x.id === shot.id);
      const origin = shots[i];
      const mk = (segIds: string[], id: string) => recomputeShotFromSegs({
        ...origin, id,
        time: {...origin.time, seg_ids: segIds},
        sfx: id === newId ? [] : origin.sfx,
        layers: id === newId ? JSON.parse(JSON.stringify(origin.layers ?? [])) : origin.layers,
      }, timing);
      shots.splice(i, 1, mk(left, origin.id), mk(right, newId));
      return {...draft, shots};
    });
    s.notify('ok', `已拆分：${shot.id} + 新镜 ${newId}（保存后可跑服务端校验重算时间）`);
  };

  // ---- 客户端 lint（与 card_lint/s3_check 同口径的子集）----
  const lint = useMemo(() => {
    const out: {level: 'err' | 'warn'; shot?: string; msg: string}[] = [];
    for (const sh of sb.shots) {
      const dur = (sh.time.end_ms - sh.time.start_ms) / 1000;
      if (dur < 2) out.push({level: 'warn', shot: sh.id, msg: `时长 ${dur.toFixed(2)}s < 2s`});
      if (dur > 18) out.push({level: 'warn', shot: sh.id, msg: `时长 ${dur.toFixed(2)}s > 18s`});
      if (sh.recipe_ref?.startsWith('card:')) {
        const entry = CARD_REGISTRY[sh.recipe_ref.slice(5)];
        if (!entry) out.push({level: 'err', shot: sh.id, msg: `未注册的卡: ${sh.recipe_ref}`});
        else {
          const nT = entry.arities?.TEXT ?? 0;
          if (nT > 0 && (sh.config?.TEXT ?? []).length > 0 && (sh.config?.TEXT ?? []).length !== nT) {
            out.push({level: 'warn', shot: sh.id, msg: `TEXT ${sh.config?.TEXT.length} 条 ≠ 卡要求 ${nT} 条`});
          }
          for (const t of [...(sh.config?.TEXT ?? []), ...(sh.config?.STEPS ?? [])]) {
            if (t.length > 16) out.push({level: 'warn', shot: sh.id, msg: `文案超 16 字: "${t.slice(0, 12)}…"`});
          }
          const nS = entry.arities?.STEPS ?? 0;
          if (nS > 0 && (sh.config?.STEPS ?? []).length > 0 && (sh.config?.STEPS ?? []).length !== nS) {
            out.push({level: 'warn', shot: sh.id, msg: `STEPS ${sh.config?.STEPS.length} 条 ≠ 卡要求 ${nS} 条`});
          }
        }
      }
      for (const c of sh.sfx ?? []) {
        if (!s.snap!.meta.sfx.includes(c.name)) out.push({level: 'warn', shot: sh.id, msg: `音效不存在: ${c.name}`});
      }
      if ((sh.overlay?.length ?? 0) > 2) out.push({level: 'warn', shot: sh.id, msg: 'overlay > 2（渲染只取前 2）'});
    }
    return out;
  }, [sb, s.snap]);

  return (
    <div className="sb">
      <ShotList shots={sb.shots} selected={shot?.id} onSelect={(id) => {
        selectAndFrame(id);
        setSelLayerId(null);
      }} />
      <div className="sb-center">
        <CanvasBox data={data} shotId={shot?.id} playerRef={playerRef} fps={fps}
                   curFrame={curFrame} playing={playing} onTogglePlay={togglePlay}
                   onSeekLocal={seekLocalMs}
                   shotObj={shot} selLayerId={selLayerId}
                   onSelectLayer={setSelLayerId}
                   onLayerPatch={(layerId, patch, coalesce) => {
                     if (!shot) return;
                     s.updateShot(shot.id, (x) => ({
                       layers: (x.layers ?? []).map((y) => y.id === layerId ? {...y, ...patch} : y),
                     } as any), coalesce);
                   }}
                   extra={
                     <>
                       <select value={`${s.projDraft?.canvas?.width}x${s.projDraft?.canvas?.height}`}
                               onChange={(e) => {
                                 const [w, h] = e.target.value.split('x').map(Number);
                                 if (!s.projDraft) return;
                                 s.setProjDraft((pr) => ({...pr, canvas: {...pr.canvas, width: w, height: h,
                                   ratio: w > h ? '16:9' : '9:16'}}));
                                 s.saveProj();
                                 s.notify('ok', `画幅已切为 ${w}×${h}（重渲后生效）`);
                               }}
                               title="画幅切换（横屏/竖屏），写入 project.json">
                         <option value="1920x1080">横屏 16:9</option>
                         <option value="1080x1920">竖屏 9:16</option>
                       </select>
                       <select value={routeMode} onChange={(e) => changeRouteMode(e.target.value as any)}
                               title="S3 画面配方路由方式：auto=本地确定性规则（同文案同画面，无 LLM）；llm=大模型在白名单池内选">
                         <option value="auto">路由: 自动规则</option>
                         <option value="llm">路由: 大模型</option>
                       </select>
                       <button className="small" disabled={!shot}
                               onClick={() => { setPickerLayer(false); setPickerOpen(true); }}>
                          🎬 换效果
                       </button>
                     </>
                   } />
        <CursorInspector ctx={cursorCtx} cursorMs={cursorMs} fps={fps}
                         onPlay={() => { if (cursorCtx?.cShot) { s.selectShot(cursorCtx.cShot.id); window.setTimeout(() => { seekLocalMs(cursorMs! - cursorCtx.cShot.time.start_ms); playerRef.current?.play(); }, 30); } }}
                         onSplit={splitAtCursor}
                         onAddSfx={() => {
                           if (cursorCtx?.cShot !== shot || !shot) return;
                           const cue = {t_ms: Math.max(0, Math.round(cursorMs! - shot.time.start_ms)), name: meta0Sfx(s), gain: 1};
                           s.updateShot(shot.id, (x) => ({sfx: [...(x.sfx ?? []), cue]}));
                           s.notify('ok', `已在光标处加音效 ${cue.name}@${cue.t_ms}ms`);
                         }}
                         onSwapEffect={() => { setPickerLayer(false); setPickerOpen(true); }}
                         onAddLayer={() => { setPickerLayer(true); setPickerOpen(true); }} />
        <Timeline
          shots={sb.shots} timing={timing} totalMs={totalMs} fps={fps}
          selected={shot?.id} curFrame={curFrame} cursorMs={cursorMs}
          selLayerId={selLayerId}
          onSelect={(id) => { s.selectShot(id); setSelLayerId(null); }}
          onLayerTime={(layerId, patch) => {
            if (!shot) return;
            s.updateShot(shot.id, (x) => ({
              layers: (x.layers ?? []).map((y) => y.id === layerId ? {...y, ...patch} : y),
            } as any), true);
          }}
          onScrub={(ms) => {
            setCursorMs(Math.round(ms));
            const target = sb.shots.find((x: Shot) => ms >= x.time.start_ms && ms < x.time.end_ms);
            if (target) {
              if (target.id !== shot?.id) s.selectShot(target.id);
              // 等下一帧 selected 生效后 seek
              window.setTimeout(() => seekLocalMs(ms - target.time.start_ms), 30);
            }
          }}
          onSelectLayer={setSelLayerId}
          assets={s.stagedAssets ?? s.snap?.artifacts.manifest}
          onBoundaryDrag={(i, newLeftSegIds, newRightSegIds) => {
            s.setSbDraft((draft) => ({
              ...draft,
              shots: draft.shots.map((sh: Shot, idx: number) => {
                if (idx === i) return recomputeShotFromSegs({...sh, time: {...sh.time, seg_ids: newLeftSegIds}}, timing);
                if (idx === i + 1) return recomputeShotFromSegs({...sh, time: {...sh.time, seg_ids: newRightSegIds}}, timing);
                return sh;
              }),
            }), true);
          }}
        />
      </div>
      <div className="sb-right">
        <div className="rtabs">
          <button className={rightTab === 'props' ? 'on' : ''} onClick={() => setRightTab('props')}>镜头属性{shot ? ` · ${shot.id}` : ''}</button>
          <button className={rightTab === 'assets' ? 'on' : ''} onClick={() => setRightTab('assets')}>资产库</button>
        </div>
        {rightTab === 'props' ? (
          <ShotParams shot={shot} cursorMs={cursorMs} selLayerId={selLayerId} onSelectLayer={setSelLayerId}
                      onOpenPicker={(layer) => { setPickerLayer(layer); setPickerOpen(true); }} />
        ) : (
          <AssetPanel />
        )}
      </div>
      <EffectPicker open={pickerOpen} onClose={() => setPickerOpen(false)} shot={shot} defaultLayer={pickerLayer} />
      <LintFloating lint={lint} onLocate={(shotId) => {s.selectShot(shotId); playerRef.current?.seekTo(0);}}
                    onValidate={() => s.startRun('s3_check + card_lint + s3_table', async () => {
        await s.saveSb();
        const r1 = await api.tool(s.jobId!, 'card_lint');
        const r2 = await api.tool(s.jobId!, 's3_check');
        await api.tool(s.jobId!, 's3_table');
        return {run_id: r2.run_id || r1.run_id};
      })} />
    </div>
  );
}

function LintFloating({lint, onLocate, onValidate}: {lint: {level: string; shot?: string; msg: string}[]; onLocate: (shotId: string) => void; onValidate: () => void}) {
  const errs = lint.filter((l) => l.level === 'err');
  const warns = lint.filter((l) => l.level === 'warn');
  return (
    <div style={{position: 'absolute', left: 12, bottom: 150, zIndex: 30, width: 320}}>
      <div style={{background: 'var(--bg-panel)', border: '1px solid var(--hairline-strong)', borderRadius: 10, boxShadow: '0 8px 30px rgba(0,0,0,0.4)'}}>
        <div style={{display: 'flex', alignItems: 'center', gap: 6, padding: '7px 10px', borderBottom: '1px solid var(--hairline)'}}>
          <span style={{fontWeight: 700, fontSize: 12}}>自检</span>
          {errs.length > 0 && <span className="chip err">{errs.length} 错误</span>}
          {warns.length > 0 && <span className="chip warn">{warns.length} 提醒</span>}
          {errs.length + warns.length === 0 && <span className="chip ok">通过</span>}
          <div style={{flex: 1}} />
          <button className="small" onClick={onValidate} title="保存并跑服务端 s3_check + card_lint + 编排表">服务端校验</button>
        </div>
        {(errs.length > 0 || warns.length > 0) && (
          <div style={{maxHeight: 130, overflow: 'auto', padding: '6px 10px', fontSize: 11}}>
            {[...errs, ...warns].map((l, i) => (
              <div key={i} style={{cursor: l.shot ? 'pointer' : 'default'}}
                   title={l.shot ? '点击定位到该镜头' : undefined}
                   onClick={() => l.shot && onLocate(l.shot)}>
                {l.shot && <span className="mono acc">{l.shot} </span>}{l.msg}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ShotList({shots, selected, onSelect}: {shots: Shot[]; selected?: string; onSelect: (id: string) => void}) {
  return (
    <div className="sb-left">
      <div style={{padding: '9px 12px', fontSize: 11, letterSpacing: 1, color: 'var(--ink-faint)', fontWeight: 700, position: 'sticky', top: 0, background: 'var(--bg-panel)', borderBottom: '1px solid var(--hairline)', zIndex: 2}}>
        镜头 {shots.length}
      </div>
      {shots.map((sh) => (
        <div key={sh.id} className={`shot-item ${sh.id === selected ? 'on' : ''}`} onClick={() => onSelect(sh.id)}>
          <span className="sid">{sh.id.replace('S', '')}</span>
          <span className={`roll-dot ${sh.roll}`} />
          <div className="meta">
            <div className="recipe">{sh.recipe_ref}</div>
            <div className="vo">{sh.vo}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

function CanvasBox({data, shotId, playerRef, fps, curFrame, playing, onTogglePlay, onSeekLocal, extra, shotObj, selLayerId, onSelectLayer, onLayerPatch}: {
  data: any; shotId?: string; playerRef: React.RefObject<PlayerRef>; fps: number;
  curFrame: number; playing: boolean; onTogglePlay: () => void; onSeekLocal: (ms: number) => void;
  extra?: React.ReactNode; shotObj?: Shot; selLayerId: string | null;
  onSelectLayer: (id: string | null) => void; onLayerPatch: (id: string, patch: any, coalesce?: boolean) => void;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [box, setBox] = useState({w: 0, h: 0});
  const dragRef = useRef<{mode: 'move' | 'scale'; startX: number; startY: number; ox: number; oy: number; oscale: number; id: string} | null>(null);
  const cw = data.project.canvas.width;
  const chh = data.project.canvas.height;

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      const {width, height} = el.getBoundingClientRect();
      const ar = cw / chh;
      let w = width - 8;
      let h = w / ar;
      if (h > height - 8) {
        h = height - 8;
        w = h * ar;
      }
      setBox({w: Math.max(80, w), h: Math.max(80, h)});
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [cw, chh]);

  const shot = data.storyboard.shots.find((x: Shot) => x.id === shotId);
  const localMs = curFrame / fps * 1000;

  // 当前帧可见图层（与渲染端同判定）
  const visibleLayers = ((shotObj?.layers ?? []) as any[]).filter((l) =>
    l.enabled !== false && localMs >= (l.in_ms ?? 0) && (l.out_ms == null || localMs < l.out_ms));

  // ---- 剪映式 Gizmo：画布上拖动/缩放图层 ----
  const pxPerUnit = box.w; // x/y 是 0..1 画面比例 → 像素
  const startDrag = (e: React.PointerEvent, mode: 'move' | 'scale', L: any) => {
    e.stopPropagation();
    e.preventDefault();
    onSelectLayer(L.id);
    dragRef.current = {mode, startX: e.clientX, startY: e.clientY, ox: L.x ?? 0.5, oy: L.y ?? 0.5, oscale: L.scale ?? 1, id: L.id};
  };
  // 拖动期挂 window 监听：pointer capture 会把事件锁在目标元素上，挂窗最稳
  useEffect(() => {
    const move = (e: PointerEvent) => {
      const d = dragRef.current;
      if (!d || !box.w) return;
      if (d.mode === 'move') {
        const nx = d.ox + (e.clientX - d.startX) / pxPerUnit;
        const ny = d.oy + (e.clientY - d.startY) / box.h;
        onLayerPatch(d.id, {x: Math.min(1, Math.max(0, +nx.toFixed(3))), y: Math.min(1, Math.max(0, +ny.toFixed(3)))}, true);
      } else {
        const dist = ((e.clientX - d.startX) + (e.clientY - d.startY)) / 2;
        const ns = d.oscale * (1 + dist / (box.w * 0.35));
        onLayerPatch(d.id, {scale: +Math.min(2.5, Math.max(0.2, ns)).toFixed(3)}, true);
      }
    };
    const up = () => {
      if (dragRef.current) onSelectLayer(dragRef.current.id);
      dragRef.current = null;
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
    return () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
  });

  return (
    <>
      <div className="canvas-wrap" ref={wrapRef} onPointerDown={() => onSelectLayer(null)}>
        <div className="canvas-box" style={{width: box.w, height: box.h, position: 'relative'}}>
          {shotId && <StudioShotPlayer ref={playerRef} data={data} shotId={shotId} />}
          {/* 图层选择框/Gizmo：覆盖在 Player 之上 */}
          {visibleLayers.filter((l) => l.kind !== 'overlay').map((L) => {
            const on = L.id === selLayerId;
            const cx = (L.x ?? 0.5) * box.w;
            const cy = (L.y ?? 0.5) * box.h;
            const base = Math.min(box.w, box.h) * (L.scale ?? 1) * 0.5;
            const bw = Math.max(56, base * 1.1);
            const bh = Math.max(40, base * 0.62);
            return (
              <div key={L.id}
                   onPointerDown={(e) => startDrag(e, 'move', L)}
                   style={{
                     position: 'absolute', left: cx - bw / 2, top: cy - bh / 2, width: bw, height: bh,
                     border: on ? '2px solid var(--accent)' : '1.5px dashed rgba(255,255,255,0.45)',
                     borderRadius: 8, cursor: 'grab', zIndex: 40,
                     background: on ? 'rgba(255,75,31,0.06)' : 'transparent',
                   }}>
                {on && (
                  <>
                    <div title="拖动缩放"
                         onPointerDown={(e) => startDrag(e, 'scale', L)}
                         style={{position: 'absolute', right: -7, bottom: -7, width: 14, height: 14,
                                 borderRadius: '50%', background: 'var(--accent)', border: '2px solid #fff',
                                 cursor: 'nwse-resize'}} />
                    <div style={{position: 'absolute', left: 6, top: -20, fontSize: 10, color: '#fff',
                                 background: 'rgba(0,0,0,0.6)', borderRadius: 4, padding: '1px 6px', whiteSpace: 'nowrap'}}>
                      {L.label || L.ref || L.kind} · {(L.x ?? 0.5).toFixed(2)},{(L.y ?? 0.5).toFixed(2)} ×{(L.scale ?? 1).toFixed(2)}
                    </div>
                  </>
                )}
              </div>
            );
          })}
        </div>
      </div>
      <div className="transport">
        <button className="primary small" onClick={onTogglePlay}>{playing ? '⏸ 暂停' : '▶ 播放'}</button>
        <button className="small" onClick={() => playerRef.current?.seekTo(Math.max(0, curFrame - 1))}>◀帧</button>
        <button className="small" onClick={() => playerRef.current?.seekTo(curFrame + 1)}>帧▶</button>
        <span className="time">f{curFrame} · {fmtClock(localMs)} / {fmtClock(((shot?.time.end_ms ?? 0) - (shot?.time.start_ms ?? 0)))}</span>
        <div style={{flex: 1}} />
        <span className="chip mono">{shot?.id}</span>
        <span className="chip">{shot?.recipe_ref}</span>
        {(shot?.overlay?.length ?? 0) > 0 && <span className="chip">{shot?.overlay?.join(' + ')}</span>}
        {shot?.presentation && shot.presentation !== 'none' && <span className="chip">{shot.presentation}</span>}
        {(shot?.layers?.length ?? 0) > 0 && <span className="chip acc">图层 {shot?.layers?.length}</span>}
        <div style={{flex: 1}} />
        {extra}
      </div>
    </>
  );
}

const meta0Sfx = (s: any) => s.snap?.meta?.sfx?.[0] ?? 'click';

/** 图层类型 → 分类标签（镜头构成清单用） */
function layerTag(L: any): string {
  if (L.kind === 'card') return '内容卡';
  if (L.kind === 'overlay') return '特效';
  if (L.kind === 'text') return '字体';
  if (L.kind === 'media_video') return '素材·视频';
  if (L.kind === 'media_image') return '素材·图片';
  return '图层';
}

/** 游标检查器：任意秒的画面上下文 + 在此处执行的动作 */
function CursorInspector({ctx, cursorMs, fps, onPlay, onSplit, onAddSfx, onSwapEffect, onAddLayer}: {
  ctx: {cShot: Shot | null; seg: any; word: any; localMs: number; activeLayers: any[]; nearSfx: any[]} | null;
  cursorMs: number | null; fps: number;
  onPlay: () => void; onSplit: () => void; onAddSfx: () => void; onSwapEffect: () => void; onAddLayer: () => void;
}) {
  return (
    <div style={{display: 'flex', alignItems: 'center', gap: 8, padding: '6px 12px',
                 background: 'var(--bg-panel)', borderTop: '1px solid var(--hairline)', flexWrap: 'wrap', minHeight: 34}}>
      <span className="chip acc mono" title="光标（全局时间）">{cursorMs != null ? fmtClock(cursorMs) : '--:--'}</span>
      {ctx ? (
        <>
          <span className="chip">{ctx.cShot?.id ?? '（间隙）'}</span>
          {ctx.seg && (
            <span className="muted" style={{fontSize: 12, maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}
                  title={ctx.seg.text}>
              {ctx.seg.id}「{ctx.word ? <b style={{color: 'var(--accent)'}}>{ctx.word.text}</b> : ctx.seg.text.slice(0, 12)}…」
            </span>
          )}
          {ctx.activeLayers.length > 0 && <span className="chip">层: {ctx.activeLayers.map((l: any) => l.label || l.ref || l.kind).join(' / ')}</span>}
          {ctx.nearSfx.length > 0 && <span className="chip">♪ {ctx.nearSfx.map((c: any) => c.name).join(',')}</span>}
        </>
      ) : (
        <span className="faint" style={{fontSize: 12}}>点时间轴任意位置定位 → 此处显示那一秒的画面内容</span>
      )}
      <div style={{flex: 1}} />
      <button className="small" disabled={!ctx?.cShot} onClick={onPlay} title="选中所处镜头并从这里播放">⏵ 从此处播</button>
      <button className="small" disabled={ctx?.cShot !== undefined && !ctx?.cShot} onClick={onSplit} title="在光标处把镜头一分为二（重分组 seg_ids）">✂ 拆分</button>
      <button className="small" onClick={onAddSfx} title="在光标处加音效 cue">♪ 音效</button>
      <button className="small" onClick={onAddLayer} title="在选中镜头上加一个图层（可叠加）">➕ 图层</button>
      <button className="primary small" onClick={onSwapEffect} title="替换选中镜头的主画面效果">🎬 换效果</button>
    </div>
  );
}

function Timeline({shots, timing, totalMs, fps, selected, curFrame, cursorMs, selLayerId, onSelect, onScrub, onBoundaryDrag, onLayerTime, onSelectLayer, assets}: {
  shots: Shot[]; timing: any; totalMs: number; fps: number; selected?: string;
  curFrame: number; cursorMs: number | null; selLayerId: string | null;
  onSelect: (id: string) => void; onScrub: (ms: number) => void;
  onBoundaryDrag: (shotIdx: number, left: string[], right: string[]) => void;
  onLayerTime: (layerId: string, patch: {in_ms?: number; out_ms?: number | null}) => void;
  onSelectLayer: (id: string | null) => void;
  assets?: any;
}) {
  const trackRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{shotIdx: number; combined: any[]} | null>(null);
  const [actBoundary, setActBoundary] = useState<number | null>(null);
  const layerDragRef = useRef<{id: string; edge: 'in' | 'out' | 'move'; startX: number; in0: number; out0: number | null; shotStart: number} | null>(null);

  // 轨道行高（剪映式：主叙事 / 字幕 / 图层×N；素材归属到卡片/图层，不单独设轨）
  const ROW = {main: 40, sub: 20};
  const layersTop = ROW.main + ROW.sub + 4;
  const selectedShot = shots.find((x) => x.id === selected);
  const layerCount = Math.max(1, (selectedShot?.layers ?? []).length);
  const trackH = layersTop + layerCount * 10 + 6;

  const playheadMs = selectedShot ? selectedShot.time.start_ms + (curFrame / fps) * 1000 : 0;

  const msToPct = (ms: number) => `${(ms / Math.max(1, totalMs)) * 100}%`;
  const pxPerMs = () => (trackRef.current?.clientWidth ?? 1) / Math.max(1, totalMs);

  const startBoundaryDrag = (e: React.PointerEvent, i: number) => {
    e.stopPropagation();
    e.preventDefault();
    // 合并 shot i 与 i+1 的 segs（按 timing 顺序）
    const combined = [...shots[i].time.seg_ids, ...shots[i + 1].time.seg_ids]
      .map((sid: string) => timing.segments.find((t: any) => t.id === sid))
      .filter(Boolean)
      .sort((a: any, b: any) => a.start_ms - b.start_ms);
    if (combined.length < 2) return;
    dragRef.current = {shotIdx: i, combined};
    setActBoundary(i);
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  };

  const onMove = (e: React.PointerEvent) => {
    const d = dragRef.current;
    if (!d || !trackRef.current) return;
    const rect = trackRef.current.getBoundingClientRect();
    const ms = ((e.clientX - rect.left) / rect.width) * totalMs;
    // 找分割点：seg k 的 start ≥ ms 的最小 k（1..len-1），保证两侧都非空
    let k = d.combined.findIndex((t: any) => t.start_ms >= ms);
    if (k <= 0) k = 1;
    if (k > d.combined.length - 1) k = d.combined.length - 1;
    const left = d.combined.slice(0, k).map((t: any) => t.id);
    const right = d.combined.slice(k).map((t: any) => t.id);
    onBoundaryDrag(d.shotIdx, left, right);
  };

  // 图层时间窗拖动（剪映轨道语义：拖左缘=入点、右缘=出点、拖中部=整体平移）。
  // 拖动期挂 window（pointer capture 会把 move 锁在起点元素上，挂窗最稳）
  useEffect(() => {
    const move = (e: PointerEvent) => {
      const ld = layerDragRef.current;
      if (!ld || !trackRef.current) return;
      const rect = trackRef.current.getBoundingClientRect();
      const ms = ((e.clientX - rect.left) / rect.width) * totalMs - ld.shotStart;
      const deltaMs = ms - (ld.edge === 'in' ? ld.in0 : ld.edge === 'out' ? (ld.out0 ?? 0) : ld.in0);
      const shotDur = shots.find((x) => x.id === selected)?.time.end_ms ?? 0;
      if (ld.edge === 'in') {
        onLayerTime(ld.id, {in_ms: Math.max(0, Math.round(ld.in0 + deltaMs))});
      } else if (ld.edge === 'out') {
        const base = ld.out0 ?? (shotDur || 5000);
        onLayerTime(ld.id, {out_ms: Math.max(Math.round(ld.in0 + 200), Math.round(base + deltaMs))});
      } else {
        const span = (ld.out0 ?? 5000) - ld.in0;
        const nin = Math.max(0, Math.round(ld.in0 + deltaMs));
        onLayerTime(ld.id, {in_ms: nin, out_ms: nin + Math.max(200, Math.round(span))});
      }
    };
    const up = () => {
      layerDragRef.current = null;
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
    return () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
  });

  const endDrag = () => {
    dragRef.current = null;
    layerDragRef.current = null;
    setActBoundary(null);
  };

  const trackClick = (e: React.PointerEvent) => {
    if (dragRef.current || layerDragRef.current) return;
    const rect = trackRef.current!.getBoundingClientRect();
    onScrub(((e.clientX - rect.left) / rect.width) * totalMs);
  };

  return (
    <div className="tl">
      <div className="tl-body">
        {/* 轨道标签列 */}
        <div className="tl-labels">
          <span style={{height: ROW.main}}>主叙事</span>
          <span style={{height: ROW.sub}}>字幕</span>
          <span style={{height: layerCount * 10 + 6}}>图层</span>
        </div>
        <div className="tl-track" ref={trackRef}
             style={{height: trackH}}
             onPointerDown={trackClick}
             onPointerMove={onMove}
             onPointerUp={endDrag}
             onPointerLeave={endDrag}>
          {/* 轨1 主叙事：镜头块 */}
          {shots.map((sh, i) => (
            <div key={sh.id}
                 className={`tl-block ${sh.id === selected ? 'on' : ''}`}
                 style={{
                   left: msToPct(sh.time.start_ms),
                   width: msToPct(sh.time.end_ms - sh.time.start_ms),
                   top: 3, height: ROW.main - 8,
                   background: recipeColor(sh) + (sh.roll === 'A' ? 'CC' : '99'),
                 }}
                 onPointerDown={(e) => {
                   e.stopPropagation();
                   onSelect(sh.id);
                 }}>
              <div className="t">{sh.id} {sh.roll}</div>
              <div className="recipe">{sh.recipe_ref}</div>
            </div>
          ))}
          {/* 轨3 字幕：timing 段，点击定位 */}
          {timing.segments.map((t: any) => {
            // 一镜对应字幕 1:1：timing 固定不可改；重分组只改镜头的 seg_ids 划分
            const inSelected = selectedShot?.time.seg_ids?.includes(t.id);
            return (
              <div key={t.id} title={`${t.id} · ${t.text}${inSelected ? '（属于当前选中镜头）' : ''}`}
                   onPointerDown={(e) => {e.stopPropagation(); onScrub(t.start_ms + 10);}}
                   style={{
                     position: 'absolute', top: ROW.main + 3, height: ROW.sub - 6,
                     left: msToPct(t.start_ms), width: msToPct(t.end_ms - t.start_ms),
                     background: inSelected ? 'rgba(159,160,250,0.55)' : 'rgba(159,160,250,0.14)',
                     border: `1px solid ${inSelected ? 'rgba(159,160,250,0.95)' : 'rgba(159,160,250,0.3)'}`,
                     borderRadius: 3, fontSize: 9, lineHeight: '12px',
                     color: inSelected ? '#E6E6FF' : 'var(--ink-faint)',
                     paddingLeft: 3, overflow: 'hidden', whiteSpace: 'nowrap', cursor: 'pointer', zIndex: 2,
                   }}>
              {t.text}
              </div>
            );
          })}
          {/* 镜头间边界（重新分组 seg_ids） */}
          {shots.slice(0, -1).map((sh, i) => (
            <div key={`b${i}`} className={`tl-boundary ${actBoundary === i ? 'act' : ''}`}
                 style={{left: msToPct(shots[i].time.end_ms), top: 0, bottom: 0}}
                 title="拖动重新分组（timing 段在相邻镜头间移动）"
                 onPointerDown={(e) => startBoundaryDrag(e, i)} />
          ))}
          {/* 轨4 图层：选中镜的每层一条时间窗（拖缘/平移） */}
          {selectedShot && ((selectedShot.layers ?? []) as any[]).map((L, li) => {
            const shotDur = selectedShot.time.end_ms - selectedShot.time.start_ms;
            const inMs = L.in_ms ?? 0;
            const outMs = L.out_ms ?? shotDur;
            const on = L.id === selLayerId;
            const top = layersTop + li * 10;
            return (
              <div key={L.id} title={`${L.label || L.ref || L.kind}（拖边缘改时间窗，拖中间平移）`}
                   onPointerDown={(e) => {
                     e.stopPropagation();
                     const rect = trackRef.current!.getBoundingClientRect();
                     const px = e.clientX - rect.left;
                     const el = e.currentTarget as HTMLElement;
                     const edgeW = Math.max(4, Math.min(10, el.clientWidth / 4));
                     const edge = px - el.getBoundingClientRect().left < edgeW ? 'in'
                       : el.getBoundingClientRect().right - px < edgeW ? 'out' : 'move';
                     layerDragRef.current = {id: L.id, edge, startX: e.clientX, in0: inMs, out0: L.out_ms ?? null, shotStart: selectedShot.time.start_ms};
                     onSelectLayer(L.id);
                   }}
                   style={{
                     position: 'absolute', zIndex: 5, top, height: 8, borderRadius: 4,
                     left: msToPct(selectedShot.time.start_ms + inMs),
                     width: `calc(${(outMs - inMs) / Math.max(1, totalMs) * 100}% )`,
                     background: L.kind === 'overlay' ? 'rgba(159,160,250,0.85)' : 'rgba(243,167,18,0.9)',
                     outline: on ? '2px solid var(--accent)' : 'none',
                     cursor: 'ew-resize', fontSize: 8, color: 'rgba(0,0,0,0.75)',
                     overflow: 'hidden', whiteSpace: 'nowrap', paddingLeft: 4, lineHeight: '8px',
                   }}>
                {L.label || L.ref || L.kind}
              </div>
            );
          })}
          <div className="tl-playhead" style={{left: msToPct(playheadMs)}} />
          {cursorMs != null && (
            <div title="游标（全局定位）"
                 style={{position: 'absolute', top: 0, bottom: 0, width: 0,
                         borderLeft: '2px dashed var(--warn)', left: msToPct(cursorMs), zIndex: 4, pointerEvents: 'none', opacity: 0.8}} />
          )}
        </div>
      </div>
      <div className="tl-legend">
        <span className="k"><span className="roll-dot A" />A-roll（IP 出镜）</span>
        <span className="k"><span className="roll-dot B" style={{background: B_ROLL_COLOR}} />B-roll（图卡/素材）</span>
        <span className="k"><span className="roll-dot" style={{background: CARD_COLOR}} />移植卡</span>
        <span className="k faint">主叙事=内容卡 · 字幕=timing 段（点击定位） · 橙条=图层时间窗</span>
        <div style={{flex: 1}} />
        <span className="mono faint">总长 {fmtClock(totalMs)}</span>
      </div>
    </div>
  );
}

function ShotParams({shot, cursorMs, onOpenPicker, selLayerId, onSelectLayer}: {
  shot?: Shot; cursorMs: number | null; onOpenPicker: (layer: boolean) => void;
  selLayerId: string | null; onSelectLayer: (id: string | null) => void;
}) {
  const s = useStore();
  const meta = s.snap!.meta;
  const [sfxPreview, setSfxPreview] = useState<string | null>(null);
  const [assetTab, setAssetTab] = useState<'cards' | 'media'>('cards');
  const [mediaBusy, setMediaBusy] = useState<string | null>(null);
  const [stockKw, setStockKw] = useState('');
  const [capUrl, setCapUrl] = useState('');
  const selLayer = selLayerId;
  const setSelLayer = onSelectLayer;
  const recipeGroups = useMemo(() => ({
    local: meta.shot_components.map((n) => ({label: n, value: n})),
    special: [{label: 'RealFootage（B-roll 视频）', value: 'RealFootage'}],
    card: Object.values(meta.cards).filter((c) => c.tier === 'injectable').map((c) => ({label: `card:${c.slug} · ${c.desc.slice(0, 18)}`, value: `card:${c.slug}`})),
  }), [meta]);
  if (!shot) return <div className="sb-right-scroll"><div className="empty">选择一个镜头</div></div>;

  const entry = shot.recipe_ref?.startsWith('card:') ? CARD_REGISTRY[shot.recipe_ref.slice(5)] : undefined;
  const u = (patch: Partial<Shot> | ((x: Shot) => Partial<Shot>), coalesce = false) => s.updateShot(shot.id, patch, coalesce);
  const setCfg = (patch: Record<string, unknown>, coalesce = false) =>
    u((x) => ({config: {...(x.config ?? {}), ...patch}}), coalesce);

  const previewSfx = (name: string) => {
    setSfxPreview(name);
    const a = new Audio(`/sfx/${name}.mp3`);
    a.play().catch(() => undefined);
    a.onended = () => setSfxPreview(null);
  };

  const layers = (shot.layers ?? []) as any[];
  const cardLayers = layers.filter((L) => L.kind === 'card');
  const textLayers = layers.filter((L) => L.kind === 'text');
  const mediaLayers = layers.filter((L) => L.kind === 'media_image' || L.kind === 'media_video');

  const isMainSelected = !selLayerId || !layers.some((L) => L.id === selLayerId);
  const selCardLayer = layers.find((L) => L.id === selLayerId && L.kind === 'card');
  const selTextLayer = layers.find((L) => L.id === selLayerId && L.kind === 'text');
  const selMediaLayer = layers.find((L) => L.id === selLayerId && (L.kind === 'media_image' || L.kind === 'media_video'));

  const addMediaLayer = async (kind: 'media_image' | 'media_video', file: File) => {
    setMediaBusy(kind);
    try {
      const r = await api.uploadLayerMedia(s.jobId!, file.name, file);
      const id = `L${layers.length + 1}-${Math.random().toString(36).slice(2, 5)}`;
      s.updateShot(shot.id, (x) => ({layers: [...(x.layers ?? []), {
        id, kind, ref: r.path, label: file.name, enabled: true,
        presentation: 'rise_fade', x: 0.72, y: 0.62, opacity: 1,
      } as any]} as any));
      setSelLayer(id);
      setAssetTab('media');
      s.notify('ok', `素材已贴入 ${shot.id}（${kind === 'media_video' ? '视频' : '图片'}图层）`);
    } catch (e: any) {
      s.notify('err', `上传失败: ${e.message}`);
    } finally {
      setMediaBusy(null);
    }
  };

  const shotDur = shot.time.end_ms - shot.time.start_ms;

  // 通用图层属性块（时间窗/位置/透明度/入场）
  const layerCommon = (L: any) => {
    const setL = (patch: any) => u((x) => ({layers: (x.layers ?? []).map((y) => y.id === L.id ? {...y, ...patch} : y)}), true);
    return (
      <>
        <Row label="时间窗" help="镜头内相对时刻">
          <div style={{display: 'flex', gap: 5, alignItems: 'center'}}>
            <input type="number" step={100} value={L.in_ms ?? 0} onChange={(e) => setL({in_ms: parseFloat(e.target.value) || 0})} style={{width: 74}} />
            <span className="faint">→</span>
            <input type="number" step={100} value={L.out_ms ?? ''} placeholder="末尾"
                   onChange={(e) => setL({out_ms: e.target.value === '' ? null : parseFloat(e.target.value)})} style={{width: 74}} />
            <span className="faint" style={{fontSize: 11}}>/ {shotDur}ms</span>
          </div>
        </Row>
        <Row label="位置">
          <div style={{display: 'flex', gap: 5, alignItems: 'center'}}>
            <span className="faint" style={{fontSize: 11}}>x</span>
            <input type="range" min={0} max={1} step={0.01} value={L.x ?? 0.5} onChange={(e) => setL({x: parseFloat(e.target.value)})} style={{width: 64}} />
            <span className="faint" style={{fontSize: 11}}>y</span>
            <input type="range" min={0} max={1} step={0.01} value={L.y ?? 0.5} onChange={(e) => setL({y: parseFloat(e.target.value)})} style={{width: 64}} />
            <span className="faint" style={{fontSize: 11}}>缩放</span>
            <input type="range" min={0.2} max={2} step={0.05} value={L.scale ?? 1} onChange={(e) => setL({scale: parseFloat(e.target.value)})} style={{width: 64}} />
            <span className="mono" style={{fontSize: 10, width: 60, textAlign: 'right'}}>{(L.x ?? 0.5).toFixed(2)},{(L.y ?? 0.5).toFixed(2)}×{(L.scale ?? 1).toFixed(2)}</span>
          </div>
        </Row>
        <Row label="透明度">
          <div style={{display: 'flex', gap: 5, alignItems: 'center'}}>
            <input type="range" min={0.05} max={1} step={0.05} value={L.opacity ?? 1}
                   onChange={(e) => setL({opacity: parseFloat(e.target.value)})} style={{flex: 1}} />
            <span className="mono" style={{fontSize: 10, width: 30, textAlign: 'right'}}>{Math.round((L.opacity ?? 1) * 100)}%</span>
          </div>
        </Row>
        <Row label="入场">
          <select value={L.presentation ?? 'none'} onChange={(e) => setL({presentation: e.target.value})} style={{width: '100%'}}>
            {['none', 'rise_fade', 'slam_in', 'blur_focus'].map((pp) => <option key={pp} value={pp}>{pp}</option>)}
          </select>
        </Row>
        <Row label="出场" help="设了时间窗终点后的退场方式">
          <select value={L.exit ?? 'fade'} onChange={(e) => setL({exit: e.target.value})} style={{width: '100%'}}>
            <option value="fade">淡出（末 8 帧）</option>
            <option value="none">硬切</option>
          </select>
        </Row>
        <Row label="删除">
          <button className="danger small" onClick={() => {
            u((x) => ({layers: (x.layers ?? []).filter((y) => y.id !== L.id)}));
            setSelLayer(null);
          }}>🗑 删除此层</button>
        </Row>
      </>
    );
  };

  return (
    <div className="sb-right-scroll">
      {/* 子页签：资产卡 / 素材（左右切换） */}
      <div className="rtabs">
        <button className={assetTab === 'cards' ? 'on' : ''} onClick={() => setAssetTab('cards')}>
          资产卡（{1 + cardLayers.length + textLayers.length}）
        </button>
        <button className={assetTab === 'media' ? 'on' : ''} onClick={() => setAssetTab('media')}>
          素材（{mediaLayers.length}）
        </button>
      </div>

      {assetTab === 'cards' && (
        <>
          <Section title="这个镜头的画面卡" extra={
            <button className="small" onClick={() => onOpenPicker(true)}>＋ 加卡</button>
          }>
            <Row label="主卡">
              <button className="small" style={{width: '100%', textAlign: 'left', justifyContent: 'flex-start',
                       background: isMainSelected ? 'var(--accent-soft)' : undefined, borderColor: isMainSelected ? 'var(--accent)' : undefined}}
                      onClick={() => setSelLayer(null)}>
                <span className="chip acc" style={{marginRight: 6}}>主</span>{shot.recipe_ref}
              </button>
            </Row>
            {cardLayers.map((L) => (
              <Row key={L.id} label="叠加">
                <div style={{display: 'flex', gap: 4, alignItems: 'center', width: '100%'}}>
                  <button className="small" style={{flex: 1, textAlign: 'left', justifyContent: 'flex-start',
                           background: L.id === selLayerId ? 'var(--accent-soft)' : undefined, borderColor: L.id === selLayerId ? 'var(--accent)' : undefined}}
                          onClick={() => setSelLayer(L.id)}>
                    {L.label || L.ref}
                  </button>
                  <button className="ghost small" title={L.enabled === false ? '已隐藏（点此显示）' : '显示中（点此隐藏预览）'}
                          onClick={() => u((x) => ({layers: (x.layers ?? []).map((y) => y.id === L.id ? {...y, enabled: y.enabled === false} : y)}))}>
                    {L.enabled === false ? '🚫' : '👁'}
                  </button>
                  <button className="ghost small" title="删除" onClick={() => {
                    u((x) => ({layers: (x.layers ?? []).filter((y) => y.id !== L.id)}));
                    if (selLayerId === L.id) setSelLayer(null);
                  }}>🗑</button>
                </div>
              </Row>
            ))}
            {textLayers.map((L) => (
              <Row key={L.id} label="文字">
                <div style={{display: 'flex', gap: 4, alignItems: 'center', width: '100%'}}>
                  <button className="small" style={{flex: 1, textAlign: 'left', justifyContent: 'flex-start',
                           background: L.id === selLayerId ? 'var(--accent-soft)' : undefined, borderColor: L.id === selLayerId ? 'var(--accent)' : undefined}}
                          onClick={() => setSelLayer(L.id)}>
                    {L.config?.text || '（文字层）'}
                  </button>
                  <button className="ghost small" title={L.enabled === false ? '已隐藏（点此显示）' : '显示中（点此隐藏预览）'}
                          onClick={() => u((x) => ({layers: (x.layers ?? []).map((y) => y.id === L.id ? {...y, enabled: y.enabled === false} : y)}))}>
                    {L.enabled === false ? '🚫' : '👁'}
                  </button>
                  <button className="ghost small" title="删除" onClick={() => {
                    u((x) => ({layers: (x.layers ?? []).filter((y) => y.id !== L.id)}));
                    if (selLayerId === L.id) setSelLayer(null);
                  }}>🗑</button>
                </div>
              </Row>
            ))}
            <div className="faint" style={{fontSize: 11, marginTop: 2}}>点选一张卡 → 下方只编辑这一张的文字，其他效果不动。</div>
          </Section>

          <Section title="编辑所选">
            {isMainSelected && (
              <>
                <Row label="画面配方">
                  <select value={shot.recipe_ref} onChange={(e) => u({recipe_ref: e.target.value})} style={{width: '100%'}}>
                    <optgroup label="自研组件">
                      {recipeGroups.local.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </optgroup>
                    <optgroup label="特殊">
                      {recipeGroups.special.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </optgroup>
                    <optgroup label={`移植卡（${recipeGroups.card.length}）`}>
                      {recipeGroups.card.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </optgroup>
                  </select>
                </Row>
                {entry && (
                  <div className="muted" style={{fontSize: 11, lineHeight: 1.5, margin: '4px 0 6px'}}>
                    {entry.desc.slice(0, 60)}
                  </div>
                )}
                {entry && (
                  <Row label="自动填词">
                    <button className="small" onClick={() => {
                      const cfg: Record<string, unknown> = {};
                      for (const [key, n] of Object.entries(entry.arities ?? {})) {
                        if (typeof n === 'number' && n > 0) cfg[key] = deriveTexts({vo: shot.vo, intent: shot.intent}, n);
                      }
                      setCfg(cfg);
                    }}>从口播派生全部槽位</button>
                  </Row>
                )}
                {entry && Object.entries(entry.arities ?? {}).filter(([, n]) => (n as number) > 0).map(([key, n]) => (
                  <Row key={key} label={`${key}（${n}）`} help="留空则从口播自动派生">
                    <TextListField value={(shot.config?.[key] as string[]) ?? []} max={n as number}
                                   onChange={(v) => setCfg({[key]: v}, true)} />
                  </Row>
                ))}
                {!entry && (
                  <Row label="TEXT">
                    <TextListField value={(shot.config?.TEXT as string[]) ?? []} onChange={(v) => setCfg({TEXT: v}, true)} />
                  </Row>
                )}
                <Row label="CONFIG">
                  <JsonField value={shot.config?.CONFIG ?? null} rows={4} onChange={(v) => setCfg({CONFIG: v ?? undefined})} />
                </Row>
                <Row label="素材绑定" help="主卡当前绑定的素材，可上传替换">
                  <div style={{display: 'flex', gap: 5, flexWrap: 'wrap'}}>
                    {(s.stagedAssets?.screenshots?.[shot.id]) && <span className="chip ok">截图已绑定</span>}
                    {(s.stagedAssets?.broll_videos?.[shot.id]) && <span className="chip ok">视频已绑定</span>}
                    {(shot.roll === 'A') && <span className="chip acc">IP 形象</span>}
                    <label style={{cursor: 'pointer'}}>
                      <span className="chip acc" style={{cursor: 'pointer'}}>⬆ 替换图片</span>
                      <input type="file" style={{display: 'none'}}
                             onChange={(e) => {
                               const file = e.target.files?.[0];
                               if (!file) return;
                               api.uploadAsset(s.jobId!, shot.id, 'screenshot', file.name, file).then(() => {
                                 s.reloadStaged();
                                 s.notify('ok', '主卡素材已替换');
                               }).catch((er) => s.notify('err', er.message));
                             }} />
                    </label>
                  </div>
                </Row>
              </>
            )}

            {selCardLayer && (() => {
              const L = selCardLayer;
              const lEntry = CARD_REGISTRY[L.ref ?? ''];
              const keys = Object.entries(lEntry?.arities ?? {}).filter(([, n]) => (n as number) > 0);
              return (
                <>
                  {keys.length > 0 ? keys.map(([key, n]) => (
                    <Row key={key} label={`${key}（${n}）`} help="留空则从口播自动派生">
                      <TextListField value={(L.config?.[key] as string[]) ?? []} max={n as number}
                                     onChange={(v) => u((x) => ({layers: (x.layers ?? []).map((y) => y.id === L.id ? {...y, config: {...L.config, [key]: v}} : y)}), true)} />
                    </Row>
                  )) : (
                    <div className="faint" style={{fontSize: 11, marginBottom: 4}}>纯动效卡（无文字槽位）。要配你的内容：</div>
                  )}
              {(lEntry as any)?.images?.length > 0 && (lEntry as any).images.map((imgKey: string, gi: number) => (
                    <Row key={imgKey} label={`图片 ${gi + 1}`} help="替换卡内配图">
                      <div style={{display: 'flex', gap: 4, alignItems: 'center'}}>
                        <span className="chip" style={{fontSize: 10}}>
                          {L.config?.CONFIG?.[imgKey] ? '已替换 ✓' : '默认图'}
                        </span>
                        <label style={{cursor: 'pointer'}}>
                          <span className="chip acc" style={{cursor: 'pointer', fontSize: 10}}>⬆ 上传替换</span>
                          <input type="file" accept="image/*" style={{display: 'none'}}
                                 onChange={(e) => {
                                   const file = e.target.files?.[0];
                                   if (!file) return;
                                   api.uploadLayerMedia(s.jobId!, file.name, file).then((r) => {
                                     u((x) => ({layers: (x.layers ?? []).map((y) => y.id === L.id ? {...y, config: {...L.config, CONFIG: {...(L.config?.CONFIG ?? {}), [imgKey]: r.path}}} : y)}));
                                     s.notify('ok', `图片 ${gi + 1} 已替换`);
                                   }).catch((er) => s.notify('err', er.message));
                                 }} />
                        </label>
                      </div>
                    </Row>
              ))}
                </>
              );
            })()}

            {selTextLayer && (() => {
              const L = selTextLayer;
              const setL = (patch: any) => u((x) => ({layers: (x.layers ?? []).map((y) => y.id === L.id ? {...y, ...patch} : y)}), true);
              return (
                <>
                  <Row label="文字"><input value={L.config?.text ?? ''} onChange={(e) => setL({config: {...L.config, text: e.target.value}})} style={{width: '100%'}} /></Row>
                  <Row label="字体">
                    <select value={L.config?.font ?? 'sans'} onChange={(e) => setL({config: {...L.config, font: e.target.value}})} style={{width: '100%'}}>
                      <option value="sans">黑体（默认）</option>
                      <option value="serif">宋体 · 衬线</option>
                      <option value="mono">等宽 · 代码感</option>
                    </select>
                  </Row>
                  <Row label="字号/颜色">
                    <div style={{display: 'flex', gap: 5}}>
                      <input type="number" value={L.config?.size ?? 64} onChange={(e) => setL({config: {...L.config, size: parseFloat(e.target.value) || 64}})} style={{width: 70}} />
                      <input type="color" value={/^#[0-9a-fA-F]{6}$/.test(L.config?.color ?? '') ? L.config.color : '#ffffff'}
                             onChange={(e) => setL({config: {...L.config, color: e.target.value}})} style={{width: 38, height: 26, padding: 1}} />
                    </div>
                  </Row>
                </>
              );
            })()}

            {(selCardLayer || selTextLayer) && layerCommon(selCardLayer ?? selTextLayer)}
          </Section>
        </>
      )}

      {assetTab === 'media' && (
        <>
          <Section title="分步生成（不用出门找素材）">
            <Row label="生成图片" help="① 按口播写任务单(JSON) → ② 本地 ComfyUI 出图 → 自动贴入">
              <button className="small" style={{width: '100%'}} disabled={mediaBusy === 'gen'}
                      onClick={() => {
                        setMediaBusy('gen');
                        api.applyEffect(s.jobId!, {effect: 'gen_image', shot_id: shot.id, adapter: 'hand-drawn-styles'})
                          .then((r) => {
                            if (!r.run_id) { setMediaBusy(null); s.notify('ok', '任务单已写入'); return; }
                            const poll = window.setInterval(() => {
                              api.runDetail(r.run_id!).then((d) => {
                                if (d.status !== 'running') {
                                  window.clearInterval(poll); setMediaBusy(null);
                                  s.reloadStaged();
                                  s.notify(d.status === 'done' ? 'ok' : 'err', d.status === 'done' ? '图片已生成并贴入' : '生图失败（需 ComfyUI 8188）');
                                }
                              }).catch(() => window.clearInterval(poll));
                            }, 2000);
                          }).catch((e) => { setMediaBusy(null); s.notify('err', e.message); });
                      }}>
                        {mediaBusy === 'gen' ? '①任务单 ✓ ②生图中…' : '⚡ 生成图片（2 步）'}
                      </button>
            </Row>
            <Row label="搜索视频" help="给英文关键词，Pexels/Pixabay 免费图库检索下载">
              <div style={{display: 'flex', gap: 4}}>
                <input value={stockKw} onChange={(e) => setStockKw(e.target.value)} placeholder="如 city night"
                       style={{flex: 1, minWidth: 0}} />
                <button className="small" disabled={!stockKw.trim()}
                        onClick={() => api.applyEffect(s.jobId!, {effect: 'stock', shot_id: shot.id,
                          keywords: stockKw.split(/[,，]/).map((x) => x.trim()).filter(Boolean)}).then(() => s.notify('ok', '搜索下载中')).catch((e) => s.notify('err', e.message))}>
                  搜索
                </button>
              </div>
            </Row>
            <Row label="录屏网页" help="Playwright 打开网页自动录一段">
              <div style={{display: 'flex', gap: 4}}>
                <input value={capUrl} onChange={(e) => setCapUrl(e.target.value)} placeholder="https://网址" style={{flex: 1, minWidth: 0}} />
                <button className="small" disabled={!capUrl.trim()}
                        onClick={() => api.applyEffect(s.jobId!, {effect: 'capture', shot_id: shot.id, url: capUrl, mode: 'record', seconds: 8})
                          .then(() => s.notify('ok', '录制中（8 秒）')).catch((e) => s.notify('err', e.message))}>
                  录制
                </button>
              </div>
            </Row>
          </Section>

          <Section title="素材层" extra={
            <span style={{display: 'flex', gap: 4}}>
              <label style={{cursor: 'pointer'}}>
                <span className="chip acc" style={{cursor: 'pointer'}}>＋图片</span>
                <input type="file" accept="image/*" style={{display: 'none'}}
                       onChange={(e) => e.target.files?.[0] && addMediaLayer('media_image', e.target.files[0])} />
              </label>
              <label style={{cursor: 'pointer'}}>
                <span className="chip acc" style={{cursor: 'pointer'}}>＋视频</span>
                <input type="file" accept="video/*" style={{display: 'none'}}
                       onChange={(e) => e.target.files?.[0] && addMediaLayer('media_video', e.target.files[0])} />
              </label>
            </span>
          }>
            {mediaBusy && <div className="chip acc" style={{marginBottom: 6}}><span className="spin" /> 上传中…</div>}
            {mediaLayers.map((L) => (
              <Row key={L.id} label={L.kind === 'media_video' ? '视频' : '图片'}>
                <div style={{display: 'flex', gap: 4, alignItems: 'center', width: '100%'}}>
                  <button className="small" style={{flex: 1, textAlign: 'left', justifyContent: 'flex-start',
                           background: L.id === selLayerId ? 'var(--accent-soft)' : undefined, borderColor: L.id === selLayerId ? 'var(--accent)' : undefined}}
                          onClick={() => setSelLayer(L.id)}>
                    {L.label || L.ref}
                  </button>
                  <button className="ghost small" title={L.enabled === false ? '已隐藏（点此显示）' : '显示中（点此隐藏预览）'}
                          onClick={() => u((x) => ({layers: (x.layers ?? []).map((y) => y.id === L.id ? {...y, enabled: y.enabled === false} : y)}))}>
                    {L.enabled === false ? '🚫' : '👁'}
                  </button>
                  <button className="ghost small" title="删除" onClick={() => {
                    u((x) => ({layers: (x.layers ?? []).filter((y) => y.id !== L.id)}));
                    if (selLayerId === L.id) setSelLayer(null);
                  }}>🗑</button>
                </div>
              </Row>
            ))}
            {mediaLayers.length === 0 && <div className="faint" style={{fontSize: 11}}>还没有素材。点右上 ＋图片/＋视频 上传 → 作为一层贴入本镜。</div>}
          </Section>

          {selMediaLayer && (() => {
            const L = selMediaLayer;
            const setL = (patch: any) => u((x) => ({layers: (x.layers ?? []).map((y) => y.id === L.id ? {...y, ...patch} : y)}), true);
            return (
              <Section title="编辑所选素材">
                <Row label="素材替换">
                  <label style={{cursor: 'pointer'}}>
                    <span className="chip acc" style={{cursor: 'pointer'}}>⬆ 上传替换</span>
                    <input type="file" style={{display: 'none'}}
                           accept={L.kind === 'media_video' ? 'video/*' : 'image/*'}
                           onChange={(e) => {
                             const file = e.target.files?.[0];
                             if (!file) return;
                             api.uploadLayerMedia(s.jobId!, file.name, file).then((r) => {
                               setL({ref: r.path});
                               s.notify('ok', '素材已替换：' + r.path);
                             }).catch((er) => s.notify('err', er.message));
                           }} />
                  </label>
                </Row>
                <Row label="动态" help="跨整段时间窗的镜头运动">
                  <select value={L.motion ?? 'none'} onChange={(e) => setL({motion: e.target.value})} style={{width: '100%'}}>
                    <option value="none">静止</option>
                    <option value="corner_takeover">全屏 → 缩到右上角</option>
                    <option value="grow_takeover">小 → 突然占满全屏</option>
                    <option value="kenburns_in">缓推近</option>
                    <option value="kenburns_out">缓拉远</option>
                  </select>
                </Row>
                {layerCommon(L)}
              </Section>
            );
          })()}
        </>
      )}

      {/* 更多设置（低频，全部折叠） */}
      <details style={{padding: '8px 14px 16px'}}>
        <summary style={{cursor: 'pointer', fontSize: 12, color: 'var(--ink-muted)', userSelect: 'none'}}>
          更多设置（主画面入场 / 氛围 / 音效 / 设计备注 / 口播 / 元信息）
        </summary>
        <Section title="主题（全局配色，直接进画面）">
          <Row label="配色" help="bg=底色 text=文字色 anchor=强调色，写进 project.json 后整片统一换色">
            <select value={s.projDraft?.style?.theme ?? ''}
                    onChange={(e) => {
                      const t = s.snap!.meta.themes.find((x) => x.id === e.target.value);
                      if (!t || !s.projDraft) return;
                      s.setProjDraft((pr) => ({...pr, style: {...pr.style, theme: t.id,
                        b_roll: {...pr.style.b_roll, palette: {bg: t.bg, anchor: t.anchor, text: t.text}}}}));
                      s.saveProj();
                      s.notify('ok', `主题已切 ${t.id}（整片配色，重渲后生效）`);
                    }} style={{width: '100%'}}>
              <option value="">选择主题…</option>
              {s.snap!.meta.themes.map((t) => <option key={t.id} value={t.id}>{t.id} · {t.description?.slice(0, 14) ?? ''}</option>)}
            </select>
          </Row>
        </Section>
        <Section title="主画面表达">
          <Row label="入场">
            <select value={shot.presentation ?? 'none'} onChange={(e) => u({presentation: e.target.value})} style={{width: '100%'}}>
              {meta.presentations.map((pp) => <option key={pp} value={pp}>{pp}</option>)}
            </select>
          </Row>
          <Row label="氛围层" help="最多 2 层。更多 → 用素材/卡片图层">
            <MultiCapsule options={meta.overlays} value={shot.overlay ?? []} max={2}
                          onChange={(v) => u({overlay: v}, true)} />
          </Row>
        </Section>
        <Section title={`音效 ${shot.sfx?.length ?? 0}`}>
          {(shot.sfx ?? []).map((c, i) => (
            <div key={i} style={{display: 'flex', gap: 4, marginBottom: 5, alignItems: 'center'}}>
              <input type="number" value={c.t_ms} onChange={(e) => u((x) => ({sfx: (x.sfx ?? []).map((y, j) => j === i ? {...y, t_ms: parseFloat(e.target.value) || 0} : y)}), true)}
                     style={{width: 64}} title="镜头内相对时刻 ms" />
              <select value={c.name} onChange={(e) => u((x) => ({sfx: (x.sfx ?? []).map((y, j) => j === i ? {...y, name: e.target.value} : y)}))}
                      style={{flex: 1}}>
                {meta.sfx.map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
              <button className="ghost small" onClick={() => previewSfx(c.name)} title="试听">{sfxPreview === c.name ? '♪' : '▷'}</button>
              <button className="ghost small" onClick={() => u((x) => ({sfx: (x.sfx ?? []).filter((_, j) => j !== i)}))}>✕</button>
            </div>
          ))}
          <button className="small" onClick={() => u((x) => ({sfx: [...(x.sfx ?? []), {t_ms: 0, name: meta.sfx[0] ?? 'click', gain: 1}]}))}>
            ＋ 加音效 cue
          </button>
        </Section>
        <Section title="设计备注">
          <Row label="intent"><input value={shot.intent ?? ''} onChange={(e) => u({intent: e.target.value}, true)} style={{width: '100%'}} /></Row>
          <Row label="visual"><input value={shot.visual ?? ''} onChange={(e) => u({visual: e.target.value}, true)} style={{width: '100%'}} /></Row>
          <Row label="motion">
            <textarea rows={3} value={(shot.motion ?? []).join('\n')} onChange={(e) => u({motion: e.target.value.split('\n').filter((x) => x !== '')}, true)} style={{width: '100%'}} />
          </Row>
        </Section>
        <Section title="口播（来自 timing，只读）">
          <div style={{background: 'var(--fill-subtle)', borderRadius: 8, padding: '8px 10px', fontSize: 12.5, lineHeight: 1.7}}>
            {shot.vo || <span className="faint">（无）</span>}
          </div>
          <div className="faint mono" style={{fontSize: 11, marginTop: 6}}>
            {fmtClock(shot.time.start_ms)} → {fmtClock(shot.time.end_ms)} · seg_ids: {(shot.time.seg_ids ?? []).join(',')}
          </div>
        </Section>
        <Section title="镜头元信息">
          <Row label="roll" help="A=IP出镜，B=内容卡。配方决定，一般不改">
            <div style={{display: 'flex', gap: 5}}>
              {(['A', 'B'] as const).map((r) => (
                <button key={r} className="small" onClick={() => u({roll: r})}
                        style={shot.roll === r ? {background: r === 'A' ? A_ROLL_COLOR : B_ROLL_COLOR, borderColor: 'transparent', color: '#fff', fontWeight: 700} : undefined}>
                  {r}-roll
                </button>
              ))}
            </div>
          </Row>
          <Row label="视角">
            <select value={shot.view_angle ?? ''} onChange={(e) => u({view_angle: (e.target.value || null) as any})} style={{width: '100%'}}>
              <option value="">（无）</option>
              {meta.view_angles.map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
          </Row>
          <Row label="转场">
            <select value={shot.transition_in ?? 'cut'} onChange={(e) => u({transition_in: e.target.value})} style={{width: '100%'}}>
              <option value="cut">cut</option>
              {meta.transitions.filter((t) => t !== 'cut').map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
          </Row>
          <Row label="相机">
            <select value={shot.camera?.dir ?? 'auto'} onChange={(e) => u({camera: {dir: e.target.value as any}})} style={{width: '100%'}}>
              <option value="auto">自动</option>
              <option value="in">in（推近）</option>
              <option value="out">out（拉远）</option>
            </select>
          </Row>
          <Row label="状态">
            <select value={shot.status ?? 'pending'} onChange={(e) => u({status: e.target.value})} style={{width: '100%'}}>
              {['pending', 'asset_ok', 'rendered', 'qa_pass', 'rejected'].map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
          </Row>
        </Section>
      </details>
    </div>
  );
}
