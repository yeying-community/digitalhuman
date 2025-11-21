from __future__ import annotations

import copy
import logging
from pathlib import Path
from threading import RLock
from typing import Any, Dict

import yaml

logger = logging.getLogger(__name__)


class VtuberConfigRenderer:
    def __init__(self, template_path: Path):
        self.template_path = Path(template_path)
        self._lock = RLock()
        self._template = self._load()

    def _load(self) -> Dict[str, Any]:
        if not self.template_path.exists():
            raise FileNotFoundError(f"VTuber 配置模板不存在: {self.template_path}")
        with self.template_path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        logger.info("Loaded VTuber config template from %s", self.template_path)
        return data

    def reload(self) -> None:
        with self._lock:
            self._template = self._load()

    def render(self, llm_base_url: str) -> str:
        with self._lock:
            cfg = copy.deepcopy(self._template)
        self._ensure_nested(
            cfg,
            ["character_config", "agent_config", "llm_configs", "openai_compatible_llm"],
            "base_url",
            llm_base_url,
        )
        return yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False)

    @staticmethod
    def _ensure_nested(root: Dict[str, Any], path: list[str], key: str, value: Any) -> None:
        cursor: Dict[str, Any] = root
        for name in path:
            cursor = cursor.setdefault(name, {})
        cursor[key] = value
