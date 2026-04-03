"""
scraper_contracts.py - Stable result contracts for scraper flows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Tuple


@dataclass(frozen=True)
class ScrapedItem:
    id: str
    type: str
    url: str
    title: str
    author: str
    html: str
    date: str
    upvotes: int = 0
    creator_url_token: Optional[str] = None

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "ScrapedItem":
        return cls(
            id=str(raw.get("id", "")),
            type=raw.get("type", "unknown"),
            url=raw.get("url", ""),
            title=raw.get("title", ""),
            author=raw.get("author", ""),
            html=raw.get("html", ""),
            date=raw.get("date", ""),
            upvotes=raw.get("upvotes", 0),
            creator_url_token=raw.get("creator_url_token"),
        )

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "url": self.url,
            "title": self.title,
            "author": self.author,
            "html": self.html,
            "date": self.date,
            "upvotes": self.upvotes,
        }
        if self.creator_url_token:
            payload["creator_url_token"] = self.creator_url_token
        return payload


@dataclass(frozen=True)
class PaginationStats:
    requested_limit: int
    saved_count: int
    pages_fetched: int
    last_offset: int
    reached_end: bool
    stopped_early: bool

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "PaginationStats":
        return cls(
            requested_limit=raw.get("requested_limit", 0),
            saved_count=raw.get("saved_count", 0),
            pages_fetched=raw.get("pages_fetched", 0),
            last_offset=raw.get("last_offset", 0),
            reached_end=raw.get("reached_end", False),
            stopped_early=raw.get("stopped_early", False),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requested_limit": self.requested_limit,
            "saved_count": self.saved_count,
            "pages_fetched": self.pages_fetched,
            "last_offset": self.last_offset,
            "reached_end": self.reached_end,
            "stopped_early": self.stopped_early,
        }


@dataclass(frozen=True)
class CreatorProfileSummary:
    user_id: str
    name: str
    url_token: str
    headline: str
    description: str
    profile_url: str
    avatar_url: str
    follower_count: int
    following_count: int
    voteup_count: int
    answer_count: int
    articles_count: int
    question_count: int
    video_count: int
    column_count: int

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "CreatorProfileSummary":
        return cls(
            user_id=raw.get("user_id", ""),
            name=raw.get("name", ""),
            url_token=raw.get("url_token", ""),
            headline=raw.get("headline", ""),
            description=raw.get("description", ""),
            profile_url=raw.get("profile_url", ""),
            avatar_url=raw.get("avatar_url", ""),
            follower_count=raw.get("follower_count", 0),
            following_count=raw.get("following_count", 0),
            voteup_count=raw.get("voteup_count", 0),
            answer_count=raw.get("answer_count", 0),
            articles_count=raw.get("articles_count", 0),
            question_count=raw.get("question_count", 0),
            video_count=raw.get("video_count", 0),
            column_count=raw.get("column_count", 0),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "url_token": self.url_token,
            "headline": self.headline,
            "description": self.description,
            "profile_url": self.profile_url,
            "avatar_url": self.avatar_url,
            "follower_count": self.follower_count,
            "following_count": self.following_count,
            "voteup_count": self.voteup_count,
            "answer_count": self.answer_count,
            "articles_count": self.articles_count,
            "question_count": self.question_count,
            "video_count": self.video_count,
            "column_count": self.column_count,
        }


@dataclass(frozen=True)
class PageFetchResult:
    source_url: str
    page_type: str
    items: Tuple[ScrapedItem, ...]
    pagination: Optional[PaginationStats] = None

    @property
    def is_empty(self) -> bool:
        return not self.items

    def to_legacy_payload(self) -> Any:
        payload = [item.to_dict() for item in self.items]
        if self.page_type == "question":
            return payload
        return payload[0] if payload else {}


@dataclass(frozen=True)
class CreatorFetchResult:
    creator: CreatorProfileSummary
    items: Tuple[ScrapedItem, ...]
    answers: PaginationStats
    articles: PaginationStats

    @property
    def is_empty(self) -> bool:
        return not self.items

    def to_dict(self) -> Dict[str, Any]:
        return {
            "creator": self.creator.to_dict(),
            "items": [item.to_dict() for item in self.items],
            "sync": {
                "answers": self.answers.to_dict(),
                "articles": self.articles.to_dict(),
            },
        }


def to_scraped_items(items: Iterable[Dict[str, Any]]) -> Tuple[ScrapedItem, ...]:
    return tuple(ScrapedItem.from_dict(item) for item in items)
