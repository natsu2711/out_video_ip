/** 镜头 Props 派生（纯函数，不读文件系统）。
 * 数据由 Python 侧（s5_render.py）读好 JSON 后经 --props 传入，
 * 结构见 JobData。禁止在 Remotion 组件内使用 Node 的 fs/path。 */

export interface JobData {
  job: {id: string; root: string};
  project: Project;
  timing: Timing;
  storyboard: Storyboard;
  assets: Assets;
}

export interface Project {
  canvas: {width: number; height: number; fps: number; ratio: string};
  voice: {provider: string; ref_audio: string; speed: number};
  style: {
    a_roll: {style_lock: string; reference_images: {[k: string]: string}};
    b_roll: {palette: {bg: string; anchor: string; text: string}};
  };
}

export interface Timing {
  version: string;
  audio: string;
  duration_ms: number;
  segments: Array<{
    id: string;
    start_ms: number;
    end_ms: number;
    text: string;
    words: Array<{text: string; start_ms: number; end_ms: number}>;
  }>;
}

export interface Storyboard {
  job_id: string;
  shots: Array<Shot>;
  rhythm_check?: {a_b_ratio: number[]};
}

export interface Shot {
  id: string;
  time: {start_ms: number; end_ms: number; seg_ids: string[]};
  vo: string;
  roll: 'A' | 'B';
  b_type?: 'text' | 'graphic' | 'real';
  view_angle?: 'host' | 'protagonist' | 'supporting' | 'pov';
  intent: string;
  visual: string;
  motion: string[];
  transition_in: string;
  overlay?: string[];
  presentation?: 'wipe_mask' | 'rise_fade' | 'slam_in' | 'blur_focus' | 'none';
  camera?: {dir: 'in' | 'out'};
  recipe_ref: string;
  assets_needed: string[];
  status: string;
  config?: {TEXT?: string[]; CONFIG?: Record<string, unknown>; scene?: string; note?: string};
  sfx?: Array<{t_ms: number; name: string; gain?: number}>;
}

export interface Assets {
  ip_images: {[view: string]: string};
  bgm?: string;
  screenshots?: {[shotId: string]: string};
  ip_scenes?: {[shotId: string]: string};
  ip_poses?: {[pose: string]: string};
}

export function shotProps(
  data: JobData,
  shotId: string,
): {shot: Shot; timingSegs: typeof data.timing.segments; tokens: typeof data.project.style.b_roll.palette} {
  const shot = data.storyboard.shots.find((s) => s.id === shotId);
  if (!shot) throw new Error(`Shot ${shotId} not found`);
  const timingSegs = shot.time.seg_ids
    .map((sid) => data.timing.segments.find((s) => s.id === sid))
    .filter((s): s is typeof data.timing.segments[0] => s !== undefined);
  const tokens = data.project.style.b_roll.palette;
  return {shot, timingSegs, tokens};
}

export function msToFrames(ms: number, fps: number): number {
  return Math.floor((ms / 1000) * fps);
}

export function fps30Ms(ms: number): number {
  return msToFrames(ms, 30);
}
