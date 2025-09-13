# ~/work/tools/openai-gateway/main.py
import os, sys, asyncio, json, inspect
from typing import List, Optional, Literal, Dict, Any, Union
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

# 让 Python 找到同事项目（按你的路径）
COLLEAGUE_ROOT = os.path.expanduser(
    "~/work/company/yeying-interviewer/third_party/yeying-interviewer-main"
)
sys.path.append(COLLEAGUE_ROOT)

from llm.clients.qwen_client import QwenClient  # 同事项目里的客户端


# ---- OpenAI Chat Completions 最小请求体（兼容字符串与分片数组）----
class ContentPart(BaseModel):
    # 先兼容 text，其他类型先忽略；保留字段位以便后续扩展
    type: Literal["text", "image_url", "input_text"]
    text: Optional[str] = None
    image_url: Optional[Dict[str, Any]] = None


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    # 关键：既可字符串，也可 parts 数组
    content: Union[str, List[ContentPart]]


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = None
    messages: List[Message]
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.9
    stream: Optional[bool] = False


app = FastAPI(title="OpenAI-Compatible Gateway", version="0.1.0")


def _safe_call_chat(client, messages, **maybe_kwargs):
    """按 chat_completion 的真实签名过滤参数后再调用"""
    fn = getattr(client, "chat_completion")
    sig = inspect.signature(fn)
    valid = {k: v for k, v in maybe_kwargs.items() if k in sig.parameters}
    return fn(messages, **valid)


def _qwen_client(model: Optional[str]):
    """
    构造 QwenClient，并兼容不同实现的构造签名：
    - 优先尝试 (api_key=None, model_name=model)
    - 如果 TypeError（不收 model_name 等），回退到无参构造
    """
    try:
        return QwenClient(api_key=None, model_name=model)
    except TypeError:
        return QwenClient()


def _normalize_messages(msgs: List[Message]) -> List[Dict[str, Any]]:
    """
    将多模态 content 归一化为纯文本（仅拼接 text 分片；其他类型先忽略）
    """
    norm: List[Dict[str, Any]] = []
    for m in msgs:
        if isinstance(m.content, str):
            text = m.content
        else:
            # 数组形式：拼接其中的 text 分片，其他类型先忽略
            text = "".join([p.text or "" for p in m.content if getattr(p, "type", None) == "text"])
        norm.append({"role": m.role, "content": text})
    return norm


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest, request: Request):
    """
    OpenAI 兼容的 /v1/chat/completions
    - 非流式：一次性返回 choices[0].message.content
    - 流式：SSE data: 行输出 delta.content
    """
    client = _qwen_client(req.model)

    try:
        # 统一把 messages 归一化为纯文本，避免 422
        msgs = _normalize_messages(req.messages)

        if not req.stream:
            # 使用安全调用，自动过滤对方不支持的 kwargs（如 top_p）
            result: Dict[str, Any] = _safe_call_chat(
                client,
                msgs,  # 用归一化后的
                temperature=req.temperature,
                top_p=req.top_p,
            )
            # 如果对方已是 openai 风格，直接透传
            if isinstance(result, dict) and "choices" in result and "id" in result:
                return JSONResponse(result)

            # 兜底：把常见字段包成 openai 结构
            text = (
                result.get("choices", [{}])[0].get("message", {}).get("content")
                if isinstance(result, dict)
                else None
            )
            if not text and isinstance(result, dict):
                text = result.get("text") or result.get("output") or ""
            elif not text:
                text = str(result)  # 极端兜底

            payload = {
                "id": "chatcmpl-local",
                "object": "chat.completion",
                "created": int(os.times().elapsed),
                "model": req.model or "qwen-turbo",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": text},
                        "finish_reason": "stop",
                    }
                ],
                "usage": (result.get("usage", {}) if isinstance(result, dict) else {}),
            }
            return JSONResponse(payload)

        # ---- 流式输出（SSE）----
        async def sse_generator():
            # 同样使用安全调用
            result = _safe_call_chat(
                client,
                msgs,  # 用归一化后的
                temperature=req.temperature,
                top_p=req.top_p,
            )
            if isinstance(result, dict):
                text = (
                    result.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content")
                    or result.get("text")
                    or result.get("output")
                    or ""
                )
            else:
                text = str(result)  # 极端兜底

            for chunk in _chunk_text(text, 30):
                data = {
                    "id": "chatcmpl-local",
                    "object": "chat.completion.chunk",
                    "choices": [{"index": 0, "delta": {"content": chunk}}],
                }
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.01)
            # 结束标记
            yield "data: [DONE]\n\n"

        return StreamingResponse(sse_generator(), media_type="text/event-stream")

    except Exception as e:
        # 友好的 OpenAI 风格错误对象，便于排查
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "type": "server_error",
                    "message": f"{type(e).__name__}: {e}",
                }
            },
        )


def _chunk_text(s: str, n: int):
    for i in range(0, len(s), n):
        yield s[i : i + n]
