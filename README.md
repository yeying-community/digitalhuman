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

根据显示的log打开`http://localhost:12393/`就可以正常使用了

```bash
[INFO] Running in standard mode. For detailed debug logs, use: uv run run_server.py --verbose
2025-09-15 11:38:51 | INFO     | __main__:run:122 | Open-LLM-VTuber, version v1.2.1
2025-09-15 11:38:51 | INFO     | upgrade_codes.config_sync:backup_user_config:100 | Backing up conf.yaml to conf.yaml.backup
2025-09-15 11:38:52 | INFO     | __main__:run:149 | Initializing server context...
2025-09-15 11:38:52 | INFO     | src.open_llm_vtuber.service_context:init_live2d:315 | Initializing Live2D: mao_pro
2025-09-15 11:38:52 | INFO     | src.open_llm_vtuber.live2d_model:_lookup_model_info:142 | Model Information Loaded.
2025-09-15 11:38:52 | INFO     | src.open_llm_vtuber.service_context:init_asr:325 | Initializing ASR: sherpa_onnx_asr
2025-09-15 11:38:52 | INFO     | src.open_llm_vtuber.asr.sherpa_onnx_asr:__init__:81 | Sherpa-Onnx-ASR: Using cpu for inference
2025-09-15 11:39:03 | INFO     | src.open_llm_vtuber.service_context:init_tts:337 | Initializing TTS: edge_tts
2025-09-15 11:39:03 | INFO     | src.open_llm_vtuber.service_context:init_vad:349 | VAD is disabled.
2025-09-15 11:39:03 | INFO     | src.open_llm_vtuber.service_context:init_agent:366 | Initializing Agent: basic_memory_agent
2025-09-15 11:39:03 | INFO     | src.open_llm_vtuber.agent.agent_factory:create_agent:37 | Initializing agent: basic_memory_agent
2025-09-15 11:39:03 | INFO     | src.open_llm_vtuber.agent.stateless_llm_factory:create_llm:23 | Initializing LLM: openai_compatible_llm
2025-09-15 11:39:03 | INFO     | src.open_llm_vtuber.agent.stateless_llm.openai_compatible_llm:__init__:56 | Initialized AsyncLLM with the parameters: http://127.0.0.1:8000/v1, qwen-turbo
2025-09-15 11:39:03 | WARNING  | src.open_llm_vtuber.agent.agents.basic_memory_agent:__init__:108 | use_mcpp is False, but some MCP components were passed to the agent.
2025-09-15 11:39:03 | INFO     | src.open_llm_vtuber.agent.agents.basic_memory_agent:__init__:112 | BasicMemoryAgent initialized.
2025-09-15 11:39:03 | INFO     | __main__:run:152 | Server context initialized successfully.
2025-09-15 11:39:03 | INFO     | __main__:run:158 | Starting server on localhost:12393
```
log最后一行有server的地址
