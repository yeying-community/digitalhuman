from typing import Any, Dict, Optional, List, Union, Generator
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import json
import time
import sys
import os
import re

from .state import RoundState
from .minio_adapter import MinioAdapter

router = APIRouter()

# Injected at startup
APP_STATE: Optional[RoundState] = None
MINIO: Optional[MinioAdapter] = None
UPLOAD_OBJECT_NAME: Optional[str] = None

# Track which question we last served to the client
LAST_SERVED_INDEX: int = -1  # -1 means we've never served any question yet

def log(*args):
    print("[round-server]", *args, file=sys.stdout, flush=True)

# === New: speak style switch ===
PURE_QUESTION: bool = os.getenv("PURE_QUESTION", "true").lower() in ("1", "true", "yes")
CAT_PREFIX_RE = re.compile(r"^\s*【[^】]+】\s*")

class ChatMessage(BaseModel):
    role: str
    # Accept OpenAI-style string or content-parts array [{'type':'text','text':'...'}, ...]
    content: Optional[Union[str, List[Dict[str, Any]]]] = None

class ChatCompletionsRequest(BaseModel):
    model: Optional[str] = Field(default="digitalhuman-round-server")
    messages: Optional[List[ChatMessage]] = None
    stream: Optional[bool] = False
    temperature: Optional[float] = None  # ignored

@router.get("/healthz")
def healthz():
    if APP_STATE is None:
        raise HTTPException(status_code=503, detail="Not initialized")
    return {
        "status": "ok",
        "mode": "minio",
        "session_id": APP_STATE.session_id,
        "round_index": APP_STATE.round_index,
        "current_index": APP_STATE.current_index,
        "total_questions": APP_STATE.total_questions,
        "last_served_index": LAST_SERVED_INDEX,
        "pure_question": PURE_QUESTION,
    }

def _extract_user_text(req: ChatCompletionsRequest) -> str:
    """
    From OpenAI-compatible messages, extract the last user text.
    Supports content: str or [{type:'text', text:'...'}]
    """
    if not req.messages:
        return ""
    text = ""
    for m in req.messages:
        if (m.role or "").lower() != "user":
            continue
        c = m.content
        if isinstance(c, str):
            text = c
        elif isinstance(c, list):
            parts = []
            for p in c:
                if isinstance(p, dict) and p.get("type") == "text":
                    t = p.get("text")
                    if isinstance(t, str):
                        parts.append(t)
            if parts:
                text = "".join(parts)
    return (text or "").strip()

def _wrap_openai_like(answer_text: str, st: RoundState) -> Dict[str, Any]:
    created_ts = int(time.time())
    return {
        "id": f"chatcmpl-{st.session_id}-{st.round_index}-{st.current_index}",
        "object": "chat.completion",
        "created": created_ts,
        "model": "digitalhuman-round-server",
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": answer_text},
            "finish_reason": "stop"
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": len(answer_text), "total_tokens": len(answer_text)},
        # Extra helpers
        "answer": answer_text,
        "question_number": (st.current_index + 1 if not st.is_completed() else st.total_questions),
        "total_questions": st.total_questions,
        "session_id": st.session_id,
        "round_index": st.round_index,
    }

def _sse_pack(data: Dict[str, Any]) -> str:
    return "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"

def _sse_done() -> str:
    return "data: [DONE]\n\n"

def _sse_stream_single(answer_text: str, st: RoundState) -> Generator[bytes, None, None]:
    """
    Minimal SSE: send one delta chunk + final [DONE].
    """
    created_ts = int(time.time())
    chunk_role = {
        "id": f"chatcmpl-{st.session_id}-{st.round_index}-{st.current_index}",
        "object": "chat.completion.chunk",
        "created": created_ts,
        "model": "digitalhuman-round-server",
        "choices": [{
            "index": 0,
            "delta": {"role": "assistant"},
            "finish_reason": None
        }]
    }
    yield _sse_pack(chunk_role).encode("utf-8")

    chunk_content = {
        "id": f"chatcmpl-{st.session_id}-{st.round_index}-{st.current_index}",
        "object": "chat.completion.chunk",
        "created": created_ts,
        "model": "digitalhuman-round-server",
        "choices": [{
            "index": 0,
            "delta": {"content": answer_text},
            "finish_reason": None
        }]
    }
    yield _sse_pack(chunk_content).encode("utf-8")

    done_chunk = {
        "id": f"chatcmpl-{st.session_id}-{st.round_index}-{st.current_index}",
        "object": "chat.completion.chunk",
        "created": created_ts,
        "model": "digitalhuman-round-server",
        "choices": [{
            "index": 0,
            "delta": {},
            "finish_reason": "stop"
        }]
    }
    yield _sse_pack(done_chunk).encode("utf-8")
    yield _sse_done().encode("utf-8")

def _build_question_text(q: Dict[str, Any]) -> str:
    """
    When PURE_QUESTION=True (default):
      - Do NOT add "问题 i/n" header
      - Strip leading category prefix like "【基础题】" from the question line
      - Return clean question text only
    When PURE_QUESTION=False:
      - Keep the old labeled style: header + original question
    """
    i = q["question_number"]
    n = q["total_questions"]
    cat = q.get("category")
    raw_q = q["question"] or ""
    if PURE_QUESTION:
        return CAT_PREFIX_RE.sub("", raw_q).strip()
    header = f"【{cat}】问题 {i}/{n}\n" if cat else f"问题 {i}/{n}\n"
    return header + raw_q

