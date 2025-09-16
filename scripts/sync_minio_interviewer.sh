#!/usr/bin/env bash
set -euo pipefail

# 目标本地目录（可传入第一个参数覆盖）
TARGET_DIR="${1:-$HOME/work/data/minio/yeying-interviewer}"

# 1) 确保目录存在
mkdir -p "$TARGET_DIR/data"

echo "[INFO] Mirroring yeying/yeying-interviewer/data -> $TARGET_DIR/data"

# 2) 仅镜像 data/ 这个前缀的所有对象
mc mirror --overwrite \
  yeying/yeying-interviewer/data "$TARGET_DIR/data"

# 3) （可选）只保留 .json 文件，删除其它非 .json 文件
# 注：如果你之后确认 data/ 下还有别的你要用的文件，就先不要删
# find "$TARGET_DIR/data" -type f ! -name "*.json" -delete
# find "$TARGET_DIR/data" -type d -empty -delete

echo "[OK] MinIO -> $TARGET_DIR 同步完成"
