# 1.部署与启动
```bash
cd ~/work/digitalhub_service
./run_digitalhub.sh
```
会启动编排器：
```bash
snw@DESKTOP-SHDD92E:~/work/digitalhub_service$ ./run_digitalhub.sh
Installed 24 packages in 102ms
INFO:     Will watch for changes in these directories: ['/home/snw/work/digitalhub_service']
INFO:     Uvicorn running on http://127.0.0.1:9009 (Press CTRL+C to quit)
INFO:     Started reloader process [1389] using WatchFiles
INFO:     Started server process [1391]
INFO:     Waiting for application startup.
INFO:     Application startup complete.

```
# 2.单机测试
```bash
cd ~/work/digitalhub_service
./curl_test.sh
```
会返回：
```bash
snw@DESKTOP-SHDD92E:~/work/digitalhub_service$ ./curl_test.sh
[PING]
{
  "code": 200,
  "data": {
    "running": false
  }
}
[BOOT VTUBER]
{
  "code": 200,
  "data": {
    "session_id": "f0866a61-46bd-411a-a0f8-af98befd34da",
    "connect_url": "http://localhost:12393",
    "status": "ready",
    "message": "数字人已生成，生成面试题后可进入沉浸式面试：http://localhost:12393"
  }
}
[START LLM]
{
  "code": 200,
  "data": {
    "running": true,
    "base_url": "http://127.0.0.1:8011/v1"
  }
}
[STATUS]
{
  "code": 200,
  "data": {
    "vtuber": {
      "pid": 1449,
      "url": "http://localhost:12393",
      "alive": true
    },
    "llm": {
      "pid": 1470,
      "port": 8011,
      "alive": true
    }
  }
}
```
最好浏览器打开数字人网页进行一次问话看是否正常
# 3.面试官侧调用
首先按照**1.部署与启动**打开数字人编排器，然后先补一下面试官的后端环境变量再启动（记得其中miniIO每次重启机器要export一次）：
```bash
export DIGITALHUB_BASE="http://127.0.0.1:9009"

# MinIO —— 用你自己的真实值
export MINIO_ENDPOINT="test-minio.yeying.pub"
export MINIO_ACCESS_KEY="你的ACCESS_KEY"
export MINIO_SECRET_KEY="你的SECRET_KEY"
export MINIO_BUCKET="yeying-interviewer"
export MINIO_SECURE="true"   # http 就填 false

# LLM 端口（和 VTuber conf 里 openai_compatible_llm 指的保持一致）
export LLM_PORT="8011"

# 如果前端浏览器不在同一台机，给 digitalhub 指明可达 IP（否则它会返回 localhost）
# export PUBLIC_HOST="<你的服务器IP或域名>"

cd ~/work/lyz0921
source .venv/bin/activate
python app.py
```
会显示：
```bash
(lyz0921) snw@DESKTOP-SHDD92E:~/work/lyz0921$ python app.py
Database initialized successfully
✅ Database initialized
🚀 Starting Yeying Interviewer System...
 * Serving Flask app 'app'
 * Debug mode: on
WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:8080
 * Running on http://172.30.168.231:8080
Press CTRL+C to quit
 * Restarting with stat
Database initialized successfully
✅ Database initialized
🚀 Starting Yeying Interviewer System...
 * Debugger is active!
 * Debugger PIN: 442-183-967
```
可以访问面试官网站实测效果，点击创建面试间（或已有会话），会等待数字人有返回后才成功，然后立即有数字人网址。点击生成面试题，等待生成完成，展示第一个面试题，就可以复制刚刚返回的数字人网址进行沉浸式面试。随便说比如“你好”，数字人会开始问问题（理想情况会跟面试官中的第一题一样，否则应该会报错，要去log看错哪了）
# 4.排错
```bash
tail -n 200 -f ~/work/digitalhub_service/logs/vtuber.log
tail -n 200 -f ~/work/digitalhub_service/logs/llm.log
```
# 5.旧模块开发测试
### 5.1.1旧的单LLM启动验证：
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
### 5.1.2验证：
```bash
curl -N http://127.0.0.1:8011/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":[{"type":"text","text":"你好"}]}],"stream":true}'
```
