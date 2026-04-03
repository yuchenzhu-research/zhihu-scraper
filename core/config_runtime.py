"""
config_runtime.py - Runtime config loading and singleton access.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

import yaml

from .config_schema import Config, build_config_from_dict, build_default_config
from .logging_setup import setup_logging
from .project_paths import get_project_root
from .structlog_compat import structlog


class ConfigLoader:
    """Configuration loader supporting defaults and singleton caching."""

    _instance: Optional["ConfigLoader"] = None
    _config: Optional[Config] = None

    def __new__(cls) -> "ConfigLoader":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

    def load(
        self,
        config_path: Optional[Union[str, Path]] = None,
        *,
        override_level: Optional[str] = None,
    ) -> Config:
        if self._config is not None:
            return self._config

        resolved_path = Path(config_path) if config_path is not None else get_project_root() / "config.yaml"

        if not resolved_path.exists():
            self._log_missing_config(resolved_path)
            self._config = self._finalize_config(build_default_config(), override_level=override_level)
            return self._config

        try:
            with open(resolved_path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}

            self._config = self._finalize_config(
                build_config_from_dict(raw),
                override_level=override_level,
            )
            return self._config
        except Exception as e:
            print(f"⚠️ Configuration file load failed: {e}")
            print("  Using default configuration / 使用默认配置")
            self._config = self._finalize_config(build_default_config(), override_level=override_level)
            return self._config

    def get(self) -> Config:
        if self._config is None:
            return self.load()
        return self._config

    def reload(self, config_path: Optional[Union[str, Path]] = None) -> Config:
        self._config = None
        return self.load(config_path)

    def _log_missing_config(self, path: Path) -> None:
        log = structlog.get_logger()
        log.warning("config_file_not_found", path=str(path), using_defaults=True)

    @staticmethod
    def _finalize_config(config: Config, *, override_level: Optional[str] = None) -> Config:
        if override_level:
            config.logging.level = override_level
        setup_logging(config)
        return config


def get_config(config_path: Optional[Union[str, Path]] = None) -> Config:
    """Convenience singleton getter / 便捷配置入口"""
    return ConfigLoader().load(config_path)
