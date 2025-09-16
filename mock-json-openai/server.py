import os, json, time, asyncio
from pathlib import Path
from typing import List, Optional, Union, Dict, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import threading

# -------- 配置 --------
ANSWER_DIR = Path(os.getenv("ANSWER_DIR", str(Path.home() / "work/data/minio/yeying-interviewer/data")))
ANSWER_GLOB = os.getenv("ANSWER_GLOB", "questions_round_*.json")
ANSWER_SORT = os.getenv("ANSWER_SORT", "name")  # name | mtime
STREAM_CHUNK_SIZE = int(os.getenv("STREAM_CHUNK_SIZE", "50"))

# -------- 数据模型（兼容 OpenAI chat.completions 最小子集）--------
class ContentPart(BaseModel):
    type: str
    text: Optional[str] = None

class Message(BaseModel):
    role: str
    content: Union[str, List[ContentPart]]

class ChatCompletionRequest(BaseModel):
    model: Optional[str] = "mock-json"
    messages: List[Message]
    stream: Optional[bool] = False
    temperature: Optional[float] = None
    top_p: Optional[float] = None

# -------- 轻量文件队列（顺序取“下一份 JSON”）--------
class JsonAnswerFeeder:
    def __init__(self, root: Path, glob_pat: str, sort: str = "name"):
        self.root = root
        self.glob_pat = glob_pat
        self.sort = sort
        self.lock = threading.Lock()
        self.files: List[Path] = []
        self.idx = 0
        self.reload()

    def reload(self):
        if not self.root.exists():
            self.files = []
            self.idx = 0
            return
        files = list(self.root.glob(self.glob_pat))
        # 自动忽略 resume.json
        files = [f for f in files if f.name != "resume.json"]
        if self.sort == "mtime":
            files.sort(key=lambda p: p.stat().st_mtime)
        else:
            files.sort(key=lambda p: p.name)
        self.files = files
        self.idx = 0

    def status(self) -> Dict[str, Any]:
        current = self.files[self.idx % len(self.files)].name if self.files else None
        return {"count": len(self.files), "index": self.idx % len(self.files) if self.files else None, "current": current}

    def reset(self):
        with self.lock:
            self.idx = 0

    def next_path(self) -> Path:
        with self.lock:
            if not self.files:
                raise RuntimeError(f"No JSON files under: {self.root} (pattern={self.glob_pat})")
            p = self.files[self.idx % len(self.files)]
            self.idx += 1
            return p

    @staticmethod
    def load_json(p: Path) -> Any:
        data = None
        try:
            text = p.read_text(encoding="utf-8")
            data = json.loads(text)
        except Exception:
            # 不是合法 JSON，则用纯文本回传
            data = {"text": p.read_text(encoding="utf-8", errors="ignore")}
        return data

feeder = JsonAnswerFeeder(ANSWER_DIR, ANSWER_GLOB, ANSWER_SORT)

# -------- 从题目里构造可说文本（方案 2 的核心）--------
def collect_questions(payload: Any) -> List[str]:
    """尽最大可能把题目收集成一个字符串列表"""
    qs: List[str] = []

    if isinstance(payload, dict):
        # 1) 直接 questions: [...]
        if isinstance(payload.get("questions"), list):
            for x in payload["questions"]:
                if isinstance(x, str):
                    qs.append(x)
        # 2) categorized_questions: { 分组: [ ... ] }
        if isinstance(payload.get("categorized_questions"), dict):
            for _k, arr in payload["categorized_questions"].items():
                if isinstance(arr, list):
                    for x in arr:
                        if isinstance(x, str):
                            qs.append(x)
    elif isinstance(payload, list):
        # 少见：顶层就是一个列表
        for x in payload:
            if isinstance(x, str):
                qs.append(x)

    # 去重但保序
    seen = set()
    uniq = []
    for q in qs:
        if q not in seen:
            seen.add(q)
            uniq.append(q)
    return uniq

def make_answer_text(payload: Any) -> str:
    """把题目拼成一段可读文本：1. xxx\\n2. xxx..."""
    qs = collect_questions(payload)
    if not qs:
        # 如果没有题目，就把常见 answer/content/text/output 之一作为 fallback
        for k in ["answer", "content", "text", "output"]:
            if isinstance(payload, dict) and isinstance(payload.get(k), str) and payload[k].strip():
                return payload[k]
        # 最后兜底：把整个对象 JSON 化
        return json.dumps(payload, ensure_ascii=False)

    # 带序号的多行文本
    lines = [f"{i}. {q}" for i, q in enumerate(qs, 1)]
    return "\n".join(lines)

def ensure_answer_field(payload: Any) -> Dict[str, Any]:
    """保证返回体里一定有 'answer' 字段；不破坏原有自定义字段"""
    if isinstance(payload, dict):
        data = dict(payload)  # 浅拷贝
    else:
        data = {"raw": payload}

    # 若已有非空 answer，尊重它；否则从 questions 构造
    if not isinstance(data.get("answer"), str) or not data.get("answer").strip():
        data["answer"] = make_answer_text(data)

    return data

def chunker(s: str, n: int):
    for i in range(0, len(s), n):
        yield s[i:i+n]

# -------- FastAPI 应用 --------
app = FastAPI(title="Mock OpenAI from Local JSON (Scheme-2 Answer Injector)", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

@app.get("/healthz")
def healthz():
    return {"status": "ok", "time": int(time.time()), "dir": str(ANSWER_DIR)}

@app.get("/admin/files")
def list_files():
    return {"dir": str(ANSWER_DIR), "glob": ANSWER_GLOB, "sort": ANSWER_SORT, "files": [p.name for p in feeder.files]}

@app.get("/admin/cursor")
def cursor_status():
    return feeder.status()

@app.post("/admin/reset")
def cursor_reset():
    feeder.reset()
    return {"status": "reset", **feeder.status()}

# ----------------- 关键改动：返回“你那份 JSON + answer” -----------------
@app.post("/v1/chat/completions")
async def chat_completions(body: ChatCompletionRequest, request: Request):
    try:
        # 忽略 messages 内容，统一“按顺序吐下一个 JSON 的内容为回答”
        p = feeder.next_path()
        raw = feeder.load_json(p)
        data = ensure_answer_field(raw)  # 在原 JSON 基础上补上 answer

        if not body.stream:
            # 方案 2：直接返回你原来的 JSON（带上 answer），数字人会优先读 answer
            return JSONResponse(data)

        # 若要求流式，则把 answer 以 OpenAI chunk 格式逐片吐出（便于前端逐字播放）
        answer_text = data.get("answer", "")
        async def sse():
            for piece in chunker(answer_text, STREAM_CHUNK_SIZE):
                chunk = {
                    "id": "chatcmpl-mock-json",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": body.model or "mock-json",
                    "choices": [{"index": 0, "delta": {"content": piece}}]
                }
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.005)
            yield "data: [DONE]\n\n"

        return StreamingResponse(sse(), media_type="text/event-stream")

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": {"type": "server_error", "message": f"{type(e).__name__}: {e}"}}
        )

# -------- 调试用 WebSocket：每次 client 发任意消息 → 推一个“下一份 JSON（含 answer）”--------
@app.websocket("/debug-ws")
async def debug_ws(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            _ = await ws.receive_text()  # 内容忽略
            p = feeder.next_path()
            raw = feeder.load_json(p)
            data = ensure_answer_field(raw)
            await ws.send_text(json.dumps({"file": p.name, "payload": data}, ensure_ascii=False))
    except WebSocketDisconnect:
        pass
