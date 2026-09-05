"""Archive normalized media assets behind one small, target-level interface."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Collection, Iterable, Iterator, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Protocol
from urllib.parse import unquote, urlsplit

from .domain import (
    Answer,
    ArchiveTarget,
    Article,
    Block,
    ColumnArchive,
    Comment,
    CommentThread,
    ListBlock,
    MediaAsset,
    MediaBlock,
    MediaKind,
    MediaRendition,
    QuestionArchive,
    Quote,
    Video,
)
from .media import MediaDownloadError, MediaDownloadReceipt, download_media, media_source_identity


class AssetDownloader(Protocol):
    def __call__(
        self, source_url: str, destination: Path, *, expected_size: int | None = None
    ) -> MediaDownloadReceipt: ...


class MediaArchiveRole(StrEnum):
    """The role an asset plays in a readable archive."""

    CONTENT = "content"
    COVER = "cover"
    PRIMARY_VIDEO = "primary_video"


@dataclass(frozen=True, slots=True)
class MediaArchiveFailure:
    """A non-secret, structured description of one failed asset download."""

    asset_id: str
    kind: MediaKind
    role: MediaArchiveRole
    source_url: str
    destination: Path
    error_type: str
    reason: str

    @property
    def display_message(self) -> str:
        """Return a concise warning suitable for a CLI or agent report."""

        labels = {
            MediaArchiveRole.CONTENT: "正文媒体",
            MediaArchiveRole.COVER: "封面",
            MediaArchiveRole.PRIMARY_VIDEO: "独立视频主文件",
        }
        return f"{labels[self.role]}下载失败，已保留远程链接：{self.asset_id}（{self.reason}）"


class PrimaryVideoDownloadError(MediaDownloadError):
    """Raised when the required main file of an independent zvideo fails."""

    def __init__(self, failure: MediaArchiveFailure) -> None:
        self.failure = failure
        super().__init__(failure.display_message)


@dataclass(frozen=True, slots=True)
class AssetArchiveReceipt:
    """Downloaded files and the URL aliases renderers can replace."""

    source_paths: Mapping[str, str]
    downloads: tuple[MediaDownloadReceipt, ...]
    failures: tuple[MediaArchiveFailure, ...] = ()


@dataclass(frozen=True, slots=True)
class _AssetRequest:
    asset: MediaAsset
    role: MediaArchiveRole

    @property
    def required(self) -> bool:
        return self.role is MediaArchiveRole.PRIMARY_VIDEO


def archive_assets(
    target: ArchiveTarget,
    media_directory: Path,
    *,
    downloader: AssetDownloader = download_media,
) -> AssetArchiveReceipt:
    """Download every unique media asset reachable from ``target``.

    Images and animations preserve the normalizer's first (original) rendition.
    Videos select the largest rendition with known dimensions.  Exact ties and
    renditions without dimensions retain source order, keeping selection stable.
    """

    media_directory = Path(media_directory)
    requests = tuple(_unique_requests(_target_requests(target)))
    downloadable = tuple(
        (request, rendition)
        for request in requests
        if (rendition := _select_rendition(request.asset)) is not None
    )
    if not downloadable:
        return AssetArchiveReceipt(MappingProxyType({}), ())

    media_directory.mkdir(parents=True, exist_ok=True)
    source_paths: dict[str, str] = {}
    downloads: list[MediaDownloadReceipt] = []
    failures: list[MediaArchiveFailure] = []
    selected_sources: dict[str, str] = {}

    for request, selected in downloadable:
        asset = request.asset
        existing_path = selected_sources.get(selected.source_url)
        if existing_path is None:
            filename = _archive_filename(asset, selected)
            destination = media_directory / filename
            try:
                if selected.size_bytes is not None and selected.size_bytes > 0:
                    receipt = downloader(
                        selected.source_url, destination, expected_size=selected.size_bytes
                    )
                else:
                    receipt = downloader(selected.source_url, destination)
            except MediaDownloadError as error:
                failure = MediaArchiveFailure(
                    asset_id=asset.id,
                    kind=asset.kind,
                    role=request.role,
                    source_url=selected.source_url,
                    destination=destination,
                    error_type=type(error).__name__,
                    reason=str(error) or type(error).__name__,
                )
                if request.required:
                    raise PrimaryVideoDownloadError(failure) from error
                failures.append(failure)
                continue
            relative_path = PurePosixPath(media_directory.name, filename).as_posix()
            selected_sources[selected.source_url] = relative_path
            downloads.append(receipt)
        else:
            relative_path = existing_path

        # Every rendition identifies the same logical asset.  Mapping all aliases
        # lets renderers replace whichever rendition appeared in the source.
        for rendition in asset.renditions:
            if rendition.source_url:
                source_paths[rendition.source_url] = relative_path

    return AssetArchiveReceipt(
        source_paths=MappingProxyType(source_paths),
        downloads=tuple(downloads),
        failures=tuple(failures),
    )


def _target_requests(target: ArchiveTarget) -> Iterator[_AssetRequest]:
    if isinstance(target, Article):
        yield from _article_requests(target)
        return
    if isinstance(target, Answer):
        yield from _answer_requests(target)
        return
    if isinstance(target, QuestionArchive):
        yield from _requests(_blocks_assets(target.question.detail))
        for answer in target.answers:
            yield from _answer_requests(answer)
        return
    if isinstance(target, ColumnArchive):
        for article in target.articles:
            yield from _article_requests(article)
        return
    if isinstance(target, Video):
        yield _AssetRequest(target.asset, MediaArchiveRole.PRIMARY_VIDEO)
        yield from _requests(_blocks_assets(target.description))
        yield from _requests(_thread_assets(target.comments))
        if target.cover_url:
            yield _AssetRequest(
                _remote_image(
                    asset_id=f"zvideo-{target.id}-cover",
                    source_url=target.cover_url,
                    alt_text=target.title,
                ),
                MediaArchiveRole.COVER,
            )
        return
    raise TypeError(f"unsupported archive target: {type(target).__name__}")


def _article_requests(article: Article) -> Iterator[_AssetRequest]:
    yield from _requests(_blocks_assets(article.blocks))
    yield from _requests(_thread_assets(article.comments))
    if article.cover_url:
        yield _AssetRequest(
            _remote_image(
                asset_id=f"article-{article.id}-cover",
                source_url=article.cover_url,
                alt_text=article.title,
            ),
            MediaArchiveRole.COVER,
        )


def _answer_requests(answer: Answer) -> Iterator[_AssetRequest]:
    yield from _requests(_blocks_assets(answer.blocks))
    yield from _requests(_thread_assets(answer.comments))


def _requests(assets: Iterable[MediaAsset]) -> Iterator[_AssetRequest]:
    for asset in assets:
        yield _AssetRequest(asset, MediaArchiveRole.CONTENT)


def _blocks_assets(blocks: Iterable[Block]) -> Iterator[MediaAsset]:
    for block in blocks:
        if isinstance(block, MediaBlock):
            yield block.asset
        elif isinstance(block, Quote):
            yield from _blocks_assets(block.blocks)
        elif isinstance(block, ListBlock):
            for item in block.items:
                yield from _blocks_assets(item)


def _thread_assets(thread: CommentThread | None) -> Iterator[MediaAsset]:
    if thread is None:
        return
    for comment in thread.comments:
        yield from _comment_assets(comment)


def _comment_assets(comment: Comment) -> Iterator[MediaAsset]:
    yield from _blocks_assets(comment.blocks)
    for reply in comment.replies:
        yield from _comment_assets(reply)


def _unique_requests(requests: Iterable[_AssetRequest]) -> Iterator[_AssetRequest]:
    seen: set[str] = set()
    for request in requests:
        if request.asset.id in seen:
            continue
        seen.add(request.asset.id)
        yield request


def _select_rendition(asset: MediaAsset) -> MediaRendition | None:
    available = tuple(rendition for rendition in asset.renditions if rendition.source_url.strip())
    if not available:
        return None
    if asset.kind is not MediaKind.VIDEO:
        return available[0]
    return max(available, key=_video_quality)


def _video_quality(rendition: MediaRendition) -> tuple[int, int, int]:
    width = rendition.width
    height = rendition.height
    if width is None or height is None or width <= 0 or height <= 0:
        area = -1
    else:
        area = width * height
    return (
        area,
        rendition.bitrate if rendition.bitrate is not None else -1,
        rendition.size_bytes if rendition.size_bytes is not None else -1,
    )


def _remote_image(*, asset_id: str, source_url: str, alt_text: str) -> MediaAsset:
    return MediaAsset(
        id=asset_id,
        kind=MediaKind.IMAGE,
        renditions=(MediaRendition(source_url=source_url),),
        alt_text=alt_text,
    )


_MIME_EXTENSIONS: Mapping[str, str] = {
    "image/avif": ".avif",
    "image/bmp": ".bmp",
    "image/gif": ".gif",
    "image/heic": ".heic",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/svg+xml": ".svg",
    "image/webp": ".webp",
    "video/mp2t": ".ts",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
    "video/x-m4v": ".m4v",
    "video/x-matroska": ".mkv",
}
_IMAGE_EXTENSIONS = frozenset(
    {".avif", ".bmp", ".gif", ".heic", ".jpeg", ".jpg", ".png", ".svg", ".webp"}
)
_ANIMATION_EXTENSIONS = frozenset({".gif", ".png", ".webp"})
_VIDEO_EXTENSIONS = frozenset({".m4v", ".mkv", ".mov", ".mp4", ".ts", ".webm"})
_SAFE_STEM = re.compile(r"[^a-z0-9._-]+")


def _archive_filename(asset: MediaAsset, rendition: MediaRendition) -> str:
    stem = _SAFE_STEM.sub("-", asset.id.casefold()).strip("._-")[:48]
    if not stem:
        stem = asset.kind.value
    extension = _extension(asset.kind, rendition)
    stable_identity = "\0".join(
        (
            asset.kind.value,
            asset.id,
            media_source_identity(rendition.source_url),
            rendition.mime_type or "",
            str(rendition.width or ""),
            str(rendition.height or ""),
            str(rendition.bitrate or ""),
            str(rendition.size_bytes or ""),
            extension,
        )
    )
    digest = hashlib.sha256(stable_identity.encode()).hexdigest()[:10]
    return f"{stem}-{digest}{extension}"


def _extension(kind: MediaKind, rendition: MediaRendition) -> str:
    allowed = _allowed_extensions(kind)
    mime_type = (rendition.mime_type or "").partition(";")[0].strip().casefold()
    mime_extension = _MIME_EXTENSIONS.get(mime_type)
    if mime_extension is not None and mime_extension in allowed:
        return mime_extension

    path_suffix = PurePosixPath(unquote(urlsplit(rendition.source_url).path)).suffix.casefold()
    if path_suffix == ".jpeg":
        path_suffix = ".jpg"
    if path_suffix in allowed:
        return path_suffix

    if kind is MediaKind.VIDEO:
        return ".mp4"
    if kind is MediaKind.ANIMATION:
        return ".gif"
    return ".jpg"


def _allowed_extensions(kind: MediaKind) -> Collection[str]:
    if kind is MediaKind.VIDEO:
        return _VIDEO_EXTENSIONS
    if kind is MediaKind.ANIMATION:
        return _ANIMATION_EXTENSIONS
    return _IMAGE_EXTENSIONS
