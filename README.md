# 部署与启动：
```bash
# 进入工程目录（你现在就在这儿就忽略）
cd ~/work/digitalhuman_round_server

# 1) Python 虚拟环境 & 依赖
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
chmod +x run.sh
export SESSION_ID="f0866a61-46bd-411a-a0f8-af98befd34da"
export ROUND_INDEX="0"

# MinIO 连接（按你们的实际环境）
export MINIO_ENDPOINT="test-minio.yeying.pub"   # 或 ip:9000
export MINIO_ACCESS_KEY="YOUR_MINIO_AK"
export MINIO_SECRET_KEY="YOUR_MINIO_SK"
export MINIO_BUCKET="yeying-interviewer"
export MINIO_SECURE="true"  # https=true; 如果走 http, 设为 false
# 服务端口（可选）
export PORT="8011"
./run.sh
```
# 验证：
```bash
curl -N http://127.0.0.1:8011/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":[{"type":"text","text":"你好"}]}],"stream":true}'
```
