/** 卡片动态加载：setCardContent 必须发生在卡模块求值前（模块求值时读 __OUTVIDEO_CARD__）。
 * Vite dev 下用 /@fs 绝对路径 + 内容哈希 query 实现「内容变更 → 重新求值」；
 * 全局串行队列保证「注入→求值」不被并发加载交叉污染。 */
declare const __CARDS_DIR__: string;

export type CardComponent = React.ComponentType<any>;

function hashStr(s: string): string {
  let h = 5381;
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) + h + s.charCodeAt(i)) | 0;
  }
  return (h >>> 0).toString(36);
}

let queue: Promise<unknown> = Promise.resolve();

const modCache = new Map<string, CardComponent>();

export function loadCardEvaluating(slug: string, content: Record<string, unknown>): Promise<CardComponent> {
  const url = `/@fs${__CARDS_DIR__}/card-${slug}.tsx?cardv=${hashStr(JSON.stringify(content))}`;
  const cached = modCache.get(url);
  if (cached) return Promise.resolve(cached);
  const next = queue.then(async () => {
    (globalThis as any).__OUTVIDEO_CARD__ = content;
    const mod = await import(/* @vite-ignore */ url);
    const comp = ((mod as any).default ?? mod) as CardComponent;
    modCache.set(url, comp);
    return comp;
  });
  queue = next.catch(() => undefined);
  return next;
}
