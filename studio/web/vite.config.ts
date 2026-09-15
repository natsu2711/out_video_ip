import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

// 项目根（studio/web → 上两级）
export const PROJECT_ROOT = path.resolve(__dirname, '../..');
// 卡片源码目录：前端经 /@fs 动态 import + 内容注入（每次内容变更换 URL 重求值）
export const CARDS_DIR = path.join(PROJECT_ROOT, 'render-engine/src/cards');

export default defineConfig({
  plugins: [react()],
  resolve: {
    // render-engine 源码的 'remotion'/'react' 导入也统一解析到本包的同一份实例，
    // 避免 Remotion 双实例导致 useCurrentFrame 等 hooks 读不到 Player 上下文
    dedupe: ['react', 'react-dom', 'remotion'],
  },
  define: {
    __CARDS_DIR__: JSON.stringify(CARDS_DIR),
  },
  publicDir: path.join(PROJECT_ROOT, 'render-engine/public'),
  server: {
    port: 5188,
    strictPort: true,
    fs: {
      allow: [PROJECT_ROOT],
    },
    proxy: {
      '/api': 'http://127.0.0.1:8321',
    },
  },
});
