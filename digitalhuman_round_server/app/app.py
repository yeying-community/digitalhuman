from fastapi import FastAPI
from typing import Any, Dict
from .config import settings
from .minio_adapter import MinioAdapter
from .loader import extract_questions
from .state import RoundState
from . import dh_gateway

QUESTIONS_OBJECT_TPL = "data/questions_round_{round}_{session}.json"
QA_COMPLETE_OBJECT_TPL = "analysis/qa_complete_{round}_{session}.json"

app = FastAPI(title="digitalhuman-round-server", version="0.1.0")

@app.on_event("startup")
def on_startup():
    # 1) Init MinIO
    minio = MinioAdapter(
        endpoint=settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
        bucket=settings.MINIO_BUCKET,
    )

    # 2) Load questions JSON from MinIO (strict; no local fallback)
    questions_object = QUESTIONS_OBJECT_TPL.format(
        round=settings.ROUND_INDEX, session=settings.SESSION_ID
    )
    payload: Dict[str, Any] = minio.get_json(questions_object)

    # 3) Extract questions + categories
    questions, categories = extract_questions(payload)
    if not questions:
        raise RuntimeError(f"No questions found in {questions_object}")

    # 4) Round meta (prefer JSON, fallback to env)
    round_id = payload.get("round_id") or settings.ROUND_ID
    session_name = payload.get("session_name") or settings.SESSION_NAME
    room_id = payload.get("room_id") or settings.ROOM_ID
    round_type = payload.get("round_type") or settings.ROUND_TYPE

    # 5) Build in-memory state
    st = RoundState.create(
        session_id=settings.SESSION_ID,
        round_index=settings.ROUND_INDEX,
        round_id=round_id,
        round_type=round_type,
        session_name=session_name,
        room_id=room_id,
        questions=questions,
        categories=categories,
    )

    # 6) Bind into router singletons
    dh_gateway.APP_STATE = st
    dh_gateway.MINIO = minio
    dh_gateway.UPLOAD_OBJECT_NAME = QA_COMPLETE_OBJECT_TPL.format(
        round=settings.ROUND_INDEX, session=settings.SESSION_ID
    )

    # 7) Mount routes
    app.include_router(dh_gateway.router)

@app.get("/")
def root():
    return {"service": "digitalhuman-round-server", "status": "ready"}
