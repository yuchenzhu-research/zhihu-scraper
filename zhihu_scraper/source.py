"""Narrow Zhihu payload source built on the authenticated HTTP client.

This module only knows how to address Zhihu resources, validate transport
payload shapes, and traverse API pagination.  It deliberately does not
normalize content or decide how archives are stored.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Iterator, Mapping
from html import unescape
from html.parser import HTMLParser
from typing import Protocol
from urllib.parse import quote, urlsplit

from zhihu_scraper.urls import TargetKind, ZhihuTarget, route_zhihu_url


class _PayloadClient(Protocol):
    def get_json(self, url_or_path: str) -> object: ...

    def get_html(self, url_or_path: str) -> str: ...


class InvalidZhihuPayloadError(RuntimeError):
    """Zhihu returned data that cannot satisfy the source contract."""


class PaginationLoopError(InvalidZhihuPayloadError):
    """Zhihu pagination did not make forward progress."""


class ZhihuSource:
    """Fetch raw payloads through a small, injectable HTTP interface."""

    def __init__(self, client: _PayloadClient) -> None:
        self._client = client

    def fetch_article_payload(
        self,
        article: str | ZhihuTarget,
    ) -> Mapping[str, object]:
        article_id = _resolve_reference(article, TargetKind.ARTICLE)
        payload = self._client.get_json(f"/api/v4/articles/{article_id}")
        if _is_article_parameter_error(payload):
            article_url = f"https://zhuanlan.zhihu.com/p/{article_id}"
            return extract_article_payload(
                self._client.get_html(article_url),
                article_id,
            )
        return _require_mapping(payload, "文章 API")

    def fetch_answer_payload(
        self,
        answer: str | ZhihuTarget,
    ) -> Mapping[str, object]:
        answer_id = _resolve_reference(answer, TargetKind.ANSWER)
        return _require_mapping(
            self._client.get_json(
                f"/api/v4/answers/{answer_id}?include=content,voteup_count,question,author"
            ),
            "回答 API",
        )

    def fetch_question_payload(
        self,
        question: str | ZhihuTarget,
    ) -> Mapping[str, object]:
        question_id = _resolve_reference(question, TargetKind.QUESTION)
        return _require_mapping(
            self._client.get_json(f"/api/v4/questions/{question_id}"),
            "问题 API",
        )

    def iter_question_answer_payloads(
        self,
        question: str | ZhihuTarget,
        *,
        page_size: int = 20,
    ) -> Iterator[Mapping[str, object]]:
        question_id = _resolve_reference(question, TargetKind.QUESTION)
        endpoint = f"/api/v4/questions/{question_id}/answers"
        include = quote(
            "data[*].content,voteup_count,comment_count",
            safe="",
        )

        def page_url(offset: int) -> str:
            return (
                f"{endpoint}?limit={page_size}&offset={offset}"
                f"&platform=desktop&sort_by=default&include={include}"
            )

        yield from self._iter_payloads(
            endpoint=endpoint,
            page_url=page_url,
            page_size=page_size,
            payload_label="问题回答列表",
        )

    def fetch_column_payload(
        self,
        column: str | ZhihuTarget,
    ) -> Mapping[str, object]:
        column_token = _resolve_reference(column, TargetKind.COLUMN)
        return _require_mapping(
            self._client.get_json(f"/api/v4/columns/{column_token}"),
            "专栏 API",
        )

    def iter_column_article_payloads(
        self,
        column: str | ZhihuTarget,
        *,
        page_size: int = 20,
    ) -> Iterator[Mapping[str, object]]:
        column_token = _resolve_reference(column, TargetKind.COLUMN)
        endpoint = f"/api/v4/columns/{column_token}/items"

        def page_url(offset: int) -> str:
            return f"{endpoint}?limit={page_size}&offset={offset}"

        yield from self._iter_payloads(
            endpoint=endpoint,
            page_url=page_url,
            page_size=page_size,
            payload_label="专栏文章列表",
        )

    def fetch_video_payload(
        self,
        video: str | ZhihuTarget,
    ) -> Mapping[str, object]:
        video_id = _resolve_reference(video, TargetKind.VIDEO)
        return _require_mapping(
            self._client.get_json(f"/api/v4/zvideos/{video_id}"),
            "独立视频 API",
        )

    def _iter_payloads(
        self,
        *,
        endpoint: str,
        page_url: Callable[[int], str],
        page_size: int,
        payload_label: str,
    ) -> Iterator[Mapping[str, object]]:
        if not 1 <= page_size <= 100:
            raise ValueError("分页大小必须在 1 到 100 之间。")

        offset = 0
        current_url = page_url(offset)
        visited_urls: set[str] = set()
        seen_item_ids: set[str] = set()
        stagnant_pages = 0

        while True:
            if current_url in visited_urls:
                raise PaginationLoopError(
                    f"{payload_label}分页返回了重复地址，已停止以避免无限循环。"
                )
            visited_urls.add(current_url)

            page = _require_mapping(
                self._client.get_json(current_url),
                payload_label,
            )
            raw_data = page.get("data")
            if not isinstance(raw_data, list):
                raise InvalidZhihuPayloadError(f"{payload_label}的 data 字段必须是列表。")
            new_items = 0
            for index, item in enumerate(raw_data):
                if not isinstance(item, Mapping):
                    raise InvalidZhihuPayloadError(f"{payload_label}第 {index + 1} 项必须是对象。")
                raw_id = item.get("id")
                stable_id = (
                    str(raw_id).strip()
                    if isinstance(raw_id, (str, int)) and not isinstance(raw_id, bool)
                    else ""
                )
                if not stable_id:
                    raise InvalidZhihuPayloadError(
                        f"{payload_label}第 {index + 1} 项缺少有效 ID，无法判断分页进展。"
                    )
                if stable_id in seen_item_ids:
                    continue
                seen_item_ids.add(stable_id)
                new_items += 1
                yield dict(item)

            raw_paging = page.get("paging", {})
            if not isinstance(raw_paging, Mapping):
                raise InvalidZhihuPayloadError(f"{payload_label}的 paging 字段必须是对象。")
            raw_is_end = raw_paging.get("is_end")
            if raw_is_end is not None and not isinstance(raw_is_end, bool):
                raise InvalidZhihuPayloadError(
                    f"{payload_label}的 paging.is_end 字段必须是布尔值。"
                )
            is_end = raw_is_end if isinstance(raw_is_end, bool) else len(raw_data) < page_size
            if is_end:
                return

            # A shifting feed can overlap one whole page. Persistent lack of
            # new content is a loop even when each next URL has a new cursor.
            stagnant_pages = stagnant_pages + 1 if new_items == 0 else 0
            if stagnant_pages >= 2:
                raise PaginationLoopError(
                    f"{payload_label}连续两页没有新增内容，已停止以避免无限循环。"
                )

            offset += len(raw_data)
            raw_next = raw_paging.get("next")
            if raw_next is not None and not isinstance(raw_next, str):
                raise InvalidZhihuPayloadError(f"{payload_label}的 paging.next 字段必须是链接。")
            next_url = raw_next.strip() if isinstance(raw_next, str) else ""
            if next_url:
                current_url = _validate_next_url(next_url, endpoint)
                continue

            if not raw_data:
                raise PaginationLoopError(
                    f"{payload_label}返回空页但仍标记为未结束，无法继续分页。"
                )
            current_url = page_url(offset)


def extract_article_payload(
    document: str,
    article_id: str,
) -> Mapping[str, object]:
    """Extract one full article entity from a Zhihu HTML initial state."""

    return extract_entity_payload(
        document,
        collection="articles",
        entity_id=article_id,
    )


def extract_entity_payload(
    document: str,
    *,
    collection: str,
    entity_id: str,
) -> Mapping[str, object]:
    """Extract one entity collection item from a Zhihu HTML initial state."""

    if not isinstance(document, str):
        raise InvalidZhihuPayloadError("知乎页面 HTML 必须是文本。")
    if collection not in {"articles", "answers", "questions", "columns", "zvideos"}:
        raise ValueError("unsupported initial-state entity collection")
    normalized_id = str(entity_id)
    candidates: list[str] = []

    parser = _InitialDataScriptParser()
    try:
        parser.feed(document)
        parser.close()
    except Exception:
        # The assignment scanner below may still recover the JSON from malformed
        # surrounding HTML, so parsing failure is not immediately fatal.
        pass
    candidates.extend(parser.documents)
    candidates.extend(_window_initial_state_documents(document))

    for candidate in candidates:
        serialized_candidates = [candidate]
        decoded_candidate = unescape(candidate)
        if decoded_candidate != candidate:
            serialized_candidates.append(decoded_candidate)
        for serialized in serialized_candidates:
            try:
                state = json.loads(serialized)
            except (json.JSONDecodeError, TypeError):
                continue
            entity = _find_entity(state, collection, normalized_id)
            if entity is not None:
                return entity

    raise InvalidZhihuPayloadError(f"知乎页面初始状态中未找到 {collection}:{normalized_id}。")


def _resolve_reference(
    reference: str | ZhihuTarget,
    expected_kind: TargetKind,
) -> str:
    target: ZhihuTarget | None = None
    if isinstance(reference, ZhihuTarget):
        target = reference
    elif isinstance(reference, str):
        value = reference.strip()
        if "://" in value:
            target = route_zhihu_url(value)
        else:
            return _validate_bare_identifier(value, expected_kind)
    else:
        raise TypeError("知乎内容引用必须是 ID、链接或 ZhihuTarget。")

    if target.kind is not expected_kind:
        raise ValueError(
            f"需要{_KIND_LABELS[expected_kind]}链接，收到的是{_KIND_LABELS[target.kind]}链接。"
        )
    return _validate_bare_identifier(target.content_id, expected_kind)


_KIND_LABELS = {
    TargetKind.ARTICLE: "文章",
    TargetKind.ANSWER: "回答",
    TargetKind.QUESTION: "问题",
    TargetKind.COLUMN: "专栏",
    TargetKind.VIDEO: "独立视频",
}


def _validate_bare_identifier(value: str, kind: TargetKind) -> str:
    if kind is TargetKind.COLUMN:
        valid = bool(re.fullmatch(r"[A-Za-z0-9_-]+", value))
    else:
        valid = value.isascii() and value.isdigit()
    if not valid:
        raise ValueError(f"{_KIND_LABELS[kind]} ID 格式无效。")
    return quote(value, safe="")


def _require_mapping(payload: object, label: str) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise InvalidZhihuPayloadError(f"{label}返回值必须是对象。")
    if "error" in payload:
        raise InvalidZhihuPayloadError(f"{label}返回了错误响应。")
    return dict(payload)


def _is_article_parameter_error(payload: object) -> bool:
    if not isinstance(payload, Mapping):
        return False
    error = payload.get("error")
    if not isinstance(error, Mapping):
        return False
    code = error.get("code")
    message = error.get("message")
    return code == 10003 or (
        isinstance(message, str) and "请求参数异常" in message and "升级客户端" in message
    )


def _validate_next_url(next_url: str, endpoint: str) -> str:
    parsed = urlsplit(next_url)
    if parsed.scheme or parsed.netloc:
        host = (parsed.hostname or "").casefold()
        expected_port = 443 if parsed.scheme == "https" else 80
        if (
            parsed.scheme not in {"http", "https"}
            or not (host == "zhihu.com" or host.endswith(".zhihu.com"))
            or parsed.path != endpoint
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in {None, expected_port}
            or bool(parsed.fragment)
        ):
            raise InvalidZhihuPayloadError("分页 next 地址不是预期的知乎 API 端点。")
        return parsed._replace(scheme="https", netloc=host).geturl()
    elif parsed.path not in {"", endpoint}:
        raise InvalidZhihuPayloadError("分页 next 地址不是预期的知乎 API 端点。")
    elif not parsed.path:
        suffix = f"?{parsed.query}" if parsed.query else ""
        return f"{endpoint}{suffix}"
    return next_url


class _InitialDataScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.documents: list[str] = []
        self._capture_depth = 0
        self._parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.casefold() != "script":
            return
        attributes = {name.casefold(): value for name, value in attrs}
        if attributes.get("id") == "js-initialData":
            self._capture_depth = 1
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._capture_depth:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "script" and self._capture_depth:
            self.documents.append("".join(self._parts).strip())
            self._capture_depth = 0
            self._parts = []


_INITIAL_STATE_ASSIGNMENT = re.compile(
    r"(?:window\s*\.\s*)?__INITIAL_STATE__\s*=",
)


def _window_initial_state_documents(document: str) -> list[str]:
    candidates: list[str] = []
    for assignment in _INITIAL_STATE_ASSIGNMENT.finditer(document):
        start = document.find("{", assignment.end())
        if start < 0:
            continue
        candidate = _balanced_json_object(document, start)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _balanced_json_object(document: str, start: int) -> str | None:
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(document)):
        character = document[index]
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return document[start : index + 1]
            if depth < 0:
                return None
    return None


def _find_entity(
    value: object,
    collection_name: str,
    entity_id: str,
) -> Mapping[str, object] | None:
    if isinstance(value, Mapping):
        raw_collection = value.get(collection_name)
        entity = _entity_from_collection(raw_collection, entity_id)
        if entity is not None:
            return entity
        for nested in value.values():
            entity = _find_entity(nested, collection_name, entity_id)
            if entity is not None:
                return entity
    elif isinstance(value, list):
        for nested in value:
            entity = _find_entity(nested, collection_name, entity_id)
            if entity is not None:
                return entity
    return None


def _entity_from_collection(
    collection: object,
    entity_id: str,
) -> Mapping[str, object] | None:
    if isinstance(collection, Mapping):
        direct = collection.get(entity_id)
        if isinstance(direct, Mapping):
            return dict(direct)
        candidates: Iterable[object] = collection.values()
    elif isinstance(collection, list):
        candidates = collection
    else:
        return None

    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        candidate_id = candidate.get("id")
        if str(candidate_id) == entity_id:
            return dict(candidate)
    return None
