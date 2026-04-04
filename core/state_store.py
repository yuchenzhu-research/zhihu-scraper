"""
state_store.py - Abstract mechanism for storing and retrieving incremental points or states.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional

from .config import get_logger


class StateStore(ABC):
    """
    Abstract interface for state storage.
    状态存储的抽象接口。
    """
    
    @abstractmethod
    def get_state(self, key: str) -> Optional[str]:
        """Get state value by key. / 根据键获取状态值"""
        pass
        
    @abstractmethod
    def set_state(self, key: str, value: str) -> None:
        """Set state value by key. / 设置对应键的状态值"""
        pass


class JsonFileStateStore(StateStore):
    """
    JSON file based state storage implementation.
    基于 JSON 文件的状态存储实现。
    """

    def __init__(self, file_path: Path | str):
        self.file_path = Path(file_path)
        self.log = get_logger()
        self._state: Dict[str, str] = self._load()

    def _load(self) -> Dict[str, str]:
        """
        Load state map from file
        """
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                self.log.warning("load_state_store_failed", file_path=str(self.file_path), error=str(e))
        return {}

    def _save(self) -> None:
        """
        Persist state map to file
        """
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self.log.error("save_state_store_failed", file_path=str(self.file_path), error=str(e))

    def get_state(self, key: str) -> Optional[str]:
        return self._state.get(str(key))

    def set_state(self, key: str, value: str) -> None:
        self._state[str(key)] = str(value)
        self._save()
