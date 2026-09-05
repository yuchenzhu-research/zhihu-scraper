"""Public archive workflow: route, fetch, normalize, enrich, and save."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from types import TracebackType
from typing import Protocol, Self

from .archive import ArchiveReceipt
from .assets import MediaArchiveFailure
from .comments import CommentClient, InvalidCommentPayloadError, fetch_comment_thread
from .domain import (
    Answer,
    ArchiveTarget,
    Article,
    ColumnArchive,
    ColumnRef,
    QuestionArchive,
)
from .embedded_video import EmbeddedVideoWarning, resolve_embedded_videos
from .http import InvalidResponseError, TransportError, ZhihuHttpError
from .normalize import (
    NormalizationError,
    normalize_answer,
    normalize_article,
    normalize_column,
    normalize_question,
    normalize_video,
)
from .settings import ArchiveSettings
from .settings import BrowserFallback as BrowserFallbackMode
from .source import InvalidZhihuPayloadError, extract_entity_payload
from .urls import TargetKind, ZhihuTarget, route_zhihu_url


class ArchiveSink(Protocol):
    def archive(self, target: ArchiveTarget) -> ArchiveReceipt: ...


class PayloadSource(Protocol):
    def fetch_article_payload(self, target: ZhihuTarget) -> Mapping[str, object]: ...

    def fetch_answer_payload(self, target: ZhihuTarget) -> Mapping[str, object]: ...

    def fetch_question_payload(self, target: ZhihuTarget) -> Mapping[str, object]: ...

    def iter_question_answer_payloads(
        self,
        target: ZhihuTarget,
        *,
        page_size: int,
    ) -> Iterator[Mapping[str, object]]: ...

    def fetch_column_payload(self, target: ZhihuTarget) -> Mapping[str, object]: ...

    def iter_column_article_payloads(
        self,
        target: ZhihuTarget,
        *,
        page_size: int,
    ) -> Iterator[Mapping[str, object]]: ...

    def fetch_video_payload(self, target: ZhihuTarget) -> Mapping[str, object]: ...


class BrowserReader(Protocol):
    def set_cookie_dict(self, cookies: dict[str, str]) -> None: ...

    def fetch_html(self, url: str) -> str: ...

    def cookie_dict(self) -> dict[str, str]: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> object: ...


class BrowserFallbackUnavailableError(RuntimeError):
    """HTTP failed and no configured browser fallback can continue."""


@dataclass(frozen=True, slots=True)
class ArchiveReport:
    target: ArchiveTarget
    receipt: ArchiveReceipt
    used_browser: bool
    media_failures: tuple[MediaArchiveFailure, ...] = ()
    embedded_video_warnings: tuple[EmbeddedVideoWarning, ...] = ()


class ArchiveWorkflow:
    """One testable use case behind the project's public archive behavior."""

    def __init__(
        self,
        *,
        source: PayloadSource,
        sink: ArchiveSink,
        settings: ArchiveSettings,
        comment_client: CommentClient | None = None,
        embedded_video_fetcher: Callable[[str], object] | None = None,
        browser_factory: Callable[[], BrowserReader] | None = None,
        browser_cookies: Mapping[str, str] | None = None,
        browser_cookie_sink: Callable[[Mapping[str, str]], None] | None = None,
        resource_closer: Callable[[], object] | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._source = source
        self._sink = sink
        self._settings = settings
        self._comment_client = comment_client
        self._embedded_video_fetcher = embedded_video_fetcher
        self._browser_factory = browser_factory
        self._browser_cookies = dict(browser_cookies or {})
        self._browser_cookie_sink = browser_cookie_sink
        self._resource_closer = resource_closer
        self._clock = clock
        self._used_browser = False
        self._closed = False

    def run(self, raw_url: str) -> ArchiveReport:
        if self._closed:
            raise RuntimeError("Archive workflow is closed.")
        self._used_browser = False
        routed = route_zhihu_url(raw_url)
        target = self._collect(routed)
        embedded_video_warnings: tuple[EmbeddedVideoWarning, ...] = ()
        if self._settings.media_download and self._embedded_video_fetcher is not None:
            resolution = resolve_embedded_videos(target, get_json=self._embedded_video_fetcher)
            target = resolution.target
            embedded_video_warnings = resolution.warnings
        receipt = self._sink.archive(target)
        if not isinstance(receipt, ArchiveReceipt):
            raise TypeError("Archive sinks must return an ArchiveReceipt.")
        return ArchiveReport(
            target=target,
            receipt=receipt,
            used_browser=self._used_browser,
            media_failures=receipt.media_failures,
            embedded_video_warnings=embedded_video_warnings,
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._resource_closer is not None:
            self._resource_closer()

    def __enter__(self) -> Self:
        if self._closed:
            raise RuntimeError("Archive workflow is closed.")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _collect(self, target: ZhihuTarget) -> ArchiveTarget:
        if target.kind is TargetKind.ARTICLE:
            payload = self._single_payload(
                target,
                direct=lambda: self._source.fetch_article_payload(target),
                collection="articles",
                validate=lambda candidate: _validate_article_payload(
                    candidate,
                    source_url=target.canonical_url,
                ),
            )
            article = normalize_article(payload, source_url=target.canonical_url)
            return self._with_article_comments(article)

        if target.kind is TargetKind.ANSWER:
            payload = self._single_payload(
                target,
                direct=lambda: self._source.fetch_answer_payload(target),
                collection="answers",
                validate=lambda candidate: _validate_answer_payload(
                    candidate,
                    source_url=target.canonical_url,
                ),
            )
            answer = normalize_answer(payload, source_url=target.canonical_url)
            return self._with_answer_comments(answer)

        if target.kind is TargetKind.QUESTION:
            question_payload = self._single_payload(
                target,
                direct=lambda: self._source.fetch_question_payload(target),
                collection="questions",
                validate=lambda candidate: normalize_question(
                    candidate,
                    source_url=target.canonical_url,
                ),
            )
            question = normalize_question(
                question_payload,
                source_url=target.canonical_url,
            )
            answer_payloads = self._collection_payloads(
                target,
                collection="questions",
                direct=lambda: self._source.iter_question_answer_payloads(
                    target,
                    page_size=self._settings.page_size,
                ),
                validate=_validate_answer_payload,
            )
            answers = tuple(
                self._with_answer_comments(normalize_answer(payload)) for payload in answer_payloads
            )
            return QuestionArchive(
                question=question,
                answers=answers,
                archived_at=self._clock(),
            )

        if target.kind is TargetKind.COLUMN:
            column_payload = self._single_payload(
                target,
                direct=lambda: self._source.fetch_column_payload(target),
                collection="columns",
                validate=lambda candidate: normalize_column(
                    candidate,
                    source_url=target.canonical_url,
                ),
            )
            column = normalize_column(
                column_payload,
                source_url=target.canonical_url,
            )
            origin = ColumnRef(
                token=column.token,
                title=column.title,
                url=column.source_url,
            )
            articles: list[Article] = []
            article_payloads = self._collection_payloads(
                target,
                collection="columns",
                direct=lambda: self._source.iter_column_article_payloads(
                    target,
                    page_size=self._settings.page_size,
                ),
                validate=_validate_article_payload,
            )
            for payload in article_payloads:
                article = normalize_article(payload)
                if all(item.token != origin.token for item in article.columns):
                    article = replace(
                        article,
                        columns=(*article.columns, origin),
                    )
                articles.append(self._with_article_comments(article))
            if column.item_count == 0 and articles:
                column = replace(column, item_count=len(articles))
            return ColumnArchive(
                column=column,
                articles=tuple(articles),
                archived_at=self._clock(),
            )

        if target.kind is TargetKind.VIDEO:
            payload = self._single_payload(
                target,
                direct=lambda: self._source.fetch_video_payload(target),
                collection="zvideos",
                validate=lambda candidate: normalize_video(
                    candidate,
                    source_url=target.canonical_url,
                ),
            )
            video = normalize_video(payload, source_url=target.canonical_url)
            if not self._settings.comments:
                return video
            thread = self._comments("zvideo", video.id, video.source_url)
            return replace(video, comments=thread)

        raise AssertionError(f"unhandled target kind: {target.kind}")

    def _single_payload(
        self,
        target: ZhihuTarget,
        *,
        direct: Callable[[], Mapping[str, object]],
        collection: str,
        validate: Callable[[Mapping[str, object]], object],
    ) -> Mapping[str, object]:
        def validated(payload: Mapping[str, object]) -> Mapping[str, object]:
            validate(payload)
            return payload

        mode = self._settings.browser_fallback
        if mode is BrowserFallbackMode.ALWAYS:
            return validated(self._browser_payload(target, collection=collection))
        try:
            return validated(direct())
        except (
            InvalidZhihuPayloadError,
            InvalidResponseError,
            NormalizationError,
            ZhihuHttpError,
            TransportError,
        ):
            if mode is BrowserFallbackMode.NEVER:
                raise
            return validated(self._browser_payload(target, collection=collection))

    def _browser_payload(
        self,
        target: ZhihuTarget,
        *,
        collection: str,
    ) -> Mapping[str, object]:
        if self._browser_factory is None:
            raise BrowserFallbackUnavailableError("HTTP 抓取失败，但当前没有配置浏览器回退。")
        with self._browser_factory() as browser:
            if self._browser_cookies:
                browser.set_cookie_dict(self._browser_cookies)
            document = browser.fetch_html(target.canonical_url)
            exported_cookies = browser.cookie_dict()
            if exported_cookies:
                self._browser_cookies.update(exported_cookies)
                if self._browser_cookie_sink is not None:
                    self._browser_cookie_sink(exported_cookies)
        self._used_browser = True
        return extract_entity_payload(
            document,
            collection=collection,
            entity_id=target.content_id,
        )

    def _collection_payloads(
        self,
        target: ZhihuTarget,
        *,
        collection: str,
        direct: Callable[[], Iterator[Mapping[str, object]]],
        validate: Callable[[Mapping[str, object]], object],
    ) -> tuple[Mapping[str, object], ...]:
        def collect_validated() -> tuple[Mapping[str, object], ...]:
            payloads = tuple(direct())
            for payload in payloads:
                validate(payload)
            return payloads

        try:
            return collect_validated()
        except (
            InvalidZhihuPayloadError,
            InvalidResponseError,
            NormalizationError,
            ZhihuHttpError,
            TransportError,
        ):
            if self._settings.browser_fallback is BrowserFallbackMode.NEVER:
                raise
            self._browser_payload(target, collection=collection)
            return collect_validated()

    def _with_article_comments(self, article: Article) -> Article:
        if not self._settings.comments:
            return article
        return replace(
            article,
            comments=self._comments("article", article.id, article.source_url),
        )

    def _with_answer_comments(self, answer: Answer) -> Answer:
        if not self._settings.comments:
            return answer
        return replace(
            answer,
            comments=self._comments("answer", answer.id, answer.source_url),
        )

    def _comments(self, target_kind: str, target_id: str, source_url: str):
        if self._comment_client is None:
            raise RuntimeError("评论已启用，但没有可用的知乎请求客户端。")

        def fetch():
            return fetch_comment_thread(
                self._comment_client,
                target_kind=target_kind,
                target_id=target_id,
                root_limit=self._settings.comment_roots,
                reply_limit=self._settings.comment_replies,
            )

        try:
            return fetch()
        except (
            InvalidCommentPayloadError,
            InvalidResponseError,
            ZhihuHttpError,
            TransportError,
        ):
            if self._settings.browser_fallback is BrowserFallbackMode.NEVER:
                raise
            collections = {
                "article": "articles",
                "answer": "answers",
                "zvideo": "zvideos",
            }
            self._browser_payload(
                route_zhihu_url(source_url),
                collection=collections[target_kind],
            )
            return fetch()


def _validate_article_payload(
    payload: Mapping[str, object],
    *,
    source_url: str | None = None,
) -> None:
    article = normalize_article(payload, source_url=source_url)
    if not article.blocks:
        raise NormalizationError("article payload is missing full content")


def _validate_answer_payload(
    payload: Mapping[str, object],
    *,
    source_url: str | None = None,
) -> None:
    answer = normalize_answer(payload, source_url=source_url)
    if not answer.blocks:
        raise NormalizationError("answer payload is missing full content")
