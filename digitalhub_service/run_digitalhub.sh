#!/usr/bin/env bash
set -euo pipefail

# 路径按你的目录，已对齐
export VTUBER_ROOT="${VTUBER_ROOT:-$HOME/work/3rdparty/Open-LLM-VTuber}"
export LLM_SERVER_ROOT="${LLM_SERVER_ROOT:-$HOME/work/digitalhuman_round_server}"
export PUBLIC_HOST="${PUBLIC_HOST:-localhost}"

if command -v uv >/dev/null 2>&1; then
  # 用 uv 直接启动，临时环境自动解析依赖，无需系统 python/venv/pip
  exec uv run \
    --with fastapi>=0.110 \
    --with 'uvicorn[standard]>=0.29' \
    --with pydantic>=2.6 \
    --with requests>=2.31 \
    uvicorn digitalhub_service:app --host 127.0.0.1 --port 9009 --reload
elif command -v python3 >/dev/null 2>&1; then
  # 兜底：系统有 python3 就用 venv 跑
  PY=python3
  $PY -m venv .venv
  . .venv/bin/activate
  python -m pip install -U pip wheel
  python -m pip install -r requirements_digitalhub.txt
  exec uvicorn digitalhub_service:app --host 127.0.0.1 --port 9009 --reload
else
  echo "未发现 uv 或 python3。请先安装 uv（推荐）或 python3。"
  exit 1
fi
