/** 后端 API 封装 + 核心数据类型（与 render-engine/src/lib/loader.ts 的 JobData 对齐） */

export interface JobSummary {
  id: string;
  title: string;
  canvas?: {width: number; height: number; fps: number; ratio: string};
  theme?: string | null;
  stages: Record<string, {status: string; note?: string; ts?: string; fresh?: boolean; stale?: string[]}>;
  current?: string | null;
  next_runnable?: string | null;
  gates: Record<string, string>;
  meta?: Record<string, unknown>;
  stage_artifacts?: Record<string, Array<{rel: string; exists: boolean; count?: number}>>;
  error?: string;
}

export interface Shot {
  id: string;
  time: {start_ms: number; end_ms: number; seg_ids: string[]};
  vo: string;
  roll: 'A' | 'B';
  b_type?: 'real' | 'graphic' | 'text' | null;
  view_angle?: string | null;
  intent: string;
  visual: string;
  motion: string[];
  transition_in?: string;
  overlay?: string[];
  presentation?: string;
  camera?: {dir: 'in' | 'out'};
  recipe_ref: string;
  assets_needed?: string[];
  status: string;
  config?: {TEXT?: string[]; STEPS?: string[]; CONFIG?: Record<string, unknown>; scene?: string; note?: string; [k: string]: unknown};
  sfx?: Array<{t_ms: number; name: string; gain?: number}>;
  layers?: Array<{
    id: string; kind: 'overlay' | 'card' | 'media_image' | 'media_video' | 'text'; ref?: string; label?: string;
    enabled?: boolean; in_ms?: number; out_ms?: number | null;
    x?: number; y?: number; scale?: number; opacity?: number;
    presentation?: 'none' | 'rise_fade' | 'slam_in' | 'blur_focus';
    config?: any;
  }>;
  seg?: {beat?: string; visual_hint?: string};
  ir?: Record<string, unknown>;
  compiler_plan?: Record<string, unknown> | null;
  degraded?: boolean;
  rhythm_check?: Record<string, unknown>;
}

export interface TimingSegment {
  id: string;
  start_ms: number;
  end_ms: number;
  text: string;
  seg_ref?: string;
  match?: number;
  ok?: boolean;
  words?: Array<{text: string; start_ms: number; end_ms: number; protected?: boolean}>;
  align_confidence?: 'high' | 'medium' | 'low';
  align_score?: number;
}

export interface Timing {
  version: string;
  audio: string;
  duration_ms: number;
  backend?: string;
  segments: TimingSegment[];
  invariants?: Record<string, unknown>;
}

export interface ScriptSegment {
  id: string;
  text: string;
  beat: string;
  visual_hint: string;
  protected_tokens?: Array<{token: string; char_start: number; char_end: number}>;
}

export interface ScriptDoc {
  version?: string;
  job_id?: string;
  source?: string;
  meta?: Record<string, unknown>;
  segments: ScriptSegment[];
}

export interface CardEntry {
  slug: string;
  component: string;
  tier: 'injectable' | 'raw';
  durationInFrames: number | null;
  desc: string;
  contentKeys: Record<string, boolean>;
  arities: Record<string, number>;
  jsxTexts?: string[];
  sourceFile: string;
}

export interface ThemeDef {
  id: string;
  name?: string;
  bg: string;
  text: string;
  anchor: string;
  description?: string;
}

export interface Meta {
  cards: Record<string, CardEntry>;
  shot_components: string[];
  overlays: string[];
  presentations: string[];
  beats: string[];
  visual_hints: string[];
  view_angles: string[];
  b_types: string[];
  transitions: string[];
  sfx: string[];
  themes: ThemeDef[];
}

export interface Snapshot {
  summary: JobSummary;
  artifacts: {
    project?: any;
    script?: ScriptDoc | null;
    timing?: Timing | null;
    storyboard?: {version?: string; job_id?: string; shots: Shot[]; rhythm_check?: any; meta?: any} | null;
    manifest?: any;
    briefs?: any;
    stock_keywords?: any;
    relevance?: any;
    local_images?: any;
    qa?: any;
    sfx_cues?: any;
    frame_metrics?: any;
    table_md?: string | null;
    ablation?: string | null;
    story?: string | null;
  };
  meta: Meta;
}

export interface RunInfo {
  id: string;
  job: string;
  label: string;
  status: 'running' | 'done' | 'failed';
  started: number;
  ended?: number | null;
  returncode?: number | null;
  log?: string[];
}

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  if (!r.ok) {
    let detail = `${r.status} ${r.statusText}`;
    try {
      const j = await r.json();
      detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail ?? j);
    } catch { /* ignore */ }
    throw new Error(detail);
  }
  return r.json() as Promise<T>;
}

export interface RecallCandidate {
  slug: string; source: string; score: number; matched_intents: string[];
  desc?: string; category?: string; category3?: string; tier?: string;
  durationInFrames?: number; arities?: Record<string, number>; images?: string[];
  slotDefaults?: Record<string, unknown>;
}
export interface RecallResult {
  query: string; beat: string; intents: string[]; weknora_available: boolean;
  candidates: RecallCandidate[];
}

export interface StockClip {url?: string; width?: number; height?: number; duration?: number; preview?: string; term?: string}
export interface StockSearch {available: boolean; provider: string; keywords: string[]; note: string; clips: StockClip[]}

