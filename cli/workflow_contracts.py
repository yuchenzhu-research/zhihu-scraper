"""
workflow_contracts.py - Typed application-level results for CLI/TUI workflows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from cli.save_contracts import CreatorSaveResult, SaveRunResult


@dataclass(frozen=True)
class UrlTaskResult:
    url: str
    success: bool
    save_result: Optional[SaveRunResult] = None
    partial_save_result: Optional[SaveRunResult] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class BatchWorkflowResult:
    items: Tuple[UrlTaskResult, ...]

    @property
    def total_count(self) -> int:
        return len(self.items)

    @property
    def success_count(self) -> int:
        return sum(1 for item in self.items if item.success)

    @property
    def failed_count(self) -> int:
        return self.total_count - self.success_count

    @property
    def has_failures(self) -> bool:
        return self.failed_count > 0


@dataclass(frozen=True)
class CreatorWorkflowResult:
    creator: str
    result: Optional[CreatorSaveResult]

    @property
    def success(self) -> bool:
        return self.result is not None


@dataclass(frozen=True)
class MonitorWorkflowResult:
    collection_id: str
    discovered_count: int
    batch: BatchWorkflowResult
    pointer_advanced: bool
    unsupported_count: int = 0
    next_pointer: Optional[str] = None

    @property
    def has_new_items(self) -> bool:
        return self.discovered_count > 0

    @property
    def has_new_activity(self) -> bool:
        return self.discovered_count + self.unsupported_count > 0
