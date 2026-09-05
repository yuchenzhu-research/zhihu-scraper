"""Map Zhihu payloads into stable domain objects."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from .content import parse_rich_text
from .domain import (
    Answer,
    Article,
    Author,
    Column,
    ColumnRef,
    MediaAsset,
    MediaKind,
    MediaRendition,
    Question,
    QuestionRef,
    Video,
)


class NormalizationError(ValueError):
    """A source payload is missing identity required by the archive."""


def normalize_article(
    payload: Mapping[str, Any],
    *,
    source_url: str | None = None,
) -> Article:
    """Normalize either an article API item or extracted page state."""

    article_id = _required_identifier(payload.get("id"), label="article id")
    canonical_url = source_url or f"https://zhuanlan.zhihu.com/p/{article_id}"
    title = _required_text(payload.get("title"), label="article title")
    raw_content = payload.get("content")
    content = raw_content if isinstance(raw_content, str) else ""

    return Article(
        id=article_id,
        title=title,
        source_url=canonical_url,
        author=_normalize_author(payload.get("author")),
        published_at=_utc_datetime(
            _field(
                payload,
                "created",
                "created_time",
                "createdTime",
                "created_at",
                "createdAt",
            )
        ),
        updated_at=_utc_datetime(
            _field(
                payload,
                "updated",
                "updated_time",
                "updatedTime",
                "updated_at",
                "updatedAt",
            )
        ),
        blocks=parse_rich_text(content, base_url=canonical_url),
        voteup_count=_nonnegative_int(
            _field(payload, "voteup_count", "voteupCount", "vote_count", "voteCount")
        ),
        cover_url=_optional_text(
            _field(
                payload,
                "image_url",
                "imageUrl",
                "title_image",
                "titleImage",
                "cover_url",
                "coverUrl",
            )
        ),
        columns=_normalize_columns(payload),
        comments=None,
    )


def normalize_answer(
    payload: Mapping[str, Any],
    *,
    source_url: str | None = None,
) -> Answer:
    answer_id = _required_identifier(payload.get("id"), label="answer id")
    question_payload = payload.get("question")
    if not isinstance(question_payload, Mapping):
        raise NormalizationError("missing answer question")
    question_id = _required_identifier(
        question_payload.get("id"),
        label="question id",
    )
    question_title = _required_text(
        question_payload.get("title"),
        label="question title",
    )
    canonical_url = source_url or f"https://www.zhihu.com/question/{question_id}/answer/{answer_id}"
    raw_content = payload.get("content")
    content = raw_content if isinstance(raw_content, str) else ""
    return Answer(
        id=answer_id,
        question=QuestionRef(
            id=question_id,
            title=question_title,
            url=f"https://www.zhihu.com/question/{question_id}",
        ),
        source_url=canonical_url,
        author=_normalize_author(payload.get("author")),
        published_at=_utc_datetime(
            _field(
                payload,
                "created_time",
                "createdTime",
                "created",
                "created_at",
                "createdAt",
            )
        ),
        updated_at=_utc_datetime(
            _field(
                payload,
                "updated_time",
                "updatedTime",
                "updated",
                "updated_at",
                "updatedAt",
            )
        ),
        blocks=parse_rich_text(content, base_url=canonical_url),
        voteup_count=_nonnegative_int(
            _field(payload, "voteup_count", "voteupCount", "vote_count", "voteCount")
        ),
        comments=None,
    )


def normalize_question(
    payload: Mapping[str, Any],
    *,
    source_url: str | None = None,
) -> Question:
    question_id = _required_identifier(payload.get("id"), label="question id")
    canonical_url = source_url or f"https://www.zhihu.com/question/{question_id}"
    raw_detail = payload.get("detail") or payload.get("description")
    detail = raw_detail if isinstance(raw_detail, str) else ""
    raw_author = payload.get("author")
    return Question(
        id=question_id,
        title=_required_text(payload.get("title"), label="question title"),
        source_url=canonical_url,
        detail=parse_rich_text(detail, base_url=canonical_url),
        author=(_normalize_author(raw_author) if isinstance(raw_author, Mapping) else None),
        created_at=_utc_datetime(
            _field(
                payload,
                "created",
                "created_time",
                "createdTime",
                "created_at",
                "createdAt",
            )
        ),
        updated_at=_utc_datetime(
            _field(
                payload,
                "updated_time",
                "updatedTime",
                "updated",
                "updated_at",
                "updatedAt",
            )
        ),
        answer_count=_nonnegative_int(_field(payload, "answer_count", "answerCount")),
        follower_count=_nonnegative_int(_field(payload, "follower_count", "followerCount")),
    )


def normalize_column(
    payload: Mapping[str, Any],
    *,
    source_url: str | None = None,
) -> Column:
    token = (
        _optional_text(payload.get("id"))
        or _optional_text(payload.get("slug"))
        or _column_token_from_url(_optional_text(payload.get("url")))
    )
    if not token:
        raise NormalizationError("missing column token")
    raw_author = payload.get("author")
    return Column(
        token=token,
        title=_required_text(payload.get("title"), label="column title"),
        source_url=source_url or f"https://www.zhihu.com/column/{token}",
        description=_optional_text(payload.get("description")) or "",
        author=(_normalize_author(raw_author) if isinstance(raw_author, Mapping) else None),
        item_count=_nonnegative_int(
            _field(
                payload,
                "items_count",
                "itemsCount",
                "articles_count",
                "articlesCount",
                "item_count",
                "itemCount",
            )
        ),
    )


def normalize_video(
    payload: Mapping[str, Any],
    *,
    source_url: str | None = None,
) -> Video:
    video_id = _required_identifier(payload.get("id"), label="video id")
    canonical_url = source_url or f"https://www.zhihu.com/zvideo/{video_id}"
    video_payload = payload.get("video")
    renditions = normalize_video_renditions(
        video_payload if isinstance(video_payload, Mapping) else payload
    )
    if not renditions:
        raise NormalizationError("video payload contains no downloadable rendition")
    raw_description = payload.get("description")
    description = raw_description if isinstance(raw_description, str) else ""
    return Video(
        id=video_id,
        title=_required_text(payload.get("title"), label="video title"),
        source_url=canonical_url,
        author=_normalize_author(payload.get("author")),
        published_at=_utc_datetime(
            _field(
                payload,
                "published_at",
                "publishedAt",
                "created_at",
                "createdAt",
                "created",
            )
        ),
        updated_at=_utc_datetime(_field(payload, "updated_at", "updatedAt", "updated")),
        description=parse_rich_text(description, base_url=canonical_url),
        asset=MediaAsset(
            id=f"zvideo-{video_id}",
            kind=MediaKind.VIDEO,
            renditions=renditions,
            alt_text=_required_text(payload.get("title"), label="video title"),
        ),
        cover_url=_optional_text(
            _field(
                payload,
                "thumbnail",
                "cover_url",
                "coverUrl",
                "image_url",
                "imageUrl",
            )
        ),
        voteup_count=_nonnegative_int(
            _field(payload, "voteup_count", "voteupCount", "vote_count", "voteCount")
        ),
        comments=None,
    )


def _normalize_author(value: object) -> Author:
    payload = value if isinstance(value, Mapping) else {}
    identifier = _optional_text(payload.get("id"))
    name = (
        _optional_text(payload.get("name")) or _optional_text(payload.get("headline")) or "匿名用户"
    )
    url_token = _optional_text(_field(payload, "url_token", "urlToken"))
    raw_url = _optional_text(payload.get("url"))
    url: str | None = None
    if url_token:
        url = f"https://www.zhihu.com/people/{url_token}"
    elif raw_url:
        url = f"https://www.zhihu.com{raw_url}" if raw_url.startswith("/") else raw_url
    return Author(id=identifier, name=name, url=url)


def normalize_video_renditions(payload: Mapping[str, Any]) -> tuple[MediaRendition, ...]:
    """Normalize the playlist fields shared by Zhihu video and lens responses."""

    containers: list[Mapping[str, Any]] = []
    for key in ("playlist", "playlist_v2", "playlistV2", "playlists"):
        candidate = payload.get(key)
        if isinstance(candidate, Mapping):
            containers.append(candidate)
    if not containers and any(key in payload for key in ("play_url", "url", "play_url_https")):
        containers.append({"default": payload})

    renditions: list[MediaRendition] = []
    seen_urls: set[str] = set()
    for container in containers:
        for raw_variant in container.values():
            variants = (
                raw_variant
                if isinstance(raw_variant, Sequence) and not isinstance(raw_variant, (str, bytes))
                else (raw_variant,)
            )
            for variant in variants:
                if not isinstance(variant, Mapping):
                    continue
                url = _optional_text(
                    _field(
                        variant,
                        "play_url",
                        "playUrl",
                        "play_url_https",
                        "playUrlHttps",
                        "url",
                    )
                )
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                raw_format = _optional_text(variant.get("format") or variant.get("container"))
                mime_type = (
                    raw_format
                    if raw_format and "/" in raw_format
                    else f"video/{raw_format.casefold()}"
                    if raw_format
                    else None
                )
                renditions.append(
                    MediaRendition(
                        source_url=url,
                        mime_type=mime_type,
                        width=_optional_int(variant.get("width")),
                        height=_optional_int(variant.get("height")),
                        bitrate=_optional_int(_field(variant, "bitrate", "bit_rate", "bitRate")),
                        size_bytes=_optional_int(
                            _field(
                                variant,
                                "size",
                                "file_size",
                                "fileSize",
                                "play_size",
                                "playSize",
                            )
                        ),
                    )
                )
    return tuple(renditions)


def _normalize_columns(payload: Mapping[str, Any]) -> tuple[ColumnRef, ...]:
    candidates: list[object] = []
    if payload.get("column") is not None:
        candidates.append(payload["column"])
    for key in ("contributions", "columns"):
        value = payload.get(key)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            candidates.extend(value)

    columns: list[ColumnRef] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        nested_column = candidate.get("column")
        if isinstance(nested_column, Mapping):
            candidate = nested_column
        token = (
            _optional_text(candidate.get("id"))
            or _optional_text(candidate.get("slug"))
            or _column_token_from_url(_optional_text(candidate.get("url")))
        )
        if not token or token in seen:
            continue
        seen.add(token)
        columns.append(
            ColumnRef(
                token=token,
                title=_optional_text(candidate.get("title")) or token,
                url=(
                    _optional_text(candidate.get("url")) or f"https://www.zhihu.com/column/{token}"
                ),
            )
        )
    return tuple(columns)


def _field(payload: Mapping[str, Any], *keys: str) -> object:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return value
    return None


def _column_token_from_url(url: str | None) -> str | None:
    if not url:
        return None
    path_parts = [part for part in urlparse(url).path.split("/") if part]
    if len(path_parts) >= 2 and path_parts[-2] == "column":
        return path_parts[-1]
    return None


def _utc_datetime(value: object) -> datetime | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and value > 0:
        return datetime.fromtimestamp(value, tz=UTC)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return datetime.fromtimestamp(int(stripped), tz=UTC)
        try:
            parsed = datetime.fromisoformat(stripped.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    return None


def _required_identifier(value: object, *, label: str) -> str:
    identifier = _optional_text(value)
    if not identifier:
        raise NormalizationError(f"missing {label}")
    return identifier


def _required_text(value: object, *, label: str) -> str:
    text = _optional_text(value)
    if not text:
        raise NormalizationError(f"missing {label}")
    return text


def _optional_text(value: object) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return None


def _nonnegative_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if not isinstance(value, (str, int, float, bytes, bytearray)):
        return 0
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if not isinstance(value, (str, int, float, bytes, bytearray)):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
