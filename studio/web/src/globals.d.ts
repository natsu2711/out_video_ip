// Vite 环境全局声明
declare const __CARDS_DIR__: string;
// render-engine 的 cards/index.tsx 使用 webpack require.context（仅 CLI 渲染路径，Studio 不走）
declare const require: any;
