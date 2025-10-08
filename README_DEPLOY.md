## 一次拉起
git clone https://github.com/yeying-community/digitalhuman.git
cd digitalhuman
cp .env.example .env   # 填好 PUBLIC_HOST / MINIO_*
# 拉上游数字人到占位目录
git clone https://github.com/Open-LLM-VTuber/Open-LLM-VTuber.git 3rdparty/

docker compose up -d --build

## 自检
curl -s http://127.0.0.1:9009/api/v1/dh/ping
# 期望：/boot 返回 connect_url=http://{PUBLIC_HOST}:12393；/llm/start 返回 base_url=http://{PUBLIC_HOST}:8011/v1
