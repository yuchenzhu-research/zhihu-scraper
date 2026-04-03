"""
save_contracts.py - Stable result contracts for local save orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.scraper_contracts import CreatorProfileSummary, PaginationStats, ScrapedItem


@dataclass(frozen=True)
class SavedContentRecord:
    item: ScrapedItem
    folder: Path
    markdown_path: Path

    @classmethod
    def from_legacy_dict(cls, raw: Dict) -> "SavedContentRecord":
        return cls(
            item=ScrapedItem.from_dict(raw["item"]),
            folder=Path(raw["folder"]),
            markdown_path=Path(raw["markdown_path"]),
        )

    def to_legacy_dict(self) -> Dict:
        return {
            "item": self.item.to_dict(),
            "folder": self.folder,
            "markdown_path": self.markdown_path,
        }


@dataclass(frozen=True)
class SaveRunResult:
    source_url: str
    content_root: Path
    records: Tuple[SavedContentRecord, ...]
    collection_id: Optional[str] = None

    @property
    def is_empty(self) -> bool:
        return not self.records

    @property
    def saved_count(self) -> int:
        return len(self.records)

    @property
    def markdown_paths(self) -> Tuple[str, ...]:
        return tuple(str(record.markdown_path) for record in self.records)

    def to_legacy_records(self) -> List[Dict]:
        return [record.to_legacy_dict() for record in self.records]


@dataclass(frozen=True)
class CreatorSaveResult:
    creator: CreatorProfileSummary
    save_result: SaveRunResult
    answers: PaginationStats
    articles: PaginationStats

