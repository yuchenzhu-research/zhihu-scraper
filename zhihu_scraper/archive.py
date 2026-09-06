"""Filesystem archive sink for every normalized Zhihu target."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, replace
from functools import partial
from html import escape, unescape
from pathlib import Path
from urllib.parse import quote, unquote

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
from .platform import RuntimePlatform
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
    progress_path: Path | None = None


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
        self._platform = RuntimePlatform.detect()
        self._name_budget = self._platform.archive_name_budget(
            self._root, media_download=media_download
        )
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

    def begin_batch(self, target: ColumnArchive | QuestionArchive) -> LocalArchiveBatch:
        """Start a readable checkpoint session before enumerating collection items."""

        return LocalArchiveBatch(self, target)

    def _archive_standalone(
        self,
        target: ArchiveTarget,
        *,
        assets: AssetArchiveReceipt | None = None,
    ) -> ArchiveReceipt:
        title = target.title
        entry_directory = self._entry_directory(
            title=title,
            target_type=_target_type(target),
            target_id=target.id,
            source_url=target.source_url,
        )
        filename = self._document_names(entry_directory).name_for(
            title=title,
            source_url=target.source_url,
            target_type=_target_type(target),
            target_id=target.id,
        )
        entry_directory.mkdir(parents=True, exist_ok=True)

        if assets is None:
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
        *,
        assets: AssetArchiveReceipt | None = None,
    ) -> ArchiveReceipt:
        column = archive.column
        entry_directory = self._entry_directory(
            title=column.title,
            target_type="column",
            target_id=column.token,
            source_url=column.source_url,
        )
        column_filename = self._document_names(entry_directory).name_for(
            title=column.title,
            source_url=column.source_url,
            target_type="column",
            target_id=column.token,
        )
        article_names = _unique_article_names(
            archive.articles,
            entry_directory / "内容",
            max_utf16=self._name_budget,
            runtime=self._platform,
        )
        entry_directory.mkdir(parents=True, exist_ok=True)
        if assets is None:
            assets = self._archive_media(archive, entry_directory)
        render_paths = assets.source_paths

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
        base = self._root / safe_filename(title, max_utf16=self._name_budget)
        if _directory_belongs_to(
            base,
            source_url,
            target_type=target_type,
        ):
            return self._validate_entry_directory(base)
        for directory in sorted(self._root.iterdir()):
            if directory.is_dir() and _directory_belongs_to(
                directory, source_url, target_type=target_type
            ):
                return self._validate_entry_directory(directory)
        occupied = {entry.name.casefold() for entry in self._root.iterdir()}
        if base.name.casefold() not in occupied:
            return self._validate_entry_directory(base)
        suffix = safe_filename(f"{title}--{target_type}-{target_id}", max_utf16=self._name_budget)
        counter = 2
        while suffix.casefold() in occupied:
            suffix = safe_filename(
                f"{title}--{target_type}-{target_id}-{counter}", max_utf16=self._name_budget
            )
            counter += 1
        return self._validate_entry_directory(self._root / suffix)

    def _validate_entry_directory(self, directory: Path) -> Path:
        self._platform.validate_archive_path(directory)
        if self._media_download:
            self._platform.validate_archive_path(directory / "media" / ("x" * 64), extra_units=16)
        return directory

    def _document_names(self, directory: Path) -> _DocumentNames:
        return _DocumentNames(directory, max_utf16=self._name_budget, runtime=self._platform)


class LocalArchiveBatch:
    """Save each collection item once, then publish its complete catalog once."""

    def __init__(self, archive: LocalArchive, target: ColumnArchive | QuestionArchive) -> None:
        self._archive = archive
        self._target = target
        archive._root.mkdir(parents=True, exist_ok=True)
        self._directory = archive._entry_directory(
            title=target.title,
            target_type=_target_type(target),
            target_id=target.id,
            source_url=target.source_url,
        )
        self._directory.mkdir(parents=True, exist_ok=True)
        self.progress_path = _batch_progress_path(
            self._directory, target, max_utf16=archive._name_budget
        )
        archive._platform.validate_archive_path(self.progress_path, extra_units=5)
        self._rows = _read_progress_rows(self.progress_path, self._directory)
        self._items: dict[str, Article | Answer] = {}
        self._receipts: dict[str, ArchiveReceipt] = {}
        self._temporary_paths: list[Path] = []
        self._closed = False
        if isinstance(target, QuestionArchive):
            self._item_directory = self._directory / "回答片段"
            self._temporary_fragments = True
        elif archive._markdown or archive._html:
            self._item_directory = self._directory / "内容"
            self._temporary_fragments = False
        else:
            self._item_directory = self._directory / "归档片段"
            self._temporary_fragments = True
        self._names = archive._document_names(self._item_directory)
        self._source_paths: dict[str, str] = {}
        self._downloads: list[MediaDownloadReceipt] = []
        self._failures: list[MediaArchiveFailure] = []
        self._write_progress(complete=False, active=True)
        self._remember_assets(archive._archive_media(target, self._directory))

    def write_item(self, item: Article | Answer) -> ArchiveReceipt:
        if self._closed:
            raise RuntimeError("batch archive is closed")
        if isinstance(self._target, ColumnArchive) != isinstance(item, Article):
            raise TypeError("collection item type does not match its archive")
        if item.id in self._receipts:
            return self._receipts[item.id]
        title = item.title if isinstance(item, Article) else f"{item.author.name}--回答-{item.id}"
        name = self._names.name_for(
            title=title,
            source_url=item.source_url,
            target_type=_target_type(item),
            target_id=item.id,
        )
        assets = self._archive._archive_media(item, self._directory)
        paths = {source: f"../{path}" for source, path in assets.source_paths.items()}
        context = None
        if isinstance(self._target, ColumnArchive):
            column = self._target.column
            progress_href = _relative_href(f"../{self.progress_path.name}")
            context = ColumnRenderContext(
                column=ColumnRef(column.token, column.title, column.source_url),
                directory=RenderNavigationItem(column.title, progress_href, progress_href),
                item_count=column.item_count,
            )
        markdown_path = None
        html_path = None
        if self._archive._markdown or self._temporary_fragments:
            markdown_path = self._item_directory / f"{name}.md"
            _atomic_write_text(
                markdown_path,
                MarkdownRenderer().render(item, media_paths=paths, column_context=context),
            )
        if self._archive._html and not self._temporary_fragments:
            html_path = self._item_directory / f"{name}.html"
            _atomic_write_text(
                html_path, HtmlRenderer().render(item, media_paths=paths, column_context=context)
            )
            self._archive._write_html_assets(self._directory / "assets")
        saved_path = markdown_path or html_path
        if saved_path is None:
            raise AssertionError("a checkpoint must produce a readable document")
        receipt = ArchiveReceipt(
            self._directory,
            markdown_path,
            html_path,
            media_downloads=assets.downloads,
            media_failures=assets.failures,
            progress_path=self.progress_path,
        )
        row = _progress_row(item, saved_path.relative_to(self._directory))
        if self._rows.get(item.source_url) != row:
            with self.progress_path.open("a", encoding="utf-8", newline="\n") as output:
                output.write(f"{row}\n")
                output.flush()
                os.fsync(output.fileno())
        self._rows[item.source_url] = row
        self._items[item.id] = item
        self._receipts[item.id] = receipt
        if self._temporary_fragments:
            self._temporary_paths.append(saved_path)
        self._remember_assets(assets)
        return receipt

    def finish(self, target: ColumnArchive | QuestionArchive) -> ArchiveReceipt:
        if self._closed:
            raise RuntimeError("batch archive is closed")
        if (type(target), target.id) != (type(self._target), self._target.id):
            raise ValueError("the final collection does not match its checkpoint session")
        assets = AssetArchiveReceipt(
            self._source_paths, tuple(self._downloads), tuple(self._failures)
        )
        if isinstance(target, ColumnArchive):
            receipt = self._archive._archive_column(target, assets=assets)
            final_paths = (
                receipt.child_markdown_paths or receipt.child_html_paths or receipt.child_pdf_paths
            )
            for item, path in zip(target.articles, final_paths, strict=True):
                self._rows[item.source_url] = _progress_row(item, path.relative_to(self._directory))
        else:
            receipt = self._archive._archive_standalone(target, assets=assets)
            final_path = receipt.markdown_path or receipt.html_path or receipt.pdf_path
            if final_path is None:
                raise AssertionError("a complete question archive must have an output document")
            # The complete question document replaces its earlier answer set, so old
            # answer links no longer describe saved content in that document.
            self._rows.clear()
            for answer in target.answers:
                self._rows[answer.source_url] = _progress_row(
                    answer, final_path.relative_to(self._directory)
                )
        self._write_progress(complete=True)
        self._closed = True
        for path in self._temporary_paths:
            path.unlink(missing_ok=True)
        if self._temporary_fragments and self._item_directory.is_dir():
            if not any(self._item_directory.iterdir()):
                self._item_directory.rmdir()
        return replace(receipt, progress_path=self.progress_path)

    def interrupt(self) -> ArchiveReceipt:
        self._write_progress(complete=False)
        self._closed = True
        return ArchiveReceipt(
            self._directory,
            None,
            None,
            child_markdown_paths=tuple(
                receipt.markdown_path
                for receipt in self._receipts.values()
                if receipt.markdown_path
            ),
            child_html_paths=tuple(
                receipt.html_path for receipt in self._receipts.values() if receipt.html_path
            ),
            media_downloads=tuple(self._downloads),
            media_failures=tuple(self._failures),
            progress_path=self.progress_path,
        )

    def _remember_assets(self, assets: AssetArchiveReceipt) -> None:
        self._source_paths.update(assets.source_paths)
        self._downloads.extend(assets.downloads)
        self._failures.extend(assets.failures)

    def _write_progress(self, *, complete: bool, active: bool = False) -> None:
        status = "已完成" if complete else "未完成（进行中）" if active else "未完成"
        source = self._target.source_url
        label = _source_label(_target_type(self._target))
        content = "\n".join(
            (
                "# 归档进度",
                "",
                f"> {label}：[{source}]({source})",
                f"> 状态：{status}",
                "> 保存进度：每个新增链接均已写入文件。"
                if active
                else f"> 本轮已保存：{len(self._items)} 项",
                "",
                "重新运行相同网址会重新读取列表、复用已有文件；旧的完整目录在本轮全部成功前保持不变。",
                "下列链接仅包含已经保存的内容，也保留此前运行留下的可读文件。",
                "",
                "## 已保存内容",
                "",
                *self._rows.values(),
                "",
            )
        )
        _atomic_write_text(self.progress_path, content)


def _batch_progress_path(
    directory: Path, target: ColumnArchive | QuestionArchive, *, max_utf16: int | None = None
) -> Path:
    identity = _source_identity(target.source_url, _source_label(_target_type(target)))
    for path in sorted(directory.glob("*.md")):
        if _is_progress_document(path) and _document_identity(path) == identity:
            return path
    candidate = directory / "归档进度.md"
    counter = 1
    while candidate.exists():
        suffix = f"归档进度--{_target_type(target)}-{target.id}"
        if counter > 1:
            suffix += f"-{counter}"
        candidate = directory / f"{safe_filename(suffix, max_utf16=max_utf16)}.md"
        counter += 1
    return candidate


def _is_progress_document(path: Path) -> bool:
    if path.suffix.casefold() != ".md":
        return False
    try:
        with path.open(encoding="utf-8") as source:
            return source.readline().rstrip("\r\n") == "# 归档进度"
    except (OSError, UnicodeError):
        return False


def _read_progress_rows(path: Path, directory: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"- \[[^\n]*\]\(([^)]*)\) · \[知乎原文\]\(([^)]*)\)", line)
        if match is None:
            continue
        relative_path, source_url = match.groups()
        saved = (directory / unquote(relative_path)).resolve()
        if saved.is_relative_to(directory.resolve()) and saved.is_file():
            rows[source_url] = line
    return rows


def _progress_row(item: Article | Answer, path: Path) -> str:
    title = item.title if isinstance(item, Article) else f"{item.author.name}的回答"
    title = (
        escape(" ".join(title.split()), quote=False)
        .replace("\\", "\\\\")
        .replace("[", "\\[")
        .replace("]", "\\]")
    )
    source_url = quote(item.source_url, safe="/:?=&%#@+~")
    return f"- [{title}]({_relative_href(path.as_posix())}) · [知乎原文]({source_url})"


def _unique_article_names(
    articles: tuple[Article, ...],
    directory: Path,
    *,
    max_utf16: int | None = None,
    runtime: RuntimePlatform | None = None,
) -> tuple[str, ...]:
    names = _DocumentNames(directory, max_utf16=max_utf16, runtime=runtime)
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

    def __init__(
        self,
        directory: Path,
        *,
        max_utf16: int | None = None,
        runtime: RuntimePlatform | None = None,
    ) -> None:
        self._directory = directory
        self._max_utf16 = max_utf16
        self._runtime = runtime
        documents = sorted(directory.iterdir()) if directory.is_dir() else []
        groups: dict[str, list[tuple[Path, tuple[str, str] | None]]] = {}
        self.identities: set[tuple[str, str]] = set()
        self._existing: dict[tuple[str, str], str] = {}
        progress_names: set[str] = set()
        for document in documents:
            if document.suffix.casefold() not in {".md", ".html", ".pdf"}:
                continue
            identity = _document_identity(document)
            groups.setdefault(document.stem.casefold(), []).append((document, identity))
            if identity is not None:
                self.identities.add(identity)
            if _is_progress_document(document):
                progress_names.add(document.stem.casefold())
        self._used = set(groups)
        for group in groups.values():
            document, identity = group[0]
            # An unknown or differently owned sibling format must stay untouched.
            if (
                identity is not None
                and document.stem.casefold() not in progress_names
                and all(owner == identity for _, owner in group)
            ):
                self._existing.setdefault(identity, document.stem)

    def name_for(self, *, title: str, source_url: str, target_type: str, target_id: str) -> str:
        identity = _source_identity(source_url, _source_label(target_type))
        if existing := self._existing.get(identity):
            self._validate(existing)
            return existing
        name = safe_filename(title, max_utf16=self._max_utf16)
        if name.casefold() in self._used:
            name = safe_filename(f"{title}--{target_type}-{target_id}", max_utf16=self._max_utf16)
        counter = 2
        while name.casefold() in self._used:
            name = safe_filename(
                f"{title}--{target_type}-{target_id}-{counter}", max_utf16=self._max_utf16
            )
            counter += 1
        self._validate(name)
        self._used.add(name.casefold())
        self._existing[identity] = name
        return name

    def _validate(self, name: str) -> None:
        if self._runtime is not None:
            self._runtime.validate_archive_path(self._directory / f"{name}.html", extra_units=5)


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
    RuntimePlatform.detect().validate_archive_path(path, extra_units=5)
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
