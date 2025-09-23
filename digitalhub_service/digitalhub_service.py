from __future__ import annotations
import os, re, time, socket, threading, subprocess
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# —— 路径（按你的机器） ——
VTUBER_ROOT = os.getenv("VTUBER_ROOT", os.path.expanduser("~/work/3rdparty/Open-LLM-VTuber"))
LLM_SERVER_ROOT = os.getenv("LLM_SERVER_ROOT", os.path.expanduser("~/work/digitalhuman_round_server"))
PUBLIC_HOST = os.getenv("PUBLIC_HOST", "localhost")

UVICORN_READY_RE = re.compile(r"Uvicorn running on (https?://[^\s]+)")
VTUBER_PORT_LINE_RE = re.compile(r"Starting server on (?:localhost|127\.0\.0\.1):(\d+)")

class BootRequest(BaseModel):
    room_id: Optional[str] = None
    session_id: Optional[str] = None
    timeout_sec: int = 90
    public_host: Optional[str] = None

class BootResponse(BaseModel):
    code: int
    data: Dict[str, Any]

class LLMStartRequest(BaseModel):
    session_id: str
    round_index: int
    port: int = 8011
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    minio_secure: bool = True

class SimpleResponse(BaseModel):
    code: int
    data: Dict[str, Any]

@dataclass
class ProcInfo:
    name: str
    popen: subprocess.Popen
    url: Optional[str] = None
    started_at: float = field(default_factory=time.time)
    extra: Dict[str, Any] = field(default_factory=dict)

class ProcManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.vtuber: Optional[ProcInfo] = None
        self.llm: Optional[ProcInfo] = None

    @staticmethod
    def _port_open(host: str, port: int, timeout: float = 0.25) -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except Exception:
            return False

    @staticmethod
    def _replace_host(url: str, new_host: str) -> str:
        return re.sub(r"(https?://)([^/:]+)(:\d+)?", lambda m: f"{m.group(1)}{new_host}{m.group(3) or ''}", url, count=1)

    @staticmethod
    def _host_port_from_url(url: str) -> tuple[str, int]:
        m = re.match(r"https?://([^/:]+)(?::(\d+))?", url)
        if not m:
            raise ValueError(f"bad url: {url}")
        host = m.group(1)
        port = int(m.group(2) or 80)
        return host, port

    # —— VTuber —— 
    def ping_vtuber(self) -> Dict[str, Any]:
        with self.lock:
            if self.vtuber and self.vtuber.url:
                url = self.vtuber.url
                try:
                    host, port = self._host_port_from_url(url)
                    alive = self._port_open(host, port)
                except Exception:
                    alive = False
                return {"running": alive, "connect_url": url}
            return {"running": False}

    def boot_vtuber(self, timeout_sec: int = 90, public_host: Optional[str] = None) -> str:
        with self.lock:
            if self.vtuber and self.vtuber.url:
                return self.vtuber.url
            popen = subprocess.Popen(
                ["uv", "run", "run_server.py"],
                cwd=VTUBER_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            proc = ProcInfo(name="vtuber", popen=popen)
            self.vtuber = proc

        ready_url = None
        detected_port: Optional[int] = None
        start = time.time()
        while time.time() - start < timeout_sec:
            line = proc.popen.stdout.readline()
            if not line:
                if proc.popen.poll() is not None:
                    break
                time.sleep(0.05)
                continue
            m1 = UVICORN_READY_RE.search(line)
            if m1:
                ready_url = m1.group(1)
                break
            m2 = VTUBER_PORT_LINE_RE.search(line)
            if m2:
                detected_port = int(m2.group(1))
        if not ready_url and detected_port and self._port_open("127.0.0.1", detected_port):
            ready_url = f"http://localhost:{detected_port}"
        if not ready_url:
            with self.lock:
                try: proc.popen.terminate()
                except Exception: pass
                self.vtuber = None
            raise RuntimeError("VTuber server boot timeout or failed to detect ready URL")
        url = self._replace_host(ready_url, public_host or PUBLIC_HOST)
        with self.lock:
            proc.url = url
        return url

    # —— LLM Round Server —— 
    def start_llm(self, req: LLMStartRequest) -> Dict[str, Any]:
        env = os.environ.copy()
        env.update({
            "SESSION_ID": req.session_id,
            "ROUND_INDEX": str(req.round_index),
            "MINIO_ENDPOINT": req.minio_endpoint,
            "MINIO_ACCESS_KEY": req.minio_access_key,
            "MINIO_SECRET_KEY": req.minio_secret_key,
            "MINIO_BUCKET": req.minio_bucket,
            "MINIO_SECURE": "true" if req.minio_secure else "false",
            "PORT": str(req.port),
        })
        with self.lock:
            if self.llm:
                try: self.llm.popen.terminate()
                except Exception: pass
                self.llm = None
            popen = subprocess.Popen(
                ["bash", "./run.sh"],
                cwd=LLM_SERVER_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
            )
            proc = ProcInfo(name="llm", popen=popen, extra={"port": req.port})
            self.llm = proc
        start = time.time()
        while time.time() - start < 25:
            if self._port_open("127.0.0.1", req.port):
                return {"running": True, "base_url": f"http://127.0.0.1:{req.port}/v1"}
            time.sleep(0.25)
        return {"running": False, "base_url": f"http://127.0.0.1:{req.port}/v1", "message": "port not open within 25s"}

    def status(self) -> Dict[str, Any]:
        with self.lock:
            data: Dict[str, Any] = {"vtuber": None, "llm": None}
            if self.vtuber:
                data["vtuber"] = {"pid": self.vtuber.popen.pid, "url": self.vtuber.url, "alive": (self.vtuber.popen.poll() is None)}
            if self.llm:
                data["llm"] = {"pid": self.llm.popen.pid, "port": self.llm.extra.get("port"), "alive": (self.llm.popen.poll() is None)}
            return data

    def stop_all(self) -> Dict[str, Any]:
        with self.lock:
            for attr in ("vtuber", "llm"):
                proc = getattr(self, attr)
                if proc:
                    try:
                        proc.popen.terminate()
                        try: proc.popen.wait(timeout=3)
                        except Exception: proc.popen.kill()
                    except Exception:
                        pass
                    setattr(self, attr, None)
        return {"stopped": True}

manager = ProcManager()
app = FastAPI(title="digitalhub", version="0.2.0")

@app.get("/api/v1/dh/ping", response_model=SimpleResponse)
def ping_dh():
    return {"code": 200, "data": manager.ping_vtuber()}

@app.post("/api/v1/dh/boot", response_model=BootResponse)
def boot_dh(req: BootRequest):
    try:
        url = manager.boot_vtuber(timeout_sec=req.timeout_sec, public_host=req.public_host)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    tip = f"数字人已生成，生成面试题后可进入沉浸式面试：{url}"
    return {"code": 200, "data": {"session_id": req.session_id, "connect_url": url, "status": "ready", "message": tip}}

@app.post("/api/v1/dh/llm/start", response_model=SimpleResponse)
def start_llm(req: LLMStartRequest):
    return {"code": 200, "data": manager.start_llm(req)}

@app.get("/api/v1/dh/status", response_model=SimpleResponse)
def status():
    return {"code": 200, "data": manager.status()}

@app.post("/api/v1/dh/stop", response_model=SimpleResponse)
def stop_all():
    return {"code": 200, "data": manager.stop_all()}

