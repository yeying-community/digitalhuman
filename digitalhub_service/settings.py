from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_path(name: str, default: Path) -> Path:
    value = os.getenv(name)
    return Path(value).expanduser() if value else default


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


@dataclass(frozen=True)
class ServiceSettings:
    vtuber_image: str
    llm_image: str
    docker_network: str
    vtuber_internal_port: int
    llm_internal_port: int
    public_vtuber_host: str
    public_vtuber_scheme: str
    public_llm_host: str
    public_llm_scheme: str
    session_path_prefix: str
    vtuber_container_prefix: str
    llm_container_prefix: str
    session_idle_seconds: int
    session_max_age_seconds: int
    cleanup_interval_seconds: int
    vtuber_conf_template: Path
    log_dir: Path


def load_settings() -> ServiceSettings:
    vtuber_image = _env("VTUBER_IMAGE", "dh-vtuber:latest")
    llm_image = _env("LLM_IMAGE", "dh-llm-round:latest")
    docker_network = _env("DH_DOCKER_NETWORK", "dhnet")
    vtuber_internal_port = _env_int("VTUBER_PORT", 12393)
    llm_internal_port = _env_int("LLM_PORT", 8011)

    public_vtuber_host = _env("PUBLIC_VTUBER_HOST", _env("PUBLIC_HOST", "localhost"))
    public_vtuber_scheme = _env("PUBLIC_VTUBER_SCHEME", "https")
    public_llm_host = _env("PUBLIC_LLM_HOST", "localhost")
    public_llm_scheme = _env("PUBLIC_LLM_SCHEME", "http")

    prefix = _env("VTUBER_SESSION_PATH_PREFIX", "/s")
    if not prefix.startswith("/"):
        prefix = f"/{prefix}"
    prefix = prefix.rstrip("/") or "/s"

    vtuber_container_prefix = _env("VTUBER_CONTAINER_PREFIX", "dh-vtuber-")
    llm_container_prefix = _env("LLM_CONTAINER_PREFIX", "dh-llm-")

    session_idle_seconds = _env_int("SESSION_MAX_IDLE_SECONDS", 900)
    session_max_age_seconds = _env_int("SESSION_MAX_AGE_SECONDS", 7200)
    cleanup_interval_seconds = max(30, _env_int("SESSION_CLEANUP_INTERVAL", 60))

    vtuber_conf_template = _env_path(
        "VTUBER_CONF_TEMPLATE",
        (BASE_DIR.parent / "conf.prod.yaml").resolve(),
    )
    log_dir = _env_path("DH_LOG_DIR", (BASE_DIR / "logs").resolve())
    log_dir.mkdir(parents=True, exist_ok=True)

    return ServiceSettings(
        vtuber_image=vtuber_image,
        llm_image=llm_image,
        docker_network=docker_network,
        vtuber_internal_port=vtuber_internal_port,
        llm_internal_port=llm_internal_port,
        public_vtuber_host=public_vtuber_host,
        public_vtuber_scheme=public_vtuber_scheme,
        public_llm_host=public_llm_host,
        public_llm_scheme=public_llm_scheme,
        session_path_prefix=prefix,
        vtuber_container_prefix=vtuber_container_prefix,
        llm_container_prefix=llm_container_prefix,
        session_idle_seconds=session_idle_seconds,
        session_max_age_seconds=session_max_age_seconds,
        cleanup_interval_seconds=cleanup_interval_seconds,
        vtuber_conf_template=vtuber_conf_template,
        log_dir=log_dir,
    )
