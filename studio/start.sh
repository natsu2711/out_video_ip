#!/bin/bash
# IP Studio 一键启动：后端 API (8321) + 前端 Vite (5188)
# 用法: bash studio/start.sh
set -e
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

if [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "✗ 未找到 .venv（先在项目根创建 Python 3.13 虚拟环境并安装流水线依赖）"; exit 1
fi
if [ ! -d "$ROOT/studio/web/node_modules" ]; then
  echo "[studio] 安装前端依赖…"
  (cd "$ROOT/studio/web" && npm install --no-audit --no-fund)
fi

cleanup() { kill $BACK_PID $WEB_PID 2>/dev/null; }
trap cleanup EXIT

echo "[studio] 后端 http://127.0.0.1:8321"
"$ROOT/.venv/bin/python" -m uvicorn studio.server.app:app --port 8321 &
BACK_PID=$!

echo "[studio] 前端 http://localhost:5188 （Ctrl+C 退出）"
cd "$ROOT/studio/web" && ./node_modules/.bin/vite --port 5188 &
WEB_PID=$!

open "http://localhost:5188" 2>/dev/null || true
wait
