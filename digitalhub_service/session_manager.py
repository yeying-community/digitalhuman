from __future__ import annotations

import hashlib
import io
import logging
import tarfile
import threading
import time
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

import docker
from docker.errors import APIError, NotFound
from docker.models.containers import Container
from docker.models.networks import Network

from .settings import ServiceSettings
from .vtuber_config import VtuberConfigRenderer

logger = logging.getLogger(__name__)


@dataclass
class BootPayload:
    room_id: Optional[str]
    session_id: str
    timeout_sec: int
    public_host: Optional[str]


@dataclass
class LLMStartPayload:
    room_id: str
    session_id: str
    round_index: int
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    minio_secure: bool
    port: Optional[int] = None


@dataclass
class ContainerInfo:
    name: str
    container_id: str
    internal_url: Optional[str] = None
    public_url: Optional[str] = None
    host_port: Optional[int] = None
    created_at: float = field(default_factory=time.time)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "container_id": self.container_id,
            "internal_url": self.internal_url,
            "public_url": self.public_url,
            "host_port": self.host_port,
            "created_at": self.created_at,
        }


@dataclass
class SessionState:
    session_id: str
    slug: str
    room_id: Optional[str]
    vtuber: Optional[ContainerInfo] = None
    llm: Optional[ContainerInfo] = None
    created_at: float = field(default_factory=time.time)
    last_access_at: float = field(default_factory=time.time)
    last_round_index: Optional[int] = None

    def touch(self) -> None:
        self.last_access_at = time.time()

    def summary(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "room_id": self.room_id,
            "vtuber": self.vtuber.as_dict() if self.vtuber else None,
            "llm": self.llm.as_dict() if self.llm else None,
            "created_at": self.created_at,
            "last_access_at": self.last_access_at,
            "last_round_index": self.last_round_index,
        }


