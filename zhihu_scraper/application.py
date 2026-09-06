"""Public archive workflow: route, fetch, normalize, enrich, and save."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Literal, Protocol, Self, cast

from .archive import ArchiveReceipt
from .assets import MediaArchiveFailure
from .comments import CommentClient, InvalidCommentPayloadError, fetch_comment_thread
from .domain import (
    Answer,
    ArchiveTarget,
    Article,
    ColumnArchive,
    ColumnRef,
    CommentThread,
    QuestionArchive,
)
from .embedded_video import EmbeddedVideoResolver, EmbeddedVideoWarning
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

    def begin_batch(self, target: ColumnArchive | QuestionArchive) -> BatchArchiveSink: ...


class BatchArchiveSink(Protocol):
    @property
    def progress_path(self) -> Path: ...

    def write_item(self, item: Article | Answer) -> ArchiveReceipt: ...

    def finish(self, target: ColumnArchive | QuestionArchive) -> ArchiveReceipt: ...

    def interrupt(self) -> ArchiveReceipt: ...


@dataclass(frozen=True, slots=True)
class BatchProgress:
    stage: Literal["started", "saved", "completed", "interrupted"]
    completed: int
    total: int | None
    current_title: str | None = None
    progress_path: Path | None = None
    media_failures: tuple[MediaArchiveFailure, ...] = ()


class BatchArchiveInterruptedError(RuntimeError):
    """A batch stopped after its completed items were saved to readable files."""

    def __init__(
        self, receipt: ArchiveReceipt, completed: int, *, progress_saved: bool = True
    ) -> None:
        self.receipt = receipt
        self.completed = completed
        self.progress_saved = progress_saved
        progress_message = (
            f"进度记录：{receipt.progress_path}"
            if progress_saved
            else "进度记录未能更新，已写入的文件仍保留在保存目录中"
        )
        super().__init__(f"本轮归档未完成，已保存 {completed} 项；{progress_message}")


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
        progress: Callable[[BatchProgress], None] | None = None,
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
        self._progress = progress
        self._batch: BatchArchiveSink | None = None
        self._batch_completed = 0
        self._batch_total: int | None = None
        self._video_resolver: EmbeddedVideoResolver | None = None
        self._used_browser = False
        self._closed = False

    def run(self, raw_url: str) -> ArchiveReport:
        if self._closed:
            raise RuntimeError("Archive workflow is closed.")
        self._used_browser = False
        self._batch = None
        self._batch_completed = 0
        self._batch_total = None
        self._video_resolver = (
            EmbeddedVideoResolver(self._embedded_video_fetcher)
            if self._settings.media_download and self._embedded_video_fetcher is not None
            else None
        )
        routed = route_zhihu_url(raw_url)
        try:
            target = self._collect(routed)
            if self._batch is not None:
                if not isinstance(target, (ColumnArchive, QuestionArchive)):
                    raise TypeError("batch archives must produce a collection target")
                receipt = self._batch.finish(target)
                self._emit_progress("completed")
            else:
                target = self._enrich(target)
                receipt = self._sink.archive(target)
        except BaseException as error:
            if self._batch is None:
                raise
            progress_saved = True
            try:
                partial_receipt = self._batch.interrupt()
            except BaseException:
                # A secondary checkpoint failure must not replace the cause of interruption.
                progress_saved = False
                partial_receipt = ArchiveReceipt(
                    self._batch.progress_path.parent,
                    None,
                    None,
                    progress_path=self._batch.progress_path,
                )
            try:
                self._emit_progress("interrupted")
            except BaseException:
                pass
            if not isinstance(error, Exception):
                raise
            raise BatchArchiveInterruptedError(
                partial_receipt, self._batch_completed, progress_saved=progress_saved
            ) from error
        if not isinstance(receipt, ArchiveReceipt):
            raise TypeError("Archive sinks must return an ArchiveReceipt.")
        return ArchiveReport(
            target=target,
            receipt=receipt,
            used_browser=self._used_browser,
            media_failures=receipt.media_failures,
            embedded_video_warnings=tuple(self._video_resolver.warnings.values())
            if self._video_resolver is not None
            else (),
        )

    def _enrich[T: ArchiveTarget](self, target: T) -> T:
        if self._video_resolver is None:
            return target
        return cast(T, self._video_resolver.resolve(target).target)

    def _begin_batch(self, target: ColumnArchive | QuestionArchive, total: int) -> None:
        self._batch = self._sink.begin_batch(target)
        self._batch_total = total or None
        self._emit_progress("started")

    def _save_batch_item[T: (Article, Answer)](self, item: T) -> T:
        if self._batch is None:
            raise AssertionError("a batch must start before saving items")
        enriched = self._enrich(item)
        receipt = self._batch.write_item(enriched)
        self._batch_completed += 1
        self._emit_progress(
            "saved", current_title=item.title, media_failures=receipt.media_failures
        )
        return enriched

    def _emit_progress(
        self,
        stage: Literal["started", "saved", "completed", "interrupted"],
        *,
        current_title: str | None = None,
        media_failures: tuple[MediaArchiveFailure, ...] = (),
    ) -> None:
        if self._progress is not None:
            self._progress(
                BatchProgress(
                    stage,
                    self._batch_completed,
                    self._batch_total,
                    current_title,
                    self._batch.progress_path if self._batch is not None else None,
                    media_failures,
                )
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
            batch_target = self._enrich(
                QuestionArchive(question=question, answers=(), archived_at=self._clock())
            )
            self._begin_batch(batch_target, question.answer_count)
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
                self._save_batch_item(self._with_answer_comments(normalize_answer(payload)))
                for payload in answer_payloads
            )
            return replace(batch_target, answers=answers)

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
            column_batch = ColumnArchive(column=column, articles=(), archived_at=self._clock())
            self._begin_batch(column_batch, column.item_count)
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
                articles.append(self._save_batch_item(self._with_article_comments(article)))
            if column.item_count == 0 and articles:
                column = replace(column, item_count=len(articles))
            return replace(column_batch, column=column, articles=tuple(articles))

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
        return next(
            self._recover(
                direct=lambda: iter((validated(direct()),)),
                recovery=lambda: iter(
                    (validated(self._browser_payload(target, collection=collection)),)
                ),
            )
        )

    def _recover[T](
        self,
        *,
        direct: Callable[[], Iterator[T]],
        recovery: Callable[[], Iterator[T]],
    ) -> Iterator[T]:
        """Apply one recovery policy to single payloads, streams, and comments."""
        try:
            yield from direct()
        except (
            InvalidZhihuPayloadError,
            InvalidCommentPayloadError,
            InvalidResponseError,
            NormalizationError,
            ZhihuHttpError,
            TransportError,
        ) as error:
            if self._settings.browser_fallback is BrowserFallbackMode.NEVER or (
                isinstance(error, ZhihuHttpError) and error.status_code == 429
            ):
                raise
            yield from recovery()

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
    ) -> Iterator[Mapping[str, object]]:
        seen: set[str] = set()

        def collect_validated() -> Iterator[Mapping[str, object]]:
            for payload in direct():
                validate(payload)
                identifier = str(payload["id"])
                if identifier in seen:
                    continue
                seen.add(identifier)
                yield payload

        def refresh_and_collect() -> Iterator[Mapping[str, object]]:
            self._browser_payload(target, collection=collection)
            yield from collect_validated()

        yield from self._recover(direct=collect_validated, recovery=refresh_and_collect)

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

    def _comments(self, target_kind: str, target_id: str, source_url: str) -> CommentThread:
        client = self._comment_client
        if client is None:
            raise RuntimeError("评论已启用，但没有可用的知乎请求客户端。")

        def fetch() -> CommentThread:
            return fetch_comment_thread(
                client,
                target_kind=target_kind,
                target_id=target_id,
                root_limit=self._settings.comment_roots,
                reply_limit=self._settings.comment_replies,
            )

        def refresh_and_fetch() -> Iterator[CommentThread]:
            collections = {
                "article": "articles",
                "answer": "answers",
                "zvideo": "zvideos",
            }
            self._browser_payload(
                route_zhihu_url(source_url),
                collection=collections[target_kind],
            )
            yield fetch()

        return next(self._recover(direct=lambda: iter((fetch(),)), recovery=refresh_and_fetch))


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