export interface ImageBrief {
  shot_id: string; adapter: string; style: string; prompt: string; negative: string;
  seed?: number | null; reference_image: string; target_path: string; png: string;
  video: boolean; status: string; error: string; vo: string;
  semantic?: {visual_intent?: string[]; beat?: string; intent_text?: string};
  slots?: {style?: string; action?: string; expression?: string; scene?: string; intent?: string};
}

export const api = {
  imageBriefs: (jobId: string) => req<{briefs: ImageBrief[]}>(`/api/job/${jobId}/image-briefs`),
  saveBrief: (jobId: string, shotId: string, prompt: string, negative?: string, slots?: Record<string, string>) =>
    req<{ok: boolean}>(`/api/job/${jobId}/image-brief/${shotId}`, {
      method: 'PUT', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({prompt, negative, slots}),
    }),
  imageRegen: (jobId: string, shotId?: string) =>
    req<{run_id: string}>(`/api/job/${jobId}/image-regen`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({shot_id: shotId ?? ''}),
    }),
  stockSearch: (jobId: string, query: string, shotId?: string) =>
    req<StockSearch>(`/api/stock-search?job_id=${encodeURIComponent(jobId)}&query=${encodeURIComponent(query)}&shot_id=${encodeURIComponent(shotId ?? '')}`),
  stockApply: (jobId: string, shotId: string, url: string, provider: string, duration?: number) =>
    req<{ok: boolean}>(`/api/job/${jobId}/stock-apply`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({shot_id: shotId, url, provider, duration: duration ?? null}),
    }),
  recall: (query: string, beat: string, topK = 8) =>
    req<RecallResult>(`/api/recall?query=${encodeURIComponent(query)}&beat=${encodeURIComponent(beat)}&top_k=${topK}`),
  jobs: () => req<JobSummary[]>('/api/jobs'),
  job: (id: string) => req<JobSummary>(`/api/job/${id}`),
  snapshot: (id: string) => req<Snapshot>(`/api/job/${id}/snapshot`),
  meta: () => req<Meta>('/api/meta'),
  saveArtifact: (id: string, name: string, content: unknown) =>
    req<{ok: boolean}>(`/api/job/${id}/artifact/${name}`, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({content}),
    }),
  run: (id: string, stage: string | null, force = false) =>
    req<{run_id: string}>(`/api/job/${id}/run`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({stage, force}),
    }),
  gate: (id: string, stage: string, approve: boolean) =>
    req<JobSummary>(`/api/job/${id}/gate`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({stage, approve}),
    }),
  tool: (id: string, tool: string, opts: {only?: string; force?: boolean; dry_run?: boolean; no_video?: boolean} = {}) =>
    req<{run_id: string}>(`/api/job/${id}/tool`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({tool, ...opts}),
    }),
  runDetail: (runId: string, tail = 200) => req<RunInfo>(`/api/run/${runId}?tail=${tail}`),
  stageAssets: (id: string) => req<{assets: any}>(`/api/job/${id}/stage-assets`, {method: 'POST'}),
  renderStill: (id: string, shotId: string, frame: number) =>
    req<{run_id: string; out: string}>(`/api/job/${id}/render-still`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({shot_id: shotId, frame}),
    }),
  renderShot: (id: string, shotId: string) =>
    req<{run_id: string}>(`/api/job/${id}/render-shot`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({shot_id: shotId}),
    }),
  uploadAsset: (id: string, shotId: string, kind: string, filename: string, file: Blob) =>
    req<{ok: boolean; path: string}>(`/api/job/${id}/upload-asset?shot_id=${shotId}&kind=${kind}&filename=${encodeURIComponent(filename)}`, {
      method: 'POST', body: file,
    }),
  applyEffect: (id: string, payload: Record<string, unknown>) =>
    req<{ok: boolean; run_id: string | null; note?: string}>(`/api/job/${id}/apply-effect`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    }),
  produce: (id: string) => req<{run_id: string}>(`/api/job/${id}/produce`, {method: 'POST'}),
  uploadLayerMedia: (id: string, filename: string, file: Blob) =>
    req<{ok: boolean; path: string}>(`/api/job/${id}/upload-layer-media?filename=${encodeURIComponent(filename)}`, {
      method: 'POST', body: file,
    }),
  getRouteMode: (id: string) => req<{route_mode: 'auto' | 'llm'}>(`/api/job/${id}/route-mode`),
  setRouteMode: (id: string, mode: 'auto' | 'llm') =>
    req<{ok: boolean; note?: string}>(`/api/job/${id}/route-mode`, {
      method: 'PUT', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({mode}),
    }),
  createJob: (slug: string, title: string, story: string | null) =>
    req<JobSummary>('/api/jobs', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({slug, title, story}),
    }),
  fileUrl: (id: string, path: string) => `/api/job/${id}/file?path=${encodeURIComponent(path)}`,
  previewUrl: (out: string) => `/api/preview/${out}`,
};

export const fmtMs = (ms: number) => {
  const s = ms / 1000;
  return `${s.toFixed(2)}s`;
};
export const fmtClock = (ms: number) => {
  const total = Math.floor(ms / 1000);
  const m = Math.floor(total / 60);
  const s = total % 60;
  const cs = Math.floor((ms % 1000) / 10);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(cs).padStart(2, '0')}`;
};
