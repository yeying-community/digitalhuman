## 部署概览

1. 克隆仓库并准备配置：
   ```bash
   git clone https://github.com/yeying-community/digitalhuman.git
   cd digitalhuman
   cp .env.example .env  # 按实际域名/MinIO 信息修改
   git clone https://github.com/Open-LLM-VTuber/Open-LLM-VTuber.git 3rdparty/Open-LLM-VTuber
   ```

2. 构建镜像：
   ```bash
   docker compose --profile images build
   ```
   - `vtuber-image` → 每个会话的数字人容器镜像
   - `llm-image` → LLM round server 镜像

3. 启动编排层与入口网关：
   ```bash
   docker compose up -d digitalhub gateway
   ```
   - `digitalhub` 暴露 `ORCH_PORT`（默认 9009），提供 `/api/v1/dh/*` API
   - `gateway` 暴露 `VTUBER_PORT`（默认 12393），通过路径 `/s/{session_slug}/` 反代到对应的数字人容器

4. 自检：
   ```bash
   curl -s http://127.0.0.1:9009/api/v1/dh/ping
   curl -s http://127.0.0.1:9009/api/v1/dh/status
   ```
   - `/boot` 会返回 `connect_url=https://{PUBLIC_VTUBER_HOST}/s/{session_slug}/`
   - `/llm/start` 会返回 `base_url=http(s)://{PUBLIC_LLM_HOST}:<host_port>/v1`

## API 使用示例

```bash
# 1. 启动数字人（会创建专属 VTuber 容器）
curl -X POST http://127.0.0.1:9009/api/v1/dh/boot \
     -H 'Content-Type: application/json' \
     -d '{
           "room_id": "demo-room",
           "session_id": "session-123",
           "public_host": "https://vtuber.example.com"
         }'

# 2. 启动对应会话/轮次的 LLM 容器
curl -X POST http://127.0.0.1:9009/api/v1/dh/llm/start \
     -H 'Content-Type: application/json' \
     -d '{
           "room_id": "demo-room",
           "session_id": "session-123",
           "round_index": 1,
           "minio_endpoint": "https://test-minio.yeying.pub",
           "minio_access_key": "...",
           "minio_secret_key": "...",
           "minio_bucket": "yeying-interviewer",
           "minio_secure": true
         }'
```

## 目录说明

- `digitalhub_service/`：FastAPI 编排服务（通过 Docker SDK 动态拉起 VTuber/LLM 容器）。
- `gateway/`：轻量 Nginx 反向代理，按 `/s/{session}` 路由到指定的 VTuber 容器。
- `digitalhuman_round_server/`：LLM Round Server（FastAPI），容器镜像由 `docker compose --profile images build` 生成。
- `3rdparty/Open-LLM-VTuber/`：上游数字人项目源代码，用于构建会话级 VTuber 镜像。

## 运行/调试小贴士

- `digitalhub` 容器需要挂载宿主机 `/var/run/docker.sock`，以便通过 Docker SDK 管理其他容器。
- `VTUBER_IMAGE` / `LLM_IMAGE` / `DH_DOCKER_NETWORK` 等均可在 `.env` 中覆盖。
- `SESSION_MAX_IDLE_SECONDS`、`SESSION_MAX_AGE_SECONDS` 控制自动清理策略，防止孤儿容器长期占用资源。
- `gateway` 只负责反代 WebSocket/HTTP 流量，LLM API 仍通过 `base_url` 暴露给 interviewer 端用于记录或调试。
- 如需查看日志，可使用 `GET /api/v1/dh/logs/{name}`（例如 `logs/vtuber.log`）。
