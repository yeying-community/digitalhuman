核心代码在/mock-json-openai目录下，主要是提取miniIO上的json，不论接到什么，都按顺序返回json的回答，但由于json格式没有文档中的关键字，所以提取quesion或后面分类字典字段中的问题去重后放到answer字段方便数字人朗读
#使用方法：
```bash
uvicorn server:app --reload --host 0.0.0.0 --port 8001
```

#测试：
```bash
curl -s http://127.0.0.1:8001/healthz
curl -s -X POST http://127.0.0.1:8001/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"mock-json","messages":[{"role":"user","content":"hi"}]}'
```
会返回
```bash
@DESKTOP-SHDD92E:~$ curl -s http://127.0.0.1:8001/healthz
{"status":"ok","time":1758043291,"dir":"/home/snw/work/data/minio/yeying-interviewer/data"}
(.venv) snw@DESKTOP-SHDD92E:~$ curl -s -X POST http://127.0.0.1:8001/v1/chat/completions \
>   -H 'Content-Type: application/json' \
>   -d '{"model":"mock-json","messages":[{"role":"user","content":"hi"}]}'
{"questions":["【基础题】在使用LangChain框架开发Agent时，如何实现多Agent之间的状态共享与通信？","【基础题】请解释在RAG技术中，向量数据库（如Chroma或Weaviate）是如何通过embedding模型进行相似度检索的？","【基础题】在多Agent代码生成平台中，如何设计一个高效的代码评审Agent来检测代码质量和安全问题？","【项目题】在智能客服Agent系统中，你是如何设计和实现Agent记忆机制以支持长对话上下文维护的？","【项目题】多Agent代码生成平台中，如何确保不同Agent之间的协作效率和任务分发的准确性？","【项目题】在企业知识管理Agent助手中，你是如何利用RAG技术提升知识检索准确率并处理多语言文档的？","【场景题】在智能客服Agent系统中，你提到设计了Agent记忆机制以支持长对话上下文维护，如果遇到高并发场景下内存占用过高导致性能下降，你会如何优化该机制？","【场景题】在多Agent代码生成平台中，你使用了MetaGPT进行多Agent协作，如果在实际部署中发现不同Agent之间的任务调度效率低下，你会从哪些方面进行技术决策和性能优化？","【场景题】在企业知识管理Agent助手项目中，你通过RAG技术提升了知识检索准确率，如果后续需要支持实时更新的企业文档并保持检索效果，你会如何设计数据更新和索引同步方案？"],"round_index":0,"total_count":9,"generated_at":"2025-09-07T19:44:04.756670","answer":"1. 【基础题】在使用LangChain框架开发Agent时，如何实现多Agent之间的状态共享与通信？\n2. 【基础题】请解释在RAG技术中，向量数据库（如Chroma或Weaviate）是如何通过embedding模型进行相似度检索的？\n3. 【基础题】在多Agent代码生成平台中，如何设计一个高效的代码评审Agent来检测代码质量和安全问题？\n4. 【项目题】在智能客服Agent系统中，你是如何设计和实现Agent记忆机制以支持长对话上下文维护的？\n5. 【项目题】多Agent代码生成平台中，如何确保不同Agent之间的协作效率和任务分发的准确性？\n6. 【项目题】在企业知识管理Agent助手中，你是如何利用RAG技术提升知识检索准确率并处理多语言文档的？\n7. 【场景题】在智能客服Agent系统中，你提到设计了Agent记忆机制以支持长对话上下文维护，如果遇到高并发场景下内存占用过高导致性能下降，你会如何优化该机制？\n8. 【场景题】在多Agent代码生成平台中，你使用了MetaGPT进行多Agent协作，如果在实际部署中发现不同Agent之间的任务调度效率低下，你会从哪些方面进行技术决策和性能优化？\n9. 【场景题】在企业知识管理Agent助手项目中，你通过RAG技术提升了知识检索准确率，如果后续需要支持实时更新的企业文档并保持检索效果，你会如何设计数据更新和索引同步方案？"}(.venv) 
```

数字人conf相应部分主要改为：
```yaml
        llm_provider: 'openai_compatible_llm' # 使用的 LLM 提供商
...
      openai_compatible_llm:
        base_url: 'http://127.0.0.1:8001/v1' # 基础 URL
        llm_api_key: 'sk-local-placeholder' # API 密钥
        organization_id: null # 组织 ID
        project_id: null # 项目 ID
        model: 'qwen-turbo' # 使用的模型
        temperature: 1.0 # 温度，介于 0 到 2 之间
        interrupt_method: 'user'
```
特别是其中的URL端口8001要根据crul通的来填

#调用：
```bash
~/work/3rdparty/Open-LLM-VTuber$ uv run run_server.py
```
数字人会自动调用并朗读其中answer部分
