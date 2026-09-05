"""Resolve optional Zhihu video cards without mixing page URLs with media files."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from urllib.parse import urlsplit

from .domain import (
    Answer,
    ArchiveTarget,
    Article,
    Block,
    ColumnArchive,
    Comment,
    CommentThread,
    EmbeddedVideo,
    Link,
    ListBlock,
    MediaAsset,
    MediaBlock,
    MediaKind,
    MediaRendition,
    Paragraph,
    QuestionArchive,
    Quote,
    Video,
)
from .http import InvalidResponseError, RetryWaitError, TransportError, ZhihuHttpError
from .normalize import normalize_video_renditions


@dataclass(frozen=True, slots=True)
class EmbeddedVideoWarning:
    video_id: str
    source_url: str
    reason: str
    error_type: str

    @property
    def display_message(self) -> str:
        reasons = {
            "access_denied": "当前会话无法访问",
            "rate_limited": "已按限流要求停止解析",
            "request_failed": "请求未成功",
            "unavailable": "没有可下载的视频文件",
        }
        return (
            f"内嵌视频未下载，已保留原视频链接：{self.video_id}"
            f"（{reasons.get(self.reason, '视频暂不可用')}）"
        )


@dataclass(frozen=True, slots=True)
class EmbeddedVideoResolution:
    target: ArchiveTarget
    warnings: tuple[EmbeddedVideoWarning, ...]


def resolve_embedded_videos(
    target: ArchiveTarget,
    *,
    get_json: Callable[[str], object],
) -> EmbeddedVideoResolution:
    """Enrich video cards once per lens ID, keeping failures as readable links.

    The caller supplies its existing HTTP client. Only the fixed lens endpoint
    is queried; denied access and rate limits stop further optional requests.
    """

    resolver = _EmbeddedVideoResolver(get_json)
    resolved = resolver.resolve_target(target)
    return EmbeddedVideoResolution(resolved, tuple(resolver.warnings.values()))


@dataclass(frozen=True, slots=True)
class _UnavailableVideo:
    reason: str
    error_type: str


class _EmbeddedVideoResolver:
    def __init__(self, get_json: Callable[[str], object]) -> None:
        self._get_json = get_json
        self._resolved: dict[str, MediaAsset | _UnavailableVideo] = {}
        self._blocked: _UnavailableVideo | None = None
        self.warnings: dict[str, EmbeddedVideoWarning] = {}

    def resolve_target(self, target: ArchiveTarget) -> ArchiveTarget:
        if isinstance(target, Article):
            return self._resolve_entry(target)
        if isinstance(target, Answer):
            return self._resolve_entry(target)
        if isinstance(target, QuestionArchive):
            return replace(
                target,
                question=replace(target.question, detail=self._blocks(target.question.detail)),
                answers=tuple(self._resolve_entry(answer) for answer in target.answers),
            )
        if isinstance(target, ColumnArchive):
            return replace(
                target, articles=tuple(self._resolve_entry(article) for article in target.articles)
            )
        if isinstance(target, Video):
            return replace(
                target,
                description=self._blocks(target.description),
                comments=self._comments(target.comments),
            )
        raise TypeError(f"unsupported archive target: {type(target).__name__}")

    def _resolve_entry[T: (Article, Answer)](self, target: T) -> T:
        return replace(
            target, blocks=self._blocks(target.blocks), comments=self._comments(target.comments)
        )

    def _blocks(self, blocks: tuple[Block, ...]) -> tuple[Block, ...]:
        resolved: list[Block] = []
        for block in blocks:
            if isinstance(block, EmbeddedVideo):
                outcome = self._video(block.video_id)
                if isinstance(outcome, MediaAsset):
                    resolved.extend(
                        (
                            MediaBlock(replace(outcome, alt_text=block.title)),
                            Paragraph((Link("原始视频页面", block.source_url),)),
                        )
                    )
                else:
                    self.warnings.setdefault(
                        block.video_id,
                        EmbeddedVideoWarning(
                            block.video_id, block.source_url, outcome.reason, outcome.error_type
                        ),
                    )
                    resolved.append(block)
            elif isinstance(block, Quote):
                resolved.append(replace(block, blocks=self._blocks(block.blocks)))
            elif isinstance(block, ListBlock):
                resolved.append(
                    replace(block, items=tuple(self._blocks(item) for item in block.items))
                )
            else:
                resolved.append(block)
        return tuple(resolved)

    def _comments(self, thread: CommentThread | None) -> CommentThread | None:
        if thread is None:
            return None
        return replace(
            thread, comments=tuple(self._comment(comment) for comment in thread.comments)
        )

    def _comment(self, comment: Comment) -> Comment:
        return replace(
            comment,
            blocks=self._blocks(comment.blocks),
            replies=tuple(self._comment(reply) for reply in comment.replies),
        )

    def _video(self, video_id: str) -> MediaAsset | _UnavailableVideo:
        if video_id in self._resolved:
            return self._resolved[video_id]
        result = self._fetch_video(video_id)
        self._resolved[video_id] = result
        return result

    def _fetch_video(self, video_id: str) -> MediaAsset | _UnavailableVideo:
        if self._blocked is not None:
            return self._blocked
        if not re.fullmatch(r"[0-9]{1,30}", video_id):
            return _UnavailableVideo("unavailable", "InvalidVideoIdentifier")
        try:
            payload = self._get_json(f"https://lens.zhihu.com/api/v4/videos/{video_id}")
        except ZhihuHttpError as error:
            failure = _UnavailableVideo(
                _http_failure_reason(error.status_code), type(error).__name__
            )
            if error.status_code in {401, 403, 429}:
                self._blocked = failure
            return failure
        except RetryWaitError:
            self._blocked = _UnavailableVideo("rate_limited", "RetryWaitError")
            return self._blocked
        except (TransportError, InvalidResponseError, OSError, ValueError) as error:
            return _UnavailableVideo("request_failed", type(error).__name__)
        if not isinstance(payload, Mapping):
            return _UnavailableVideo("unavailable", "InvalidVideoPayload")
        error_payload = payload.get("error")
        error_code = error_payload.get("code") if isinstance(error_payload, Mapping) else None
        if isinstance(error_code, int) and error_code in {401, 403, 429}:
            self._blocked = _UnavailableVideo(_http_failure_reason(error_code), "VideoAccessError")
            return self._blocked
        renditions = tuple(
            rendition
            for rendition in normalize_video_renditions(payload)
            if _is_downloadable_video(rendition)
        )
        if not renditions:
            return _UnavailableVideo("unavailable", "InvalidVideoPayload")
        return MediaAsset(
            id=f"embedded-video-{video_id}", kind=MediaKind.VIDEO, renditions=renditions
        )


def _http_failure_reason(status_code: int) -> str:
    if status_code == 429:
        return "rate_limited"
    if status_code in {401, 403}:
        return "access_denied"
    return "request_failed"


def _is_downloadable_video(rendition: MediaRendition) -> bool:
    try:
        parsed = urlsplit(rendition.source_url)
        parsed.port
    except ValueError:
        return False
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or any(character.isspace() for character in rendition.source_url)
        or parsed.hostname in {"zhihu.com", "www.zhihu.com", "zhuanlan.zhihu.com", "lens.zhihu.com"}
    ):
        return False
    path = parsed.path.casefold()
    if path.endswith((".m3u8", ".mpd", ".html", ".htm")):
        return False
    return path.endswith((".mp4", ".webm", ".mov", ".m4v")) or rendition.mime_type in {
        "video/mp4",
        "video/webm",
        "video/quicktime",
        "video/x-m4v",
    }
