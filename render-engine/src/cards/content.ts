/** 卡内容构建器：把 shot（vo/intent/motion）映射成卡的 TEXT 注入数组。
 * 通用策略（不逐卡定制也能用）：
 *   抽取优先级：引号词「」 > 数字 > 意图短语 > 口播句切分
 *   元素数对齐 registry.arities.TEXT（多退少补，用占位短语） */
import type {CardEntry} from './index';

function extractQuotes(text: string): string[] {
  return (text.match(/[「『][^」』]+[」』]/g) || []).map((s) => s.slice(1, -1));
}

function extractNumbers(text: string): string[] {
  return (text.match(/[0-9一二两三四五六七八九十百千万亿%％.]+(?:个|天|周|年|块|美金|美元|倍|%|％)?/g) || [])
    .filter((s) => s.length <= 8)
    .slice(0, 4);
}

function sentenceChunks(text: string, n: number): string[] {
  const parts = text
    .split(/[，。！？；、]/)
    .map((s) => s.trim())
    .filter((s) => s.length >= 2);
  const out: string[] = [];
  for (const p of parts) {
    out.push(p.length > 12 ? p.slice(0, 12) : p);
    if (out.length >= n) break;
  }
  while (out.length < n) out.push(out[out.length % Math.max(1, out.length)] ?? text.slice(0, 8));
  return out.slice(0, n);
}

/** 生成 N 条内容：引号词 → 数字 → 意图 → 句子块，逐级补位 */
export function deriveTexts(shot: {vo: string; intent: string; motion?: string[]}, n: number): string[] {
  const pool: string[] = [];
  pool.push(...extractQuotes(shot.vo));
  pool.push(...extractNumbers(shot.vo));
  const intent = (shot.intent || '').replace(/[。！？]/g, '');
  if (intent) pool.push(intent.slice(0, 10));
  for (const c of sentenceChunks(shot.vo, n * 2)) {
    if (pool.length >= n * 2) break;
    pool.push(c);
  }
  // 去重 + 截长
  const seen = new Set<string>();
  const uniq = pool
    .map((s) => s.trim())
    .filter((s) => {
      if (!s || seen.has(s)) return false;
      seen.add(s);
      return true;
    })
    .map((s) => (s.length > 14 ? s.slice(0, 13) + '…' : s));
  const out: string[] = [];
  let i = 0;
  while (out.length < n && uniq.length) {
    out.push(uniq[i % uniq.length]);
    i += 1;
  }
  return out;
}

/** 构建注入对象：遍历 registry.arities 的全部槽位（TEXT/ROWS/STEPS/ITEMS/...）逐一对齐注入。
 * 修复：此前只处理 TEXT/STEPS，ROWS 类卡（如 alt-block-lines）从未被注入，渲染的是 talkcraft 原演示文案。
 * 形状感知：slotDefaults（scripts/extract_card_slots.py 抽取的槽位原始形状）为对象时，
 * 把文案合并进默认对象（保留 cls/label 等视觉字段），只覆盖 text —— 字符串直灌会渲染空白。
 * shot.config 存在时逐镜设计内容优先（talkcraft 生产范式：每卡 CONFIG 由分镜师手写，自动派生只是兜底） */
export function buildCardContent(entry: CardEntry, shot: {vo: string; intent: string; config?: Record<string, unknown>}): Record<string, unknown> {
  const inj: Record<string, unknown> = {};
  const cap16 = (a: string[]) => a.map((t) => (t.length > 16 ? t.slice(0, 15) + "…" : t));
  const defaults = (entry as any).slotDefaults ?? {};
  for (const [key, n] of Object.entries(entry.arities ?? {})) {
    if (typeof n !== "number" || n <= 0) continue;
    if (key === "SLOTS") {
      // 对象槽（{text?,image?}）：编辑器/用户直填，原样透传
      const slots = shot.config?.SLOTS as any[] | undefined;
      if (slots?.length) inj.SLOTS = slots.slice(0, n);
      continue;
    }
    const manual = (shot.config?.[key] as string[] | undefined) ?? [];
    const texts = cap16(manual.length > 0 ? manual : deriveTexts(shot, n));
    const shape = defaults[key] ?? [];
    inj[key] = shape.length > 0 && typeof shape[0] === "object" && shape[0] !== null
      ? texts.map((t, i) => ({...(shape[i % shape.length] as object), text: t}))
      : texts;
  }
  if (shot.config?.CONFIG) {
    inj.CONFIG = shot.config.CONFIG;
  }
  return inj;
}
