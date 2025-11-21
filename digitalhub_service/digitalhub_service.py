from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from .session_manager import BootPayload, LLMStartPayload, SessionManager
from .settings import load_settings

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

settings = load_settings()
manager = SessionManager(settings)
app = FastAPI(title="digitalhub", version="0.4.0")
LOG_DIR = Path(settings.log_dir)


class BootRequest(BaseModel):
    room_id: str | None = None
    session_id: str
    timeout_sec: int = 60
    public_host: str | None = None


class BootResponse(BaseModel):
    code: int
    data: Dict[str, Any]


class LLMStartRequest(BaseModel):
    room_id: str
    session_id: str
    round_index: int
    port: int | None = None
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    minio_secure: bool = True


class SimpleResponse(BaseModel):
    code: int
    data: Dict[str, Any]


@app.get("/api/v1/dh/ping", response_model=SimpleResponse)
def ping_dh() -> Dict[str, Any]:
    return {"code": 200, "data": manager.ping()}


@app.post("/api/v1/dh/boot", response_model=BootResponse)
def boot_dh(req: BootRequest) -> Dict[str, Any]:
    try:
        payload = BootPayload(**req.model_dump())
        data = manager.boot_session(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - best effort logging
        logger.exception("boot_dh failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"code": 200, "data": data}


@app.post("/api/v1/dh/llm/start", response_model=SimpleResponse)
def start_llm(req: LLMStartRequest) -> Dict[str, Any]:
    try:
        payload = LLMStartPayload(**req.model_dump())
        data = manager.start_llm(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("start_llm failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"code": 200, "data": data}


@app.get("/api/v1/dh/status", response_model=SimpleResponse)
def status() -> Dict[str, Any]:
    return {"code": 200, "data": manager.status()}


@app.post("/api/v1/dh/stop", response_model=SimpleResponse)
def stop_all() -> Dict[str, Any]:
    return {"code": 200, "data": manager.stop_all()}


def _tail_file(path: Path, lines: int) -> str:
    if not path.exists():
        return "(no log yet)"
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        block = 1024
        data = bytearray()
        while size > 0 and lines >= 0:
            step = min(block, size)
            size -= step
            handle.seek(size)
            chunk = handle.read(step)
            data[:0] = chunk
            lines -= chunk.count(b"\n")
            if lines <= 0:
                break
    return data.decode("utf-8", errors="ignore")


@app.get("/api/v1/dh/logs/{name}", response_model=SimpleResponse)
def read_logs(name: str, lines: int = Query(200, ge=1, le=5000)) -> Dict[str, Any]:
    file_path = LOG_DIR / f"{name}.log"
    content = _tail_file(file_path, lines)
    return {
        "code": 200,
        "data": {"file": str(file_path), "lines": lines, "content": content},
    }


@app.on_event("shutdown")
def _shutdown() -> None:
    manager.shutdown()
