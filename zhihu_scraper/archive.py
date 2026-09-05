"""Filesystem archive sink for every normalized Zhihu target."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, replace
from functools import partial
from html import unescape
from pathlib import Path
from urllib.parse import quote

from .assets import AssetArchiveReceipt, AssetDownloader, MediaArchiveFailure, archive_assets
from .domain import (
    Answer,
    ArchiveTarget,
    Article,
    ColumnArchive,
    ColumnRef,
    QuestionArchive,
    Video,
)
from .filenames import safe_filename
from .media import MediaDownloadReceipt, download_media
from .pdf_export import PdfDocument, PdfExporter, export_pdfs, pdf_source_url
from .render import (
    ColumnRenderContext,
    HtmlRenderer,
    MarkdownRenderer,
    RenderNavigationItem,
)
from .settings import ArchiveSettings
from .urls import UnsupportedZhihuUrlError, route_zhihu_url

MediaDownloader = AssetDownloader
_MARKDOWN_SOURCE = re.compile(
    r"^> (知乎原文|知乎原问题|知乎专栏)：\[[^\n]*\]\(([^\n]*)\)$", re.MULTILINE
)
_HTML_SOURCE = re.compile(r'<a href="([^"]*)">(知乎原文|知乎原问题|知乎专栏)</a>')


@dataclass(frozen=True, slots=True)
class ArchiveReceipt:
    entry_directory: Path
    markdown_path: Path | None
    html_path: Path | None
    child_markdown_paths: tuple[Path, ...] = ()
    child_html_paths: tuple[Path, ...] = ()
    media_downloads: tuple[MediaDownloadReceipt, ...] = ()
    media_failures: tuple[MediaArchiveFailure, ...] = ()
    pdf_path: Path | None = None
    child_pdf_paths: tuple[Path, ...] = ()


class LocalArchive:
    """Write readable Markdown, HTML, and local media without hidden state."""

    def __init__(
        self,
        root: Path,
        *,
        markdown: bool = True,
        html: bool = False,
        pdf: bool = False,
        media_download: bool = True,
        downloader: MediaDownloader = download_media,
        pdf_exporter: PdfExporter = export_pdfs,
    ) -> None:
        if not any((markdown, html, pdf)):
            raise ValueError("至少启用 Markdown 或 HTML 或 PDF 中的一种输出。")
        self._root = Path(root)
        self._markdown = markdown
        self._html = html
        self._pdf = pdf
        self._media_download = media_download
        self._downloader = downloader
        self._pdf_exporter = pdf_exporter

    @classmethod
    def from_settings(
        cls,
        settings: ArchiveSettings,
        *,
        downloader: MediaDownloader | None = None,
        pdf_exporter: PdfExporter = export_pdfs,
    ) -> LocalArchive:
        return cls(
            settings.output_dir,
            markdown=settings.markdown,
            html=settings.html,
            pdf=settings.pdf,
            pdf_exporter=pdf_exporter,
            media_download=settings.media_download,
            downloader=downloader
            or partial(
                download_media,
                proxy=settings.proxy,
                timeout=settings.timeout,
                max_retries=settings.retries,
            ),
        )

    def archive(self, target: ArchiveTarget) -> ArchiveReceipt:
        self._root.mkdir(parents=True, exist_ok=True)
        if isinstance(target, ColumnArchive):
            return self._archive_column(target)
        return self._archive_standalone(target)

    def _archive_standalone(
        self,
        target: ArchiveTarget,
    ) -> ArchiveReceipt:
        title = target.title
        entry_directory = self._entry_directory(
            title=title,
            target_type=_target_type(target),
            target_id=target.id,
            source_url=target.source_url,
        )
        filename = _DocumentNames(entry_directory).name_for(
            title=title,
            source_url=target.source_url,
            target_type=_target_type(target),
            target_id=target.id,
        )
        entry_directory.mkdir(parents=True, exist_ok=True)

        assets = self._archive_media(target, entry_directory)
        render_paths = assets.source_paths
        markdown_path = entry_directory / f"{filename}.md" if self._markdown else None
        html_path = entry_directory / f"{filename}.html" if self._html else None
        pdf_path = entry_directory / f"{filename}.pdf" if self._pdf else None

        if markdown_path is not None:
            _atomic_write_text(
                markdown_path,
                MarkdownRenderer().render(
                    target,
                    media_paths=render_paths,
                ),
            )
        if html_path is not None:
            _atomic_write_text(
                html_path,
                HtmlRenderer().render(
                    target,
                    media_paths=render_paths,
                ),
            )
            self._write_html_assets(entry_directory / "assets")

        if pdf_path is not None:
            self._pdf_exporter(
                (PdfDocument(pdf_path, HtmlRenderer().render(target, media_paths=render_paths)),),
                resource_root=entry_directory,
            )

        return ArchiveReceipt(
            entry_directory=entry_directory,
            markdown_path=markdown_path,
            html_path=html_path,
            media_downloads=assets.downloads,
            media_failures=assets.failures,
            pdf_path=pdf_path,
        )

    def _archive_column(
        self,
        archive: ColumnArchive,
    ) -> ArchiveReceipt:
        column = archive.column
        entry_directory = self._entry_directory(
            title=column.title,
            target_type="column",
            target_id=column.token,
            source_url=column.source_url,
        )
        column_filename = _DocumentNames(entry_directory).name_for(
            title=column.title,
            source_url=column.source_url,
            target_type="column",
            target_id=column.token,
        )
        entry_directory.mkdir(parents=True, exist_ok=True)
        assets = self._archive_media(archive, entry_directory)
        render_paths = assets.source_paths

        article_names = _unique_article_names(archive.articles, entry_directory / "内容")
        directory_entries = {
            article.id: RenderNavigationItem(
                title=article.title,
                markdown_href=_relative_href(f"内容/{name}.md") if self._markdown else "",
                html_href=_relative_href(f"内容/{name}.html") if self._html else "",
            )
            for article, name in zip(archive.articles, article_names, strict=True)
        }
        markdown_path = entry_directory / f"{column_filename}.md" if self._markdown else None
        html_path = entry_directory / f"{column_filename}.html" if self._html else None
        pdf_path = entry_directory / f"{column_filename}.pdf" if self._pdf else None
        markdown_renderer = MarkdownRenderer()
        html_renderer = HtmlRenderer()
        catalogs: list[tuple[Path, str]] = []
        if markdown_path is not None:
            catalogs.append(
                (
                    markdown_path,
                    markdown_renderer.render(archive, directory_entries=directory_entries),
                )
            )
        if html_path is not None:
            catalogs.append(
                (
                    html_path,
                    html_renderer.render(archive, directory_entries=directory_entries),
                )
            )

        documents: list[tuple[Path, str]] = []
        pdf_documents: list[PdfDocument] = []
        child_markdown_paths: list[Path] = []
        child_html_paths: list[Path] = []
        child_pdf_paths: list[Path] = []
        if archive.articles:
            content_directory = entry_directory / "内容"
            child_media_paths = {
                source_url: f"../{relative_path}"
                for source_url, relative_path in render_paths.items()
            }
            column_ref = ColumnRef(
                token=column.token,
                title=column.title,
                url=column.source_url,
            )
            directory_item = RenderNavigationItem(
                title=column.title,
                markdown_href=_relative_href(f"../{column_filename}.md") if self._markdown else "",
                html_href=_relative_href(f"../{column_filename}.html") if self._html else "",
            )
            for index, (article, name) in enumerate(
                zip(archive.articles, article_names, strict=True)
            ):
                previous_item = (
                    _article_navigation(
                        archive.articles[index - 1],
                        article_names[index - 1],
                        markdown=self._markdown,
                        html=self._html,
                    )
                    if index > 0
                    else None
                )
                next_item = (
                    _article_navigation(
                        archive.articles[index + 1],
                        article_names[index + 1],
                        markdown=self._markdown,
                        html=self._html,
                    )
                    if index + 1 < len(archive.articles)
                    else None
                )
                context = ColumnRenderContext(
                    column=column_ref,
                    directory=directory_item,
                    item_count=column.item_count,
                    previous=previous_item,
                    next=next_item,
                )
                if self._markdown:
                    article_markdown = content_directory / f"{name}.md"
                    documents.append(
                        (
                            article_markdown,
                            markdown_renderer.render(
                                article,
                                media_paths=child_media_paths,
                                column_context=context,
                            ),
                        )
                    )
                    child_markdown_paths.append(article_markdown)
                if self._html:
                    article_html = content_directory / f"{name}.html"
                    documents.append(
                        (
                            article_html,
                            html_renderer.render(
                                article,
                                media_paths=child_media_paths,
                                column_context=context,
                            ),
                        )
                    )
                    child_html_paths.append(article_html)
                if self._pdf:
                    article_pdf = content_directory / f"{name}.pdf"
                    pdf_context = replace(
                        context,
                        directory=RenderNavigationItem(
                            title=column.title,
                            markdown_href="",
                            html_href=_relative_href(f"../{column_filename}.pdf"),
                        ),
                        previous=_article_navigation(
                            archive.articles[index - 1],
                            article_names[index - 1],
                            markdown=False,
                            html=True,
                            html_extension="pdf",
                        )
                        if index > 0
                        else None,
                        next=_article_navigation(
                            archive.articles[index + 1],
                            article_names[index + 1],
                            markdown=False,
                            html=True,
                            html_extension="pdf",
                        )
                        if index + 1 < len(archive.articles)
                        else None,
                    )
                    pdf_documents.append(
                        PdfDocument(
                            article_pdf,
                            html_renderer.render(
                                article, media_paths=child_media_paths, column_context=pdf_context
                            ),
                        )
                    )
                    child_pdf_paths.append(article_pdf)

        if html_path is not None:
            documents.extend(
                (entry_directory / "assets" / filename, content)
                for filename, content in HtmlRenderer.assets().items()
            )
        for path, content in documents:
            _atomic_write_text(path, content)
        if pdf_path is not None:
            pdf_entries = {
                article.id: RenderNavigationItem(
                    title=article.title,
                    markdown_href="",
                    html_href=_relative_href(f"内容/{name}.pdf"),
                )
                for article, name in zip(archive.articles, article_names, strict=True)
            }
            pdf_documents.append(
                PdfDocument(
                    pdf_path,
                    html_renderer.render(archive, directory_entries=pdf_entries),
                )
            )
            self._pdf_exporter(pdf_documents, resource_root=entry_directory)
        # The catalog advertises only a batch whose document and style writes completed.
        for path, content in catalogs:
            _atomic_write_text(path, content)

        return ArchiveReceipt(
            entry_directory=entry_directory,
            markdown_path=markdown_path,
            html_path=html_path,
            child_markdown_paths=tuple(child_markdown_paths),
            child_html_paths=tuple(child_html_paths),
            media_downloads=assets.downloads,
            media_failures=assets.failures,
            pdf_path=pdf_path,
            child_pdf_paths=tuple(child_pdf_paths),
        )

    def _archive_media(
        self,
        target: ArchiveTarget,
        entry_directory: Path,
    ) -> AssetArchiveReceipt:
        if not self._media_download:
            return AssetArchiveReceipt(source_paths={}, downloads=())
        return archive_assets(
            target,
            entry_directory / "media",
            downloader=self._downloader,
        )

    def _write_html_assets(self, assets_directory: Path) -> None:
        assets_directory.mkdir(exist_ok=True)
        for filename, content in HtmlRenderer.assets().items():
            _atomic_write_text(assets_directory / filename, content)

    def _entry_directory(
        self,
        *,
        title: str,
        target_type: str,
        target_id: str,
        source_url: str,
    ) -> Path:
        base = self._root / safe_filename(title)
        if _directory_belongs_to(
            base,
            source_url,
            target_type=target_type,
        ):
            return base
        for directory in sorted(self._root.iterdir()):
            if directory.is_dir() and _directory_belongs_to(
                directory, source_url, target_type=target_type
            ):
                return directory
        occupied = {entry.name.casefold() for entry in self._root.iterdir()}
        if base.name.casefold() not in occupied:
            return base
        suffix = safe_filename(f"{title}--{target_type}-{target_id}")
        counter = 2
        while suffix.casefold() in occupied:
            suffix = safe_filename(f"{title}--{target_type}-{target_id}-{counter}")
            counter += 1
        return self._root / suffix


def _unique_article_names(articles: tuple[Article, ...], directory: Path) -> tuple[str, ...]:
    names = _DocumentNames(directory)
    return tuple(
        names.name_for(
            title=article.title,
            source_url=article.source_url,
            target_type="article",
            target_id=article.id,
        )
        for article in articles
    )


def _article_navigation(
    article: Article,
    filename: str,
    *,
    markdown: bool,
    html: bool,
    html_extension: str = "html",
) -> RenderNavigationItem:
    return RenderNavigationItem(
        title=article.title,
        markdown_href=_relative_href(f"{filename}.md") if markdown else "",
        html_href=_relative_href(f"{filename}.{html_extension}") if html else "",
    )


def _relative_href(value: str) -> str:
    """Encode URL-significant ASCII while keeping readable Unicode filenames."""

    return "".join(
        character if not character.isascii() else quote(character, safe="/._~-")
        for character in value
    )


def _target_type(target: ArchiveTarget) -> str:
    if isinstance(target, Article):
        return "article"
    if isinstance(target, Answer):
        return "answer"
    if isinstance(target, QuestionArchive):
        return "question"
    if isinstance(target, Video):
        return "video"
    if isinstance(target, ColumnArchive):
        return "column"
    raise TypeError(f"unsupported archive target: {type(target).__name__}")


def _directory_belongs_to(
    directory: Path,
    source_url: str,
    *,
    target_type: str,
) -> bool:
    identity = _source_identity(source_url, _source_label(target_type))
    return identity in _DocumentNames(directory).identities


class _DocumentNames:
    """Recover reusable names from visible source links, never from hidden state."""

    def __init__(self, directory: Path) -> None:
        documents = sorted(directory.iterdir()) if directory.is_dir() else []
        groups: dict[str, list[tuple[Path, tuple[str, str] | None]]] = {}
        self.identities: set[tuple[str, str]] = set()
        self._existing: dict[tuple[str, str], str] = {}
        for document in documents:
            if document.suffix.casefold() not in {".md", ".html", ".pdf"}:
                continue
            identity = _document_identity(document)
            groups.setdefault(document.stem.casefold(), []).append((document, identity))
            if identity is not None:
                self.identities.add(identity)
        self._used = set(groups)
        for group in groups.values():
            document, identity = group[0]
            # An unknown or differently owned sibling format must stay untouched.
            if identity is not None and all(owner == identity for _, owner in group):
                self._existing.setdefault(identity, document.stem)

    def name_for(self, *, title: str, source_url: str, target_type: str, target_id: str) -> str:
        identity = _source_identity(source_url, _source_label(target_type))
        if existing := self._existing.get(identity):
            return existing
        name = safe_filename(title)
        if name.casefold() in self._used:
            name = safe_filename(f"{title}--{target_type}-{target_id}")
        counter = 2
        while name.casefold() in self._used:
            name = safe_filename(f"{title}--{target_type}-{target_id}-{counter}")
            counter += 1
        self._used.add(name.casefold())
        self._existing[identity] = name
        return name


def _source_label(target_type: str) -> str:
    return {
        "question": "知乎原问题",
        "column": "知乎专栏",
    }.get(target_type, "知乎原文")


def _source_identity(source_url: str, label: str) -> tuple[str, str]:
    try:
        target = route_zhihu_url(source_url)
    except UnsupportedZhihuUrlError:
        return label, source_url
    return target.kind.value, target.content_id


def _document_identity(document: Path) -> tuple[str, str] | None:
    if document.suffix.casefold() == ".pdf":
        source_url = pdf_source_url(document)
        return _source_identity(source_url, "知乎原文") if source_url is not None else None
    try:
        with document.open(encoding="utf-8") as source:
            prefix = source.read(16_384)
    except (OSError, UnicodeError):
        return None
    if document.suffix.casefold() == ".md":
        match = _MARKDOWN_SOURCE.search(prefix)
        if match is not None:
            label, source_url = match.groups()
            return _source_identity(source_url, label)
    else:
        match = _HTML_SOURCE.search(prefix)
        if match is not None:
            source_url, label = match.groups()
            return _source_identity(unescape(source_url), label)
    return None


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        finally:
            raise
