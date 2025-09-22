import os
from typing import Optional

def get_env_str(name: str, default: Optional[str]=None, required: bool=False) -> str:
    v = os.getenv(name, default)
    if required and (v is None or v == ""):
        raise RuntimeError(f"Missing required env: {name}")
    return v

class Settings:
    # --- Required for this one-shot run ---
    SESSION_ID: str
    ROUND_INDEX: int

    # --- MinIO ---
    MINIO_ENDPOINT: str
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET: str
    MINIO_SECURE: bool

    # --- Optional meta carried into qa_complete ---
    ROUND_ID: Optional[str]
    SESSION_NAME: Optional[str]
    ROOM_ID: Optional[str]
    ROUND_TYPE: Optional[str] = "ai_generated"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = int(os.getenv("PORT", "8011"))

    def __init__(self) -> None:
        self.SESSION_ID   = get_env_str("SESSION_ID", required=True)
        self.ROUND_INDEX  = int(get_env_str("ROUND_INDEX", required=True))

        self.MINIO_ENDPOINT   = get_env_str("MINIO_ENDPOINT", required=True)  # e.g. test-minio.yeying.pub
        self.MINIO_ACCESS_KEY = get_env_str("MINIO_ACCESS_KEY", required=True)
        self.MINIO_SECRET_KEY = get_env_str("MINIO_SECRET_KEY", required=True)
        self.MINIO_BUCKET     = get_env_str("MINIO_BUCKET", required=True)
        self.MINIO_SECURE     = get_env_str("MINIO_SECURE", "true").lower() in ("1","true","yes")

        # Optional extras (if known at start)
        self.ROUND_ID     = get_env_str("ROUND_ID", None)
        self.SESSION_NAME = get_env_str("SESSION_NAME", None)
        self.ROOM_ID      = get_env_str("ROOM_ID", None)
        self.ROUND_TYPE   = get_env_str("ROUND_TYPE", self.ROUND_TYPE)

settings = Settings()