class SessionManager:
    def __init__(self, settings: ServiceSettings):
        self.settings = settings
        self.client = docker.from_env()
        self.renderer = VtuberConfigRenderer(settings.vtuber_conf_template)
        self.lock = threading.RLock()
        self.sessions: Dict[str, SessionState] = {}
        self._stop_event = threading.Event()
        self._network: Optional[Network] = None
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, name="dh-session-gc", daemon=True)
        self._cleanup_thread.start()
        logger.info(
            "SessionManager initialized (network=%s, vtuber_image=%s, llm_image=%s)",
            settings.docker_network,
            settings.vtuber_image,
            settings.llm_image,
        )

    def ping(self) -> Dict[str, Any]:
        with self.lock:
            sessions = len(self.sessions)
        return {
            "running": True,
            "active_sessions": sessions,
            "message": "digitalhub orchestrator ready",
        }

    def boot_session(self, payload: BootPayload) -> Dict[str, Any]:
        session_id = payload.session_id.strip()
        if not session_id:
            raise ValueError("session_id 不能为空")
        slug = self._slug_for_session(session_id)
        with self.lock:
            state = self.sessions.get(session_id)
            if state and state.vtuber and self._container_alive(state.vtuber.container_id):
                state.room_id = state.room_id or payload.room_id
                state.touch()
                return self._boot_response(state, payload.public_host)

        vtuber = self._start_vtuber_container(session_id, slug, payload.room_id)
        with self.lock:
            state = self.sessions.setdefault(session_id, SessionState(session_id=session_id, slug=slug, room_id=payload.room_id))
            state.vtuber = vtuber
            state.room_id = state.room_id or payload.room_id
            state.touch()
        return self._boot_response(state, payload.public_host)

    def start_llm(self, payload: LLMStartPayload) -> Dict[str, Any]:
        session_id = payload.session_id.strip()
        if not session_id:
            raise ValueError("session_id 不能为空")
        with self.lock:
            state = self.sessions.get(session_id)
            if not state:
                slug = self._slug_for_session(session_id)
                state = SessionState(session_id=session_id, slug=slug, room_id=payload.room_id)
                self.sessions[session_id] = state
            else:
                slug = state.slug
                state.room_id = payload.room_id or state.room_id
            state.touch()
        llm = self._start_llm_container(payload, slug)
        with self.lock:
            state = self.sessions[session_id]
            state.llm = llm
            state.last_round_index = payload.round_index
            state.touch()
        return {
            "running": True,
            "session_id": session_id,
            "round_index": payload.round_index,
            "base_url": llm.public_url,
            "internal_url": llm.internal_url,
            "host_port": llm.host_port,
        }

    def status(self) -> Dict[str, Any]:
        with self.lock:
            sessions = [state.summary() for state in self.sessions.values()]
        return {"sessions": sessions, "total_sessions": len(sessions)}

    def stop_all(self) -> Dict[str, Any]:
        with self.lock:
            states = list(self.sessions.values())
            self.sessions.clear()
        stopped = 0
        for state in states:
            stopped += self._stop_session(state)
        return {"stopped_containers": stopped, "stopped_sessions": len(states)}

    def shutdown(self) -> None:
        self._stop_event.set()
        if self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5)
        self.stop_all()

    def _boot_response(self, state: SessionState, override_host: Optional[str]) -> Dict[str, Any]:
        url = self._build_vtuber_url(state.slug, override_host)
        tip = f"数字人已生成，打开链接进入面试：{url}"
        return {
            "session_id": state.session_id,
            "connect_url": url,
            "status": "ready",
            "message": tip,
        }

    def _start_vtuber_container(self, session_id: str, slug: str, room_id: Optional[str]) -> ContainerInfo:
        name = self._vtuber_name(slug)
        self._remove_if_exists(name)
        config_text = self.renderer.render(self._llm_internal_base(slug))
        env = {"SESSION_ID": session_id, "ROOM_ID": room_id or ""}
        container: Optional[Container] = None
        try:
            container = self.client.containers.create(
                image=self.settings.vtuber_image,
                name=name,
                hostname=name,
                detach=True,
                environment=env,
                labels=self._labels(session_id, role="vtuber"),
            )
            self._copy_into_container(container, "/app/conf.yaml", config_text.encode("utf-8"))
            container.start()
            self._connect_network(container, name)
            container.reload()
            logger.info("Started VTuber container %s for session %s", name, session_id)
        except Exception:
            if container is not None:
                with suppress(Exception):
                    container.remove(force=True)
            logger.exception("VTuber container boot failed for session %s", session_id)
            raise
        internal_url = f"http://{name}:{self.settings.vtuber_internal_port}/"
        return ContainerInfo(name=name, container_id=container.id, internal_url=internal_url, public_url=self._build_vtuber_url(slug, None))

    def _start_llm_container(self, payload: LLMStartPayload, slug: str) -> ContainerInfo:
        name = self._llm_name(slug)
        self._remove_if_exists(name)
        env = {
            "ROOM_ID": payload.room_id,
            "SESSION_ID": payload.session_id,
            "ROUND_INDEX": str(payload.round_index),
            "MINIO_ENDPOINT": payload.minio_endpoint,
            "MINIO_ACCESS_KEY": payload.minio_access_key,
            "MINIO_SECRET_KEY": payload.minio_secret_key,
            "MINIO_BUCKET": payload.minio_bucket,
            "MINIO_SECURE": "true" if payload.minio_secure else "false",
            "PORT": str(self.settings.llm_internal_port),
        }
        ports = {f"{self.settings.llm_internal_port}/tcp": payload.port or None}
        container = self._run_llm_container(name, env, ports)
        container.reload()
        self._connect_network(container, name)
        host_port = self._extract_host_port(container)
        public_url = self._build_llm_url(host_port)
        internal_url = f"http://{name}:{self.settings.llm_internal_port}/v1"
        logger.info(
            "Started LLM container %s for session %s (round %s, host_port=%s)",
            name,
            payload.session_id,
            payload.round_index,
            host_port,
        )
        return ContainerInfo(
            name=name,
            container_id=container.id,
            internal_url=internal_url,
            public_url=public_url,
            host_port=host_port,
        )

    def _run_llm_container(self, name: str, env: Dict[str, str], ports: Dict[str, Optional[int]]) -> Container:
        try:
            return self.client.containers.run(
                image=self.settings.llm_image,
                name=name,
                hostname=name,
                detach=True,
                environment=env,
                labels=self._labels(env.get("SESSION_ID", ""), role="llm", extra={"round": env.get("ROUND_INDEX", "0")}),
                ports=ports,
            )
        except APIError as exc:
            port_value = next(iter(ports.values()))
            key = next(iter(ports.keys()))
            msg = str(exc).lower()
            conflict = port_value and ("address already in use" in msg or "port is already allocated" in msg)
            if conflict:
                self._remove_if_exists(name)
                logger.warning("Requested host port %s already in use, falling back to random", port_value)
                return self.client.containers.run(
                    image=self.settings.llm_image,
                    name=name,
                    hostname=name,
                    detach=True,
                    environment=env,
                    labels=self._labels(env.get("SESSION_ID", ""), role="llm", extra={"round": env.get("ROUND_INDEX", "0")}),
                    ports={key: None},
                )
            raise

    def _labels(self, session_id: str, role: str, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        labels = {
            "digitalhub.session_id": session_id,
            "digitalhub.role": role,
        }
        if extra:
            labels.update({f"digitalhub.{k}": v for k, v in extra.items()})
        return labels

    def _stop_session(self, state: SessionState) -> int:
        stopped = 0
        stopped += self._stop_container(state.vtuber)
        stopped += self._stop_container(state.llm)
        return stopped

    def _stop_container(self, info: Optional[ContainerInfo]) -> int:
        if not info:
            return 0
        with suppress(NotFound):
            container = self.client.containers.get(info.container_id)
            with suppress(APIError):
                container.stop(timeout=10)
            with suppress(APIError):
                container.remove(force=True)
            logger.info("Stopped container %s", info.name)
            return 1
        return 0

    def _copy_into_container(self, container: Container, target: str, data: bytes) -> None:
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode="w") as tar:
            tarinfo = tarfile.TarInfo(name=target.lstrip("/"))
            tarinfo.size = len(data)
            tarinfo.mtime = time.time()
            tar.addfile(tarinfo, io.BytesIO(data))
        tar_stream.seek(0)
        container.put_archive(path="/", data=tar_stream.getvalue())

    def _connect_network(self, container: Container, alias: str) -> None:
        try:
            network = self._docker_network()
        except NotFound:
            logger.warning("Docker network %s 不存在，容器将使用默认网络", self.settings.docker_network)
            return
        try:
            network.connect(container, aliases=[alias])
        except APIError as exc:
            if "already exists" in str(exc).lower():
                return
            logger.warning("Failed to attach %s to network %s: %s", alias, self.settings.docker_network, exc)

    def _docker_network(self) -> Network:
        if self._network is None:
            self._network = self.client.networks.get(self.settings.docker_network)
        return self._network

    def _container_alive(self, container_id: str) -> bool:
        with suppress(NotFound):
            container = self.client.containers.get(container_id)
            container.reload()
            return container.status in ("running", "restarting")
        return False

    def _remove_if_exists(self, name: str) -> None:
        with suppress(NotFound):
            container = self.client.containers.get(name)
            with suppress(APIError):
                container.remove(force=True)
            logger.info("Removed stale container %s", name)

    def _extract_host_port(self, container: Container) -> Optional[int]:
        ports = container.attrs.get("NetworkSettings", {}).get("Ports", {})
        key = f"{self.settings.llm_internal_port}/tcp"
        entries = ports.get(key) or []
        if entries:
            try:
                return int(entries[0].get("HostPort"))
            except (TypeError, ValueError):
                return None
        return None

    def _build_vtuber_url(self, slug: str, override_host: Optional[str]) -> str:
        host = override_host or self.settings.public_vtuber_host
        base = self._normalize_base(host, self.settings.public_vtuber_scheme)
        path = f"{self.settings.session_path_prefix}/{slug}".replace("//", "/")
        if not path.endswith("/"):
            path += "/"
        return f"{base}{path}"

    def _build_llm_url(self, host_port: Optional[int]) -> str:
        base = self._normalize_base(self.settings.public_llm_host, self.settings.public_llm_scheme)
        parsed = urlsplit(base)
        netloc = parsed.netloc
        if host_port and ":" not in netloc:
            netloc = f"{netloc}:{host_port}"
        return f"{parsed.scheme}://{netloc}/v1"

    @staticmethod
    def _normalize_base(host: str, default_scheme: str) -> str:
        host = (host or "").strip()
        if host.startswith("http://") or host.startswith("https://"):
            parsed = urlsplit(host)
            scheme = parsed.scheme
            netloc = parsed.netloc
        else:
            scheme = default_scheme
            netloc = host
        return f"{scheme}://{netloc}".rstrip("/")

    def _vtuber_name(self, slug: str) -> str:
        return f"{self.settings.vtuber_container_prefix}{slug}"

    def _llm_name(self, slug: str) -> str:
        return f"{self.settings.llm_container_prefix}{slug}"

    def _llm_internal_base(self, slug: str) -> str:
        return f"http://{self._llm_name(slug)}:{self.settings.llm_internal_port}/v1"

    def _cleanup_loop(self) -> None:
        while not self._stop_event.wait(self.settings.cleanup_interval_seconds):
            stale: Dict[str, SessionState] = {}
            now = time.time()
            with self.lock:
                for session_id, state in list(self.sessions.items()):
                    idle = now - state.last_access_at
                    age = now - state.created_at
                    expired = idle > self.settings.session_idle_seconds or age > self.settings.session_max_age_seconds
                    dead_vtuber = state.vtuber and not self._container_alive(state.vtuber.container_id)
                    dead_llm = state.llm and not self._container_alive(state.llm.container_id)
                    if expired or (dead_vtuber and dead_llm):
                        stale[session_id] = state
                for session_id in stale:
                    self.sessions.pop(session_id, None)
            for state in stale.values():
                logger.info("Session %s expired, cleaning up", state.session_id)
                self._stop_session(state)

    @staticmethod
    def _slug_for_session(session_id: str) -> str:
        cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in session_id).strip("-")
        cleaned = cleaned[:40] if cleaned else "session"
        digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:6]
        return f"{cleaned}-{digest}"
