/** S4 素材视图：manifest 浏览 + 生图任务单 + 工具执行 + 上传替换 */
import React, {useEffect, useRef, useState} from 'react';
import {useStore} from '../store';
import {api, type ImageBrief, type StockSearch} from '../api';
import {Section} from '../ui';

const TOOLS: {id: string; label: string; help: string; opts?: string}[] = [
  {id: 's4_manifest', label: '重建 manifest', help: '扫描 assets/ip 或占位 IP，登记素材映射'},
  {id: 's4b', label: '生成图任务单', help: '产出 assets/image_briefs.json（adapter 轮换）'},
  {id: 's4c', label: '图库素材(dry-run)', help: 'Pexels/Pixabay 检索关键词（不下载）', opts: 'dry_run'},
  {id: 's4e', label: 'ComfyUI 生图', help: '本地 ComfyUI 闭环生图+转视频（需 8188 端口）'},
  {id: 's4_relevance', label: '相关性打分', help: 'CLIP 打分，低分镜头标记'},
];

/** staging 后的路径（ip/… broll/… screenshots/…）由 vite publicDir 直接服务根路径；
 * 其余（job 内相对路径）走后端文件接口 */
function assetSrc(jobId: string, p: string): string {
  // manifest 里可能是绝对路径（…/assets/ip/ip24.jpg）→ 归一化成 assets/ 后的相对路径
  const m = p.match(/\/assets\/(.+)$/);
  const rel = m ? m[1] : p;
  if (/^(ip|broll|screenshots|_sc_test)\//.test(rel)) return `/${rel}`;
  return api.fileUrl(jobId, rel);
}


/** 素材视频搜索（MoneyPrinterTurbo 吸收：Pexels/Pixabay 免费商用素材库）。
 * 输入关键词或直接按某镜口播派生关键词 → 预览 → 一键应用到镜头（下载并登记 manifest，
 * S5 渲染该镜时升级为 RealFootage）。 */
function StockSearchPanel({onlyShot}: {onlyShot: string}) {
  const s = useStore();
  const [q, setQ] = useState('');
  const [shotId, setShotId] = useState(onlyShot);
  const [res, setRes] = useState<StockSearch | null>(null);
  const [loading, setLoading] = useState(false);
  const shots = s.sbDraft?.shots ?? [];
  React.useEffect(() => { if (onlyShot) setShotId(onlyShot); }, [onlyShot]);

  const search = async (query: string, sid?: string) => {
    setLoading(true);
    try { setRes(await api.stockSearch(s.jobId!, query, sid || undefined)); }
    catch (e: any) { s.notify('err', `搜索失败: ${e.message}`); }
    finally { setLoading(false); }
  };
  const apply = async (url: string, provider: string, duration?: number) => {
    if (!shotId) { s.notify('err', '先选择要应用到的镜头'); return; }
    try {
      await api.stockApply(s.jobId!, shotId, url, provider, duration);
      s.notify('ok', `已应用到 ${shotId}（S5 该镜升级 RealFootage）`);
      s.reloadStaged(); s.refreshSummary();
    } catch (e: any) { s.notify('err', `应用失败: ${e.message}`); }
  };

  return (
    <div className="panel" style={{marginBottom: 12, padding: 12}}>
      <div style={{fontWeight: 600, marginBottom: 6}}>素材视频搜索</div>
      <div style={{display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center'}}>
        <input style={{flex: 1, minWidth: 180}} placeholder="英文关键词，如 programmer typing" value={q}
               onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && search(q)} />
        <select value={shotId} onChange={(e) => setShotId(e.target.value)}>
          <option value="">选择镜头…</option>
          {shots.map((x: any) => <option key={x.id} value={x.id}>{x.id}</option>)}
        </select>
        <button className="small" disabled={loading} onClick={() => search(q)}>{loading ? '搜索中…' : '搜关键词'}</button>
        <button className="small" disabled={loading || !shotId}
                title="按该镜口播自动派生英文关键词（LLM 兜底规则）"
                onClick={() => search('', shotId)}>按镜派生</button>
      </div>
      {res && !res.available && <div className="faint" style={{marginTop: 6, fontSize: 12}}>⚠ {res.note}</div>}
      {res && (
        <div style={{display: 'flex', gap: 8, marginTop: 10, overflowX: 'auto'}}>
          {res.clips.map((c, i) => (
            <div key={i} className="thumb" style={{minWidth: 180}}>
              {c.preview ? <img src={c.preview} style={{width: '100%', height: 90, objectFit: 'cover'}}/> : null}
              <div className="cap">
                <span>{c.duration?.toFixed?.(1) ?? c.duration}s</span>
                <button className="small" onClick={() => c.url && apply(c.url, res.provider, c.duration)}>应用到 {shotId || '镜头'}</button>
              </div>
            </div>
          ))}
          {!res.clips.length && <div className="empty">无结果（无 API key 时请按关键词任务单人工搜索）</div>}
        </div>
      )}
    </div>
  );
}


/** 生图任务单（按镜头）：S3 分镜 → S4B 语义派生的全部生图任务。
 * 每镜一张卡：状态（待生成/已完成/失败）+ 成图预览 + 可编辑 prompt + 单镜重跑/全部生成。
 * 改 prompt 保存即删旧图回 pending，重跑走 s4e（ComfyUI）。 */
interface BriefSlots {style?: string; action?: string; expression?: string; scene?: string; intent?: string; [k: string]: string | undefined}
interface ImageOptions {styles: {id: string; label: string}[]; actions: {id: string; label: string}[]; expressions: {id: string; label: string}[]}

function ImageBriefsPanel() {
  const s = useStore();
  const [briefs, setBriefs] = useState<ImageBrief[]>([]);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [slots, setSlots] = useState<BriefSlots>({});
  const [opts, setOpts] = useState<ImageOptions | null>(null);
  useEffect(() => { fetch('/api/image-options').then((r) => r.json()).then(setOpts).catch(() => {}); }, []);
  const reload = async () => {
    if (!s.jobId) return;
    try { setBriefs((await api.imageBriefs(s.jobId)).briefs); } catch { /* job 无任务单 */ }
  };
  useEffect(() => { reload(); }, [s.jobId, s.stagedAssets]); // eslint-disable-line react-hooks/exhaustive-deps
  const save = async (b: ImageBrief) => {
    try {
      await api.saveBrief(s.jobId!, b.shot_id, draft, undefined, slots);
      s.notify('ok', `${b.shot_id} 槽位已保存（prompt 已按槽位重建），旧图已清`);
      setEditing(null);
      reload();
    } catch (e: any) { s.notify('err', `保存失败: ${e.message}`); }
  };
  const regen = async (shotId?: string) => {
    try {
      s.startRun(`生图 ${shotId ?? '全部缺图'}`, () => api.imageRegen(s.jobId!, shotId));
    } catch (e: any) { s.notify('err', `触发失败: ${e.message}`); }
  };
  const pending = briefs.filter((b) => b.status !== 'done').length;
  return (
    <div className="panel" style={{marginBottom: 12, padding: 12}}>
      <div style={{display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8}}>
        <div style={{fontWeight: 600}}>生图任务单（按镜头）</div>
        <span className="chip mono">{briefs.length} 镜 · 待生成 {pending}</span>
        <div style={{flex: 1}} />
        <button className="primary small" onClick={() => regen()}>生成全部缺图</button>
      </div>
      {!briefs.length && <div className="empty">暂无任务单：先在流水线跑 S4B（生图任务单）</div>}
      <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 10}}>
        {briefs.map((b) => (
          <div key={b.shot_id} className="thumb" style={{padding: 8}}>
            <div style={{display: 'flex', gap: 6, alignItems: 'center', marginBottom: 6}}>
              <strong>{b.shot_id}</strong>
              {b.status === 'done' && <span className="chip ok">已完成</span>}
              {b.status === 'error' && <span className="chip err">失败</span>}
              {b.status === 'pending' && <span className="chip warn">待生成</span>}
              {b.video && <span className="chip mono">MP4</span>}
              {b.seed != null && <span className="chip mono">seed {b.seed}</span>}
            </div>
            {b.png
              ? <img src={b.png} style={{width: '100%', aspectRatio: '16/9', objectFit: 'cover', borderRadius: 6}}/>
              : <div style={{width: '100%', aspectRatio: '16/9', borderRadius: 6, background: '#14151a',
                             display: 'flex', alignItems: 'center', justifyContent: 'center'}} className="faint">
                  {b.status === 'error' ? `失败: ${b.error.slice(0, 60)}` : '等待生图'}
                </div>}
            <div className="faint" style={{fontSize: 11, margin: '6px 0', maxHeight: 30, overflow: 'hidden'}}>
              口播：{b.vo?.slice(0, 40)}
            </div>
            {(b.semantic?.visual_intent ?? []).map((t) => <span key={t} className="chip ok" style={{marginRight: 4}}>{t}</span>)}
            {editing === b.shot_id ? (
              <div style={{display: 'grid', gap: 6}}>
                <label style={{fontSize: 11}} className="faint">画风（固定预设）
                  <select value={slots.style ?? ''} style={{width: '100%'}}
                          onChange={(e) => setSlots((d) => ({...d, style: e.target.value}))}>
                    <option value="">保持 {b.style}</option>
                    {(opts?.styles ?? []).map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
                  </select>
                </label>
                <label style={{fontSize: 11}} className="faint">动作（意图映射）
                  <select value={slots.action ?? ''} style={{width: '100%'}}
                          onChange={(e) => setSlots((d) => ({...d, action: e.target.value}))}>
                    <option value="">保持（{b.slots?.action?.slice(0, 30) ?? '默认'}）</option>
                    {(opts?.actions ?? []).map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
                  </select>
                </label>
                <label style={{fontSize: 11}} className="faint">表情（夸张轴）
                  <select value={slots.expression ?? 'auto'} style={{width: '100%'}}
                          onChange={(e) => setSlots((d) => ({...d, expression: e.target.value}))}>
                    {(opts?.expressions ?? []).map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
                  </select>
                </label>
                <label style={{fontSize: 11}} className="faint">场景内容（取整镜口播，可改）
                  <input value={slots.scene ?? b.slots?.scene ?? ''} style={{width: '100%'}}
                         placeholder={b.vo?.slice(0, 40)}
                         onChange={(e) => setSlots((d) => ({...d, scene: e.target.value}))}/>
                </label>
                <div style={{display: 'flex', gap: 6}}>
                  <button className="primary small" onClick={() => save(b)}>保存（按槽位重建 prompt）</button>
                  <button className="small" onClick={() => { save(b); regen(b.shot_id); }}>保存并重跑</button>
                  <button className="small" onClick={() => setEditing(null)}>取消</button>
                </div>
              </div>
            ) : (
              <>
                <div style={{fontSize: 11, maxHeight: 30, overflow: 'hidden'}} className="faint">
                  口播：{b.vo?.slice(0, 44)}
                </div>
                <div style={{display: 'flex', gap: 6, marginTop: 6}}>
                  <button className="small" onClick={() => { setEditing(b.shot_id); setSlots(b.slots ?? {}); }}>改槽位</button>
                  <button className="small" onClick={() => regen(b.shot_id)}>重跑此镜</button>
                </div>
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export function AssetsView() {
  const s = useStore();
  // staged 优先（与预览渲染完全一致的路径改写），manifest 原文兜底
  const staged = s.stagedAssets ?? {};
  const manifest = {
    ...(s.snap!.artifacts.manifest ?? {}),
    ...(staged as any),
  };
  const briefs = s.snap!.artifacts.briefs;
  const relevance = s.snap!.artifacts.relevance;
  const shots = s.sbDraft?.shots ?? [];
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploadTarget, setUploadTarget] = useState<{shot: string; kind: string} | null>(null);
  const [onlyShot, setOnlyShot] = useState('');

  useEffect(() => {
    if (uploadTarget) fileRef.current?.click();
  }, [uploadTarget]);

  if (!s.snap!.artifacts.manifest) return <div className="pane"><ImageBriefsPanel /><StockSearchPanel onlyShot={onlyShot} /><div className="empty">还没有 manifest.json（先跑 S4 登记素材）</div></div>;

  const runTool = (id: string, opts: Record<string, unknown> = {}) =>
    s.startRun(`tool ${id}${onlyShot ? ' ' + onlyShot : ''}`, () => api.tool(s.jobId!, id, {only: onlyShot || undefined, ...opts}));

  const upload = async (file: File) => {
    if (!uploadTarget) return;
    try {
      await api.uploadAsset(s.jobId!, uploadTarget.shot, uploadTarget.kind, file.name, file);
      s.notify('ok', `已上传 ${uploadTarget.shot} ${uploadTarget.kind}`);
      s.reloadStaged();
      s.refreshSummary();
    } catch (e: any) {
      s.notify('err', `上传失败: ${e.message}`);
    } finally {
      setUploadTarget(null);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const ipImages: [string, string][] = Object.entries(manifest.ip_images ?? {});
  const ipScenes: [string, string][] = Object.entries(manifest.ip_scenes ?? {});
  const brollVideos: [string, any][] = Object.entries(manifest.broll_videos ?? {});
  const screenshots: [string, string][] = Object.entries(manifest.screenshots ?? {});

  return (
    <div className="pane">
      <ImageBriefsPanel />
      <StockSearchPanel onlyShot={onlyShot} />
      <input ref={fileRef} type="file" style={{display: 'none'}}
             accept={uploadTarget?.kind === 'broll_video' ? 'video/*' : 'image/*'}
             onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />

      <h2>素材生产 <span className="chip mono" style={{marginLeft: 8}}>{s.jobId}</span></h2>
      <div className="sub">逐镜素材：生图 → 白板动画/图库 → 相关性打分。上传替换立即生效（自动重新 staging 到预览）。</div>

      <div className="card">
        <div style={{display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap'}}>
          <span className="muted" style={{fontSize: 12}}>--only 镜头:</span>
          <select value={onlyShot} onChange={(e) => setOnlyShot(e.target.value)} style={{width: 140}}>
            <option value="">（全部）</option>
            {shots.map((x) => <option key={x.id} value={x.id}>{x.id}</option>)}
          </select>
          {TOOLS.map((t) => (
            <button key={t.id} className="small" title={t.help} onClick={() => runTool(t.id, t.opts ? {[t.opts]: true} : {})}>
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div className="card">
        <div className="muted" style={{fontSize: 11, marginBottom: 8}}>IP 姿态/三视图（ip_images）</div>
        <div className="grid4">
          {ipImages.map(([view, p]) => (
            <div key={view} className="thumb">
              <img src={assetSrc(s.jobId!, p)} loading="lazy" />
              <div className="cap"><span>{view}</span></div>
            </div>
          ))}
          {ipImages.length === 0 && <span className="faint">无</span>}
        </div>
        {ipScenes.length > 0 && (
          <>
            <div className="muted" style={{fontSize: 11, margin: '12px 0 8px'}}>逐镜场景图（ip_scenes → A-roll）</div>
            <div className="grid4">
              {ipScenes.map(([shot, p]) => (
                <div key={shot} className="thumb">
                  <img src={assetSrc(s.jobId!, p)} loading="lazy" />
                  <div className="cap"><span>{shot}</span><span>{p.split('/').pop()}</span></div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      <div className="card">
        <div className="muted" style={{fontSize: 11, marginBottom: 8}}>B-roll 视频素材（broll_videos）</div>
        {brollVideos.length === 0 && <span className="faint">暂无（可跑 ComfyUI 生图 / 图库素材 / 上传）</span>}
        <div className="grid4">
          {brollVideos.map(([shot, v]) => {
            const flag = relevance?.flags?.[shot];
            return (
              <div key={shot} className="thumb">
                <video src={assetSrc(s.jobId!, v.path)} muted loop
                       onMouseEnter={(e) => (e.target as HTMLVideoElement).play().catch(() => undefined)}
                       onMouseLeave={(e) => (e.target as HTMLVideoElement).pause()} />
                <div className="cap">
                  <span>{shot}</span>
                  {flag && <span className={`chip ${flag.flag === 'low' ? 'warn' : 'ok'}`}>clip {flag.score?.toFixed?.(2)}</span>}
                  <button className="ghost small" title="上传替换" onClick={() => setUploadTarget({shot, kind: 'broll_video'})}>⬆</button>
                </div>
                <div className="cap"><span>{v.provider}</span></div>
              </div>
            );
          })}
        </div>
        {screenshots.length > 0 && (
          <>
            <div className="muted" style={{fontSize: 11, margin: '12px 0 8px'}}>网页实拍截图（screenshots → ScreenshotCard）</div>
            <div className="grid4">
              {screenshots.map(([shot, p]) => (
                <div key={shot} className="thumb">
                  <img src={assetSrc(s.jobId!, p)} loading="lazy" />
                  <div className="cap">
                    <span>{shot}</span>
                    <button className="ghost small" onClick={() => setUploadTarget({shot, kind: 'screenshot'})}>⬆</button>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {briefs?.briefs?.length > 0 && (
        <div className="card">
          <div className="muted" style={{fontSize: 11, marginBottom: 8}}>生图任务单（image_briefs · {briefs.briefs.length} 条）</div>
          <table className="tbl">
            <thead><tr><th>镜头</th><th>adapter</th><th>风格</th><th>prompt</th><th>目标</th></tr></thead>
            <tbody>
              {briefs.briefs.map((b: any) => (
                <tr key={b.shot_id}>
                  <td className="mono">{b.shot_id}</td>
                  <td>{b.adapter}</td>
                  <td className="muted">{b.style}</td>
                  <td className="muted" style={{maxWidth: 420, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}} title={b.prompt}>{b.prompt}</td>
                  <td className="mono faint">{b.target_path}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {relevance && (
        <div className="card">
          <div className="muted" style={{fontSize: 11, marginBottom: 8}}>
            相关性报告（threshold {relevance.threshold} · 打分 {relevance.scored} · 低分 {relevance.flagged}）
          </div>
          <div style={{display: 'flex', gap: 5, flexWrap: 'wrap'}}>
            {Object.entries(relevance.flags ?? {}).map(([shot, f]: [string, any]) => (
              <span key={shot} className={`chip ${f.flag === 'low' ? 'warn' : 'ok'}`} title={f.flag === 'low' ? '低分 → 渲染降级为背景纹理' : ''}>
                {shot} {f.score?.toFixed?.(2)}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
