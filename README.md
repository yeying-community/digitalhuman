启动方式：

```bash
source ~/work/tools/openai-gateway/.venv/bin/activate
export BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
export MODEL_NAME="qwen-turbo"   # 或你在用的具体模型，例如 qwen2.5-7b-instruct 等
export API_KEY="sk-a9c6283a936d4dde847a8e247c4dcb92"
uvicorn main:app --host 0.0.0.0 --port 8000
```

新开一个终端验证：

```bash
curl -sS http://127.0.0.1:8000/v1/chat/completions \
-H 'Content-Type: application/json' \
-d '{"model":"qwen-turbo","messages":[{"role":"user","content":"你好，用一句话自我介绍。"}]}'
```

然后根据[数字人安装文档](https://docs.llmvtuber.com/docs/quick-start)部署数字人，最后运行（注意改成实际安装路径）：

```bash
snw@DESKTOP-SHDD92E:~/work/3rdparty/Open-LLM-VTuber$ uv run run_server.py
```

就可以正常使用了