@router.post("/v1/chat/completions")
def chat_completions(req: ChatCompletionsRequest, bg: BackgroundTasks):
    global LAST_SERVED_INDEX
    if APP_STATE is None:
        raise HTTPException(status_code=503, detail="Not initialized")

    user_text = _extract_user_text(req)
    log(f"/v1/chat/completions stream={req.stream} user_text='{user_text[:50]+'...' if len(user_text)>50 else user_text}' "
        f"cur={APP_STATE.current_index} last_served={LAST_SERVED_INDEX} pure={PURE_QUESTION}")

    # 1) Already finished?
    if APP_STATE.is_completed():
        answer_text = "本轮问答已完成，感谢配合。"
        if req.stream:
            return StreamingResponse(_sse_stream_single(answer_text, APP_STATE),
                                     media_type="text/event-stream")
        return _wrap_openai_like(answer_text, APP_STATE)

    # 2) If we had served a question and user sent text, treat it as the answer to that question
    if user_text and LAST_SERVED_INDEX == APP_STATE.current_index:
        try:
            APP_STATE.save_answer(APP_STATE.current_index, user_text)
            log(f"Saved answer for q_index={APP_STATE.current_index}")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        if APP_STATE.is_completed():
            qa_complete = APP_STATE.build_qa_complete()
            if MINIO is None or UPLOAD_OBJECT_NAME is None:
                raise HTTPException(status_code=503, detail="MinIO not ready")
            MINIO.put_json(UPLOAD_OBJECT_NAME, qa_complete)
            log(f"Uploaded {UPLOAD_OBJECT_NAME}, shutting down soon...")
            final_text = "本轮问答已完成，感谢配合。"
            if req.stream:
                bg.add_task(_shutdown_after)
                return StreamingResponse(_sse_stream_single(final_text, APP_STATE),
                                         media_type="text/event-stream")
            bg.add_task(_shutdown_after)
            return _wrap_openai_like(final_text, APP_STATE)

        # fallthrough to serve next question

    # 3) Serve the current question
    q = APP_STATE.current_question_payload()
    if q is None:
        raise HTTPException(status_code=500, detail="No current question")
    answer_text = _build_question_text(q)

    LAST_SERVED_INDEX = APP_STATE.current_index  # mark served
    if req.stream:
        return StreamingResponse(_sse_stream_single(answer_text, APP_STATE),
                                 media_type="text/event-stream")
    return _wrap_openai_like(answer_text, APP_STATE)

def _shutdown_after():
    time.sleep(0.8)
    import os
    os._exit(0)

# ---- Manual endpoints kept for debugging ------------------------------------

class AnswerIn(BaseModel):
    question_index: Optional[int] = None
    answer_text: str

@router.post("/dh/answer")
def submit_answer(body: AnswerIn, bg: BackgroundTasks):
    global LAST_SERVED_INDEX
    if APP_STATE is None or MINIO is None or UPLOAD_OBJECT_NAME is None:
        raise HTTPException(status_code=503, detail="Not initialized")

    expected_idx = APP_STATE.current_index
    use_idx = expected_idx if body.question_index is None else body.question_index
    if use_idx != expected_idx:
        raise HTTPException(status_code=400, detail=f"Out-of-order answer: expected {expected_idx}, got {use_idx}")

    try:
        APP_STATE.save_answer(use_idx, body.answer_text)
        log(f"[manual] Saved answer for q_index={use_idx}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if APP_STATE.is_completed():
        qa_complete = APP_STATE.build_qa_complete()
        MINIO.put_json(UPLOAD_OBJECT_NAME, qa_complete)
        log(f"Uploaded {UPLOAD_OBJECT_NAME}, shutting down soon...")
        bg.add_task(_shutdown_after)
        return {"success": True, "is_round_completed": True, "uploaded": UPLOAD_OBJECT_NAME}

    LAST_SERVED_INDEX = APP_STATE.current_index
    return {"success": True, "is_round_completed": False, "next_question_number": APP_STATE.current_index + 1}

class SimpleAnswerIn(BaseModel):
    answer_text: str

@router.post("/dh/answer_simple")
def submit_answer_simple(body: SimpleAnswerIn, bg: BackgroundTasks):
    global LAST_SERVED_INDEX
    if APP_STATE is None or MINIO is None or UPLOAD_OBJECT_NAME is None:
        raise HTTPException(status_code=503, detail="Not initialized")

    try:
        APP_STATE.save_answer(APP_STATE.current_index, body.answer_text)
        log(f"[simple] Saved answer for q_index={APP_STATE.current_index-1}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if APP_STATE.is_completed():
        qa_complete = APP_STATE.build_qa_complete()
        MINIO.put_json(UPLOAD_OBJECT_NAME, qa_complete)
        log(f"Uploaded {UPLOAD_OBJECT_NAME}, shutting down soon...")
        bg.add_task(_shutdown_after)
        return {"success": True, "is_round_completed": True, "uploaded": UPLOAD_OBJECT_NAME}

    LAST_SERVED_INDEX = APP_STATE.current_index
    return {"success": True, "is_round_completed": False, "next_question_number": APP_STATE.current_index + 1}
