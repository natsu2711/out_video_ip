/** 配方卡注册表：79 张 talkcraft 移植卡的惰性加载器。
 * 关键机制：卡内容经 globalThis.__OUTVIDEO_CARD__ 在「模块求值前」注入
 * （import_cards.py 的 codemod 把内容常量改为 __INJ__.X ?? 原值）。
 * s5 每镜独立进程渲染 → 单进程单卡求值，注入安全；concat 阶段与卡无关。 */
import registryJson from './registry.json';

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

export const CARD_REGISTRY = registryJson as unknown as Record<string, CardEntry>;

const ctx = require.context('./', false, /^\.\/card-[^/]+\.tsx$/);

const cache: Record<string, React.ComponentType<any>> = {};

export function cardExists(slug: string): boolean {
  return ctx.keys().includes(`./card-${slug}.tsx`);
}

/** 求值并返回卡组件。调用前必须已 setCardContent（模块只在首次 require 时求值一次）。 */
export function loadCardComponent(slug: string): React.ComponentType<any> | null {
  const key = `./card-${slug}.tsx`;
  if (!ctx.keys().includes(key)) return null;
  if (!cache[slug]) {
    const mod = ctx(key);
    cache[slug] = (mod.default ?? mod) as React.ComponentType<any>;
  }
  return cache[slug];
}

/** 渲染前调用：把分镜文案灌进注入点（卡模块求值时读取） */
export function setCardContent(content: Record<string, unknown>): void {
  (globalThis as any).__OUTVIDEO_CARD__ = content;
}
