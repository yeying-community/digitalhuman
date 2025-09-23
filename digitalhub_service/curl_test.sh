#!/usr/bin/env bash
set -euo pipefail
BASE="http://127.0.0.1:9009"


echo "[PING]" && curl -s "$BASE/api/v1/dh/ping" | jq
SID="f0866a61-46bd-411a-a0f8-af98befd34da"
RID="dc29ef90-c6d9-4293-a479-c8f24d77aed2"
echo "[BOOT VTUBER]" && curl -s -X POST "$BASE/api/v1/dh/boot" -H "Content-Type: application/json" -d "{\"room_id\":\"$RID\",\"session_id\":\"$SID\",\"timeout_sec\":90}" | jq
export MINIO_ENDPOINT="test-minio.yeying.pub"
export MINIO_ACCESS_KEY="zi3QOwIWYlu9JIpOeF0O"
export MINIO_SECRET_KEY="W4mAFU5tRU4FSvQKrY2up5XcJpAck2xkrqBt2giL"
export MINIO_BUCKET="yeying-interviewer"
export MINIO_SECURE="true"
echo "[START LLM]" && curl -s -X POST "$BASE/api/v1/dh/llm/start" -H "Content-Type: application/json" -d "{\"session_id\":\"$SID\",\"round_index\":0,\"port\":8011,\"minio_endpoint\":\"$MINIO_ENDPOINT\",\"minio_access_key\":\"$MINIO_ACCESS_KEY\",\"minio_secret_key\":\"$MINIO_SECRET_KEY\",\"minio_bucket\":\"$MINIO_BUCKET\",\"minio_secure\": true}" | jq
echo "[STATUS]" && curl -s "$BASE/api/v1/dh/status" | jq
# echo "[STOP]" && curl -s -X POST "$BASE/api/v1/dh/stop" | jq
