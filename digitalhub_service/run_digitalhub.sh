#!/usr/bin/env bash
set -euo pipefail

# 基于当前脚本定位仓库根目录（.../digitalhuman/digitalhub_service -> .../digitalhuman）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJ_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 若未显式传入，则用相对路径作为默认值（不再依赖 $HOME）
export VTUBER_ROOT="${VTUBER_ROOT:-${PROJ_ROOT}/3rdparty/Open-LLM-VTuber}"
export LLM_SERVER_ROOT="${LLM_SERVER_ROOT:-${PROJ_ROOT}/digitalhuman_round_server}"
#export PUBLIC_HOST="${PUBLIC_HOST:-localhost}"
export PUBLIC_VTUBER_HOST="vtuber.yeying.pub"
export PUBLIC_LLM_HOST="llm-round.yeying.pub"
export PUBLIC_HOST="vtuber.yeying.pub"

# 可选：运行前做一下目录存在性校验，避免踩到后续 500
for d in "$VTUBER_ROOT" "$LLM_SERVER_ROOT"; do
  if [[ ! -d "$d" ]]; then
    echo "目录不存在: $d"
    echo "请确认目录结构为："
    echo "  ${PROJ_ROOT}/3rdparty/Open-LLM-VTuber"
    echo "  ${PROJ_ROOT}/digitalhuman_round_server"
    exit 1
  fi
done

# 可选：运行前做一下目录存在性校验，避免踩到后续 500
for d in "$VTUBER_ROOT" "$LLM_SERVER_ROOT"; do
  if [[ ! -d "$d" ]]; then
    echo "目录不存在: $d"
    echo "请确认目录结构为："
    echo "  ${PROJ_ROOT}/3rdparty/Open-LLM-VTuber"
    echo "  ${PROJ_ROOT}/digitalhuman_round_server"
    exit 1
  fi
done

if command -v uv >/dev/null 2>&1; then
  # 用 uv 直接启动，临时环境自动解析依赖，无需系统 python/venv/pip
  exec uv run \
    --with fastapi>=0.110 \
    --with 'uvicorn[standard]>=0.29' \
    --with pydantic>=2.6 \
    --with requests>=2.31 \
    uvicorn digitalhub_service:app --host 0.0.0.0 --port 9019 --reload
elif command -v python3 >/dev/null 2>&1; then
  # 兜底：系统有 python3 就用 venv 跑
  PY=python3
  $PY -m venv .venv
  . .venv/bin/activate
  python -m pip install -U pip wheel
  python -m pip install -r requirements_digitalhub.txt
  exec uvicorn digitalhub_service:app --host 0.0.0.0 --port 9019 --reload
else
  echo "未发现 uv 或 python3。请先安装 uv（推荐）或 python3。"
  exit 1
fi
