#!/usr/bin/env bash
set -euo pipefail

# 基于当前脚本定位仓库根目录（.../digitalhuman/digitalhub_service -> .../digitalhuman）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJ_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 若未显式传入，则用相对路径作为默认值（不再依赖 $HOME）
export VTUBER_ROOT="${VTUBER_ROOT:-${PROJ_ROOT}/3rdparty/Open-LLM-VTuber}"
export LLM_SERVER_ROOT="${LLM_SERVER_ROOT:-${PROJ_ROOT}/digitalhuman_round_server}"
export PUBLIC_VTUBER_HOST="vtuber.yeying.pub"
export PUBLIC_LLM_HOST="llm-round.yeying.pub"
export PUBLIC_HOST="vtuber.yeying.pub"

# 可选：运行前做一下目录存在性校验，避免踩到后续 500
missing=()
for d in "$VTUBER_ROOT" "$LLM_SERVER_ROOT"; do
  if [[ ! -d "$d" ]]; then
    missing+=("$d")
  fi
done
if ((${#missing[@]})); then
  echo "[WARN] 以下目录不存在，将跳过本地进程模式："
  for d in "${missing[@]}"; do
    echo "  - $d"
  done
  echo "如果你是在裸机调试，请确保 digitalhuman 仓库具备："
  echo "  ${PROJ_ROOT}/3rdparty/Open-LLM-VTuber"
  echo "  ${PROJ_ROOT}/digitalhuman_round_server"
fi

if command -v uv >/dev/null 2>&1; then
  # 用 uv 直接启动，临时环境自动解析依赖，无需系统 python/venv/pip
  exec uv run \
    --with fastapi>=0.110 \
    --with 'uvicorn[standard]>=0.29' \
    --with pydantic>=2.6 \
    --with requests>=2.31 \
    --with docker>=7.0 \
    --with PyYAML>=6.0 \
    uvicorn digitalhub_service:app --host 0.0.0.0 --port 9009
elif command -v python3 >/dev/null 2>&1; then
  # 兜底：直接用系统 python 跑（容器里已经预装依赖）
  exec python3 -m uvicorn digitalhub_service:app --host 0.0.0.0 --port 9009
else
  echo "未发现 uv 或 python3。请先安装 uv（推荐）或 python3。"
  exit 1
fi
