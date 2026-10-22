"""Fetch and normalize bounded Zhihu comment threads."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Protocol
from urllib.parse import quote, urljoin, urlsplit

from .content import parse_rich_text
from .domain import Author, Comment, CommentThread


class CommentClient(Protocol):
    def get_json(self, url_or_path: str) -> object: ...


class InvalidCommentPayloadError(ValueError):
    """A 200 response whose comment structure cannot be trusted."""


def fetch_comment_thread(
    client: CommentClient,
    *,
    target_kind: str,
    target_id: str,
    root_limit: int = 10,
    reply_limit: int = 10,
) -> CommentThread:
    """Fetch a bounded thread in the order returned by Zhihu's API."""

    for name, value in (("root_limit", root_limit), ("reply_limit", reply_limit)):
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"{name} must be a positive integer.")

    collections = {
        "article": "articles",
        "answer": "answers",
        "zvideo": "zvideos",
    }
    try:
        collection = collections[target_kind]
    except KeyError:
        raise ValueError("target_kind must be article, answer, or zvideo.") from None
    root_url = (
        f"/api/v4/comment_v5/{collection}/{target_id}/root_comment?limit={root_limit}&offset="
    )
    root_items, roots_complete = _fetch_bounded_pages(
        client,
        first_url=root_url,
        limit=root_limit,
    )
    roots: list[Comment] = []
    for item in root_items:
        root = _normalize_comment(item)
        replies: tuple[Comment, ...]
        if isinstance(item, Mapping) and item.get("child_comment_count") == 0:
            replies = ()
            replies_complete = True
        else:
            reply_url = (
                f"/api/v4/comment_v5/comment/{quote(root.id, safe='')}/child_comment"
                f"?limit={reply_limit}&offset="
            )
            reply_items, replies_complete = _fetch_bounded_pages(
                client,
                first_url=reply_url,
                limit=reply_limit,
            )
            replies = tuple(_normalize_comment(reply) for reply in reply_items)
        roots.append(
            Comment(
                id=root.id,
                author=root.author,
                blocks=root.blocks,
                created_at=root.created_at,
                like_count=root.like_count,
                replies=replies,
                replies_complete=replies_complete,
            )
        )
    return CommentThread(
        comments=tuple(roots),
        order="api_returned",
        roots_complete=roots_complete,
        root_limit=root_limit,
        reply_limit=reply_limit,
    )


def _fetch_bounded_pages(
    client: CommentClient,
    *,
    first_url: str,
    limit: int,
) -> tuple[list[object], bool]:
    items: list[object] = []
    next_url = first_url
    visited: set[str] = set()
    seen_ids: set[str] = set()
    stagnant_pages = 0
    while next_url:
        if next_url in visited:
            raise InvalidCommentPayloadError("Zhihu comment paging contains a loop.")
        visited.add(next_url)
        data, is_end, following_url = _page(client.get_json(next_url))
        unique: list[object] = []
        for item in data:
            identifier = _comment_id(item)
            if identifier not in seen_ids:
                seen_ids.add(identifier)
                unique.append(item)
        remaining = limit - len(items)
        items.extend(unique[:remaining])
        if len(unique) > remaining:
            return items, False
        if len(items) == limit:
            return items, is_end
        if is_end:
            return items, True
        stagnant_pages = stagnant_pages + 1 if not unique else 0
        if stagnant_pages >= 2:
            raise InvalidCommentPayloadError("Zhihu comment paging made no progress for two pages.")
        next_url = _next_comment_page(following_url, first_url)
    return items, False


def _comment_id(payload: object) -> str:
    if not isinstance(payload, Mapping):
        raise InvalidCommentPayloadError("Zhihu comment must be an object.")
    identifier = payload.get("id")
    if (
        isinstance(identifier, bool)
        or not isinstance(identifier, (str, int))
        or not str(identifier).strip()
    ):
        raise InvalidCommentPayloadError("Zhihu comment is missing a valid id.")
    return str(identifier).strip()


def _next_comment_page(url: str, first_url: str) -> str:
    try:
        parsed = urlsplit(urljoin("https://www.zhihu.com/", url))
        if (
            parsed.scheme == "https"
            and parsed.hostname == "www.zhihu.com"
            and parsed.port in {None, 443}
            and parsed.username is None
            and parsed.password is None
            and not parsed.fragment
            and parsed.path == urlsplit(first_url).path
        ):
            return url
    except ValueError:
        pass
    raise InvalidCommentPayloadError("Zhihu comment paging returned a different endpoint.")


def _page(payload: object) -> tuple[list[object], bool, str]:
    if not isinstance(payload, Mapping):
        raise InvalidCommentPayloadError("Zhihu comment page must be an object.")
    data = payload.get("data")
    paging = payload.get("paging")
    if not isinstance(data, list) or not isinstance(paging, Mapping):
        raise InvalidCommentPayloadError("Zhihu comment page is missing data or paging.")
    end = paging.get("is_end", paging.get("end"))
    if not isinstance(end, bool):
        raise InvalidCommentPayloadError("Zhihu comment page has an invalid paging end flag.")
    raw_next = paging.get("next")
    if end:
        next_url = ""
    elif isinstance(raw_next, str) and raw_next.strip():
        next_url = raw_next.strip()
    else:
        raise InvalidCommentPayloadError("Zhihu comment page is missing its next page URL.")
    return data, end, next_url


def _normalize_comment(payload: object) -> Comment:
    if not isinstance(payload, Mapping):
        raise InvalidCommentPayloadError("Zhihu comment must be an object.")
    identifier = _comment_id(payload)
    content = payload.get("content")
    if not isinstance(content, str):
        raise InvalidCommentPayloadError("Zhihu comment is missing content.")
    raw_created = payload.get("created_time")
    if raw_created is None:
        created_at = None
    elif isinstance(raw_created, (int, float)) and not isinstance(raw_created, bool):
        try:
            created_at = datetime.fromtimestamp(raw_created, tz=UTC)
        except (OSError, OverflowError, ValueError):
            raise InvalidCommentPayloadError("Zhihu comment has an invalid created_time.") from None
    else:
        raise InvalidCommentPayloadError("Zhihu comment has an invalid created_time.")
    raw_like_count = payload.get("like_count", 0)
    if (
        not isinstance(raw_like_count, int)
        or isinstance(raw_like_count, bool)
        or raw_like_count < 0
    ):
        raise InvalidCommentPayloadError("Zhihu comment has an invalid like_count.")
    like_count = raw_like_count
    return Comment(
        id=identifier,
        author=_normalize_author(payload.get("author")),
        blocks=parse_rich_text(content),
        created_at=created_at,
        like_count=like_count,
    )


def _normalize_author(payload: object) -> Author | None:
    if not isinstance(payload, Mapping):
        return None
    member = payload.get("member", payload)
    if not isinstance(member, Mapping):
        return None
    raw_name = member.get("name")
    if not isinstance(raw_name, str) or not raw_name.strip():
        return None
    raw_id = member.get("id")
    normalized_id = (
        str(raw_id).strip()
        if isinstance(raw_id, (str, int)) and not isinstance(raw_id, bool)
        else ""
    )
    author_id = normalized_id or None
    raw_token = member.get("url_token")
    url = (
        f"https://www.zhihu.com/people/{raw_token.strip()}"
        if isinstance(raw_token, str) and raw_token.strip()
        else None
    )
    return Author(id=author_id, name=raw_name.strip(), url=url)
