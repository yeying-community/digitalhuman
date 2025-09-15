启动方式：
'''
source ~/work/tools/openai-gateway/.venv/bin/activate
export BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
export MODEL_NAME="qwen-turbo"   # 或你在用的具体模型，例如 qwen2.5-7b-instruct 等
export API_KEY="sk-a9c6283a936d4dde847a8e247c4dcb92"
uvicorn main:app --host 0.0.0.0 --port 8000
'''

新开一个中断验证：
'''
curl -sS http://127.0.0.1:8000/v1/chat/completions \
-H 'Content-Type: application/json' \
-d '{"model":"qwen-turbo","messages":[{"role":"user","content":"你好，用一句话自我介绍。"}]}'
'''

