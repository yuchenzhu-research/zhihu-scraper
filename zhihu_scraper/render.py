"""Render normalized archive targets to Markdown and dependency-free HTML."""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from urllib.parse import urlsplit

from latex2mathml import converter as latex2mathml_converter

from .domain import (
    Answer,
    ArchiveTarget,
    Article,
    Block,
    CodeBlock,
    CodeSpan,
    ColumnArchive,
    ColumnRef,
    Comment,
    CommentThread,
    Divider,
    EmbeddedVideo,
    FormulaBlock,
    Heading,
    Inline,
    InlineFormula,
    LineBreak,
    Link,
    ListBlock,
    MediaAsset,
    MediaBlock,
    MediaKind,
    Paragraph,
    QuestionArchive,
    Quote,
    TableBlock,
    Text,
    Video,
)

_MATHML_NAMESPACE = "http://www.w3.org/1998/Math/MathML"
ET.register_namespace("", _MATHML_NAMESPACE)

ARCHIVE_CSS = """\
:root {
  color-scheme: light dark;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.75;
}
body {
  margin: 0 auto;
  max-width: 860px;
  padding: 2rem 1.25rem 5rem;
}
a {
  overflow-wrap: anywhere;
}
article img,
article video {
  height: auto;
  max-width: 100%;
}
video {
  background: #111;
  width: 100%;
}
pre {
  overflow-x: auto;
  padding: 1rem;
}
.metadata,
.archive-context,
.answer-metadata,
.comment-metadata {
  opacity: 0.78;
}
.archive-context,
.article-navigation {
  border-inline-start: 3px solid currentColor;
  margin: 1rem 0;
  padding: 0.35rem 0.8rem;
}
.article-navigation {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 1rem;
  justify-content: space-between;
}
.answer {
  border-block-start: 1px solid color-mix(in srgb, currentColor 25%, transparent);
  margin-block-start: 2rem;
  padding-block-start: 1rem;
}
.comments {
  border-block-start: 1px solid color-mix(in srgb, currentColor 25%, transparent);
  margin-block-start: 2rem;
}
.comment,
.reply {
  border-inline-start: 2px solid color-mix(in srgb, currentColor 25%, transparent);
  margin: 1rem 0;
  padding-inline-start: 1rem;
}
.reply {
  margin-inline-start: 1rem;
}
.math-inline,
.math-display {
  font-family: "STIX Two Math", "Cambria Math", serif;
}
.math-display {
  margin: 1rem 0;
  overflow-x: auto;
  padding: 0.75rem;
  text-align: center;
}
table {
  border-collapse: collapse;
  display: block;
  overflow-x: auto;
}
th,
td {
  border: 1px solid currentColor;
  padding: 0.35rem 0.65rem;
}
"""


@dataclass(frozen=True, slots=True)
class RenderNavigationItem:
    """A renderer-ready link whose filesystem naming was decided elsewhere."""

    title: str
    markdown_href: str
    html_href: str


@dataclass(frozen=True, slots=True)
class ColumnRenderContext:
    """Navigation shown when an article is rendered inside a column archive."""

    column: ColumnRef
    directory: RenderNavigationItem
    item_count: int = 0
    previous: RenderNavigationItem | None = None
    next: RenderNavigationItem | None = None


class MarkdownRenderer:
    def render(
        self,
        target: ArchiveTarget,
        *,
        image_paths: Mapping[str, str] | None = None,
        media_paths: Mapping[str, str] | None = None,
        column_context: ColumnRenderContext | None = None,
        directory_entries: Mapping[str, RenderNavigationItem] | None = None,
    ) -> str:
        paths = _combined_paths(image_paths, media_paths)
        if isinstance(target, Article):
            return _article_to_markdown(target, paths=paths, context=column_context)
        if isinstance(target, Answer):
            return _answer_to_markdown(target, paths=paths)
        if isinstance(target, QuestionArchive):
            return _question_to_markdown(target, paths=paths)
        if isinstance(target, ColumnArchive):
            return _column_to_markdown(target, entries=directory_entries or {})
        if isinstance(target, Video):
            return _video_to_markdown(target, paths=paths)
        raise TypeError(f"Unsupported archive target: {type(target).__name__}")


class HtmlRenderer:
    def render(
        self,
        target: ArchiveTarget,
        *,
        image_paths: Mapping[str, str] | None = None,
        media_paths: Mapping[str, str] | None = None,
        column_context: ColumnRenderContext | None = None,
        directory_entries: Mapping[str, RenderNavigationItem] | None = None,
    ) -> str:
        paths = _combined_paths(image_paths, media_paths)
        if isinstance(target, Article):
            body = _article_to_html(target, paths=paths, context=column_context)
        elif isinstance(target, Answer):
            body = _answer_to_html(target, paths=paths)
        elif isinstance(target, QuestionArchive):
            body = _question_to_html(target, paths=paths)
        elif isinstance(target, ColumnArchive):
            body = _column_to_html(target, entries=directory_entries or {})
        elif isinstance(target, Video):
            body = _video_to_html(target, paths=paths)
        else:
            raise TypeError(f"Unsupported archive target: {type(target).__name__}")
        stylesheet_href = (
            "../assets/archive.css"
            if isinstance(target, Article) and column_context is not None
            else "assets/archive.css"
        )
        return _html_document(target.title, body, stylesheet_href=stylesheet_href)

    @staticmethod
    def assets() -> Mapping[str, str]:
        return {"archive.css": ARCHIVE_CSS}


def content_plain_text(blocks: Sequence[Block]) -> str:
    """Return searchable text without reparsing output formats."""

    parts: list[str] = []
    for block in blocks:
        if isinstance(block, (Paragraph, Heading)):
            parts.append(_inlines_plain_text(block.inlines))
        elif isinstance(block, Quote):
            parts.append(content_plain_text(block.blocks))
        elif isinstance(block, ListBlock):
            parts.extend(content_plain_text(item) for item in block.items)
        elif isinstance(block, CodeBlock):
            parts.append(block.code)
        elif isinstance(block, FormulaBlock):
            parts.append(block.tex)
        elif isinstance(block, MediaBlock):
            parts.extend(part for part in (block.asset.alt_text, block.caption) if part)
        elif isinstance(block, EmbeddedVideo):
            parts.append(block.title or "内嵌视频")
        elif isinstance(block, TableBlock):
            parts.extend(_inlines_plain_text(cell) for cell in block.headers)
            parts.extend(_inlines_plain_text(cell) for row in block.rows for cell in row)
    return "\n\n".join(part for part in parts if part)


def _article_to_markdown(
    article: Article,
    *,
    paths: Mapping[str, str],
    context: ColumnRenderContext | None,
) -> str:
    parts = [
        f"# {_markdown_single_line(article.title)}",
        "",
        *_markdown_metadata(
            author=article.author.name,
            source_url=article.source_url,
            published_at=article.published_at,
            voteup_count=article.voteup_count,
        ),
    ]
    context_lines = _article_context_markdown(article, context)
    if context_lines:
        parts.extend(["", *context_lines])
    cover = _cover_to_markdown(article.cover_url, article.title, paths=paths)
    if cover:
        parts.extend(["", cover])
    body = _blocks_to_markdown(article.blocks, paths=paths).strip()
    if body:
        parts.extend(["", body])
    if article.comments is not None:
        parts.extend(
            [
                "",
                _comments_to_markdown(
                    article.comments,
                    heading_level=2,
                    paths=paths,
                ),
            ]
        )
    return "\n".join([*parts, ""])


def _answer_to_markdown(answer: Answer, *, paths: Mapping[str, str]) -> str:
    parts = [
        f"# {_markdown_single_line(answer.title)}",
        "",
        "> 内容类型：回答",
        f"> 问题：{_markdown_link(answer.question.title, answer.question.url)}",
        *_markdown_metadata(
            author=answer.author.name,
            source_url=answer.source_url,
            published_at=answer.published_at,
            voteup_count=answer.voteup_count,
        ),
    ]
    body = _blocks_to_markdown(answer.blocks, paths=paths).strip()
    if body:
        parts.extend(["", body])
    if answer.comments is not None:
        parts.extend(
            [
                "",
                _comments_to_markdown(
                    answer.comments,
                    heading_level=2,
                    paths=paths,
                ),
            ]
        )
    return "\n".join([*parts, ""])


def _question_to_markdown(
    archive: QuestionArchive,
    *,
    paths: Mapping[str, str],
) -> str:
    question = archive.question
    parts = [
        f"# {_markdown_single_line(question.title)}",
        "",
        f"> 知乎原问题：{_markdown_link(question.source_url, question.source_url)}",
        f"> 共归档 {len(archive.answers)} 个回答",
        f"> 知乎显示回答数：{question.answer_count}",
        f"> 归档时间：{archive.archived_at.date().isoformat()}",
    ]
    detail = _blocks_to_markdown(question.detail, paths=paths).strip()
    if detail:
        parts.extend(["", "## 问题详情", "", detail])
    for index, answer in enumerate(archive.answers, start=1):
        parts.extend(
            [
                "",
                "---",
                "",
                f"## 回答 {index} · {_markdown_single_line(answer.author.name)}",
                "",
                *_markdown_metadata(
                    author=None,
                    source_url=answer.source_url,
                    published_at=answer.published_at,
                    voteup_count=answer.voteup_count,
                    source_label="查看这个回答",
                ),
            ]
        )
        answer_body = _blocks_to_markdown(answer.blocks, paths=paths).strip()
        if answer_body:
            parts.extend(["", answer_body])
        if answer.comments is not None:
            parts.extend(
                [
                    "",
                    _comments_to_markdown(
                        answer.comments,
                        heading_level=3,
                        paths=paths,
                    ),
                ]
            )
    return "\n".join([*parts, ""])


def _column_to_markdown(
    archive: ColumnArchive,
    *,
    entries: Mapping[str, RenderNavigationItem],
) -> str:
    column = archive.column
    parts = [
        f"# {_markdown_single_line(column.title)}",
        "",
        (
            f"> 专栏作者："
            f"{_markdown_single_line(column.author.name) if column.author else '未知作者'}"
        ),
        f"> 知乎专栏：{_markdown_link(column.source_url, column.source_url)}",
        f"> 本栏目共 {column.item_count} 篇",
        f"> 本次归档 {len(archive.articles)} 篇",
        f"> 归档时间：{archive.archived_at.date().isoformat()}",
    ]
    if column.description:
        parts.extend(["", _escape_markdown_text(column.description)])
    groups = _articles_by_year(archive.articles)
    for year, articles in groups:
        parts.extend(["", f"## {year}", ""])
        for article in articles:
            entry = entries.get(article.id)
            md_path = entry.markdown_href if entry is not None else f"内容/{article.title}.md"
            html_path = entry.html_href if entry is not None else f"内容/{article.title}.html"
            date = article.published_at.date().isoformat() if article.published_at else "日期未知"
            output_links = []
            if md_path:
                output_links.append(_markdown_link("Markdown", md_path))
            if html_path:
                output_links.append(_markdown_link("HTML", html_path))
            suffix = f"（{' · '.join(output_links)}）" if output_links else ""
            parts.append(f"- {date} · {_markdown_single_line(article.title)}{suffix}")
    return "\n".join([*parts, ""])


def _video_to_markdown(video: Video, *, paths: Mapping[str, str]) -> str:
    parts = [
        f"# {_markdown_single_line(video.title)}",
        "",
        "> 内容类型：知乎视频",
        *_markdown_metadata(
            author=video.author.name,
            source_url=video.source_url,
            published_at=video.published_at,
            voteup_count=video.voteup_count,
        ),
    ]
    cover = _cover_to_markdown(video.cover_url, video.title, paths=paths)
    if cover:
        parts.extend(["", cover])
    description = _blocks_to_markdown(video.description, paths=paths).strip()
    if description:
        parts.extend(["", description])
    local_or_remote = _media_source(video.asset, paths=paths)
    original = _media_original_source(video.asset)
    parts.extend(["", "## 视频", ""])
    if local_or_remote:
        parts.append(_markdown_link("播放或下载视频", local_or_remote))
    if original:
        parts.append(f"\n{_markdown_link('原始视频链接', original)}")
    if video.comments is not None:
        parts.extend(
            [
                "",
                _comments_to_markdown(
                    video.comments,
                    heading_level=2,
                    paths=paths,
                ),
            ]
        )
    return "\n".join([*parts, ""])


def _article_to_html(
    article: Article,
    *,
    paths: Mapping[str, str],
    context: ColumnRenderContext | None,
) -> str:
    metadata = _html_metadata(
        author=article.author.name,
        source_url=article.source_url,
        published_at=article.published_at,
        voteup_count=article.voteup_count,
    )
    archive_context = _article_context_html(article, context)
    cover = _cover_to_html(article.cover_url, article.title, paths=paths)
    comments = (
        _comments_to_html(article.comments, heading_level=2, paths=paths)
        if article.comments
        else ""
    )
    return (
        "    <article>\n"
        f"      <h1>{html.escape(article.title)}</h1>\n"
        f"{metadata}"
        f"{archive_context}"
        f"{cover}"
        f"{_blocks_to_html(article.blocks, paths=paths)}\n"
        f"{comments}"
        "    </article>\n"
    )


def _answer_to_html(answer: Answer, *, paths: Mapping[str, str]) -> str:
    question_link = _html_link(answer.question.title, answer.question.url)
    metadata = _html_metadata(
        author=answer.author.name,
        source_url=answer.source_url,
        published_at=answer.published_at,
        voteup_count=answer.voteup_count,
    )
    comments = (
        _comments_to_html(answer.comments, heading_level=2, paths=paths) if answer.comments else ""
    )
    return (
        '    <article class="standalone-answer">\n'
        f"      <h1>{html.escape(answer.title)}</h1>\n"
        '      <p class="content-kind">内容类型：回答</p>\n'
        f"      <p>问题：{question_link}</p>\n"
        f"{metadata}"
        f"{_blocks_to_html(answer.blocks, paths=paths)}\n"
        f"{comments}"
        "    </article>\n"
    )


def _question_to_html(
    archive: QuestionArchive,
    *,
    paths: Mapping[str, str],
) -> str:
    question = archive.question
    question_source = _html_link("知乎原问题", question.source_url)
    detail = _blocks_to_html(question.detail, paths=paths) if question.detail else ""
    sections: list[str] = []
    for index, answer in enumerate(archive.answers, start=1):
        source = _html_link("查看这个回答", answer.source_url)
        date = (
            f"<span>发布于 {html.escape(answer.published_at.date().isoformat())}</span>"
            if answer.published_at
            else ""
        )
        comments = (
            _comments_to_html(
                answer.comments,
                heading_level=3,
                paths=paths,
            )
            if answer.comments
            else ""
        )
        sections.append(
            '      <section class="answer">\n'
            f"        <h2>回答 {index} · {html.escape(answer.author.name)}</h2>\n"
            '        <p class="answer-metadata">'
            f"{source} · {answer.voteup_count} 赞同"
            f"{' · ' + date if date else ''}</p>\n"
            f"{_blocks_to_html(answer.blocks, paths=paths, indent='        ')}\n"
            f"{comments}"
            "      </section>\n"
        )
    return (
        '    <article class="question-archive">\n'
        f"      <h1>{html.escape(question.title)}</h1>\n"
        '      <section class="metadata">\n'
        f"        <p>{question_source}</p>\n"
        f"        <p>共归档 {len(archive.answers)} 个回答</p>\n"
        f"        <p>知乎显示回答数：{question.answer_count}</p>\n"
        f"        <p>归档时间：{archive.archived_at.date().isoformat()}</p>\n"
        "      </section>\n"
        f"{'      <h2>问题详情</h2>\\n' + detail + chr(10) if detail else ''}"
        f"{''.join(sections)}"
        "    </article>\n"
    )


def _column_to_html(
    archive: ColumnArchive,
    *,
    entries: Mapping[str, RenderNavigationItem],
) -> str:
    column = archive.column
    source = _html_link("知乎专栏", column.source_url)
    groups: list[str] = []
    for year, articles in _articles_by_year(archive.articles):
        entry_lines: list[str] = []
        for article in articles:
            date = article.published_at.date().isoformat() if article.published_at else "日期未知"
            entry = entries.get(article.id)
            html_path = entry.html_href if entry is not None else f"内容/{article.title}.html"
            markdown_path = entry.markdown_href if entry is not None else f"内容/{article.title}.md"
            markdown_link = f"（{_html_link('Markdown', markdown_path)}）" if markdown_path else ""
            entry_lines.append(
                "          <li>"
                f"<time>{html.escape(date)}</time> · "
                f"{_html_link(article.title, html_path)} "
                f"{markdown_link}"
                "</li>\n"
            )
        groups.append(
            '      <section class="year-group">\n'
            f"        <h2>{html.escape(year)}</h2>\n"
            "        <ul>\n"
            f"{''.join(entry_lines)}"
            "        </ul>\n"
            "      </section>\n"
        )
    description = f"      <p>{html.escape(column.description)}</p>\n" if column.description else ""
    author = html.escape(column.author.name if column.author else "未知作者")
    return (
        '    <article class="column-directory">\n'
        f"      <h1>{html.escape(column.title)}</h1>\n"
        '      <section class="metadata">\n'
        f"        <p>专栏作者：{author}</p>\n"
        f"        <p>{source}</p>\n"
        f"        <p>本栏目共 {column.item_count} 篇</p>\n"
        f"        <p>本次归档 {len(archive.articles)} 篇</p>\n"
        f"        <p>归档时间：{archive.archived_at.date().isoformat()}</p>\n"
        "      </section>\n"
        f"{description}"
        f"{''.join(groups)}"
        "    </article>\n"
    )


def _video_to_html(video: Video, *, paths: Mapping[str, str]) -> str:
    metadata = _html_metadata(
        author=video.author.name,
        source_url=video.source_url,
        published_at=video.published_at,
        voteup_count=video.voteup_count,
    )
    source = _media_source(video.asset, paths=paths)
    original = _media_original_source(video.asset)
    safe_source = _safe_url(source)
    safe_cover = paths.get(video.cover_url) if video.cover_url else None
    if safe_cover is not None and not _is_local_media_reference(safe_cover):
        safe_cover = None
    poster = f' poster="{html.escape(safe_cover, quote=True)}"' if safe_cover else ""
    video_element = (
        f'      <video controls preload="metadata"{poster} '
        f'src="{html.escape(safe_source, quote=True)}">'
        "你的浏览器不支持 HTML5 视频。</video>\n"
        if safe_source and _is_local_media_reference(safe_source)
        else f"      <p>{_html_link('远程视频未下载', safe_source or original)}</p>\n"
    )
    original_link = f"      <p>{_html_link('原始视频链接', original)}</p>\n" if original else ""
    comments = (
        _comments_to_html(video.comments, heading_level=2, paths=paths) if video.comments else ""
    )
    return (
        '    <article class="video-archive">\n'
        f"      <h1>{html.escape(video.title)}</h1>\n"
        '      <p class="content-kind">内容类型：知乎视频</p>\n'
        f"{metadata}"
        f"{_blocks_to_html(video.description, paths=paths)}\n"
        "      <h2>视频</h2>\n"
        f"{video_element}"
        f"{original_link}"
        f"{comments}"
        "    </article>\n"
    )


def _markdown_metadata(
    *,
    author: str | None,
    source_url: str,
    published_at,
    voteup_count: int,
    source_label: str = "知乎原文",
) -> list[str]:
    lines: list[str] = []
    if author is not None:
        lines.append(f"> 作者：{_markdown_single_line(author)}")
    lines.append(f"> {source_label}：{_markdown_link(source_url, source_url)}")
    if published_at is not None:
        lines.append(f"> 发布时间：{published_at.date().isoformat()}")
    if voteup_count:
        lines.append(f"> {voteup_count} 赞同")
    return lines


def _html_metadata(
    *,
    author: str | None,
    source_url: str,
    published_at,
    voteup_count: int,
) -> str:
    lines: list[str] = ['      <section class="metadata">\n']
    if author is not None:
        lines.append(f"        <p>作者：{html.escape(author)}</p>\n")
    lines.append(f"        <p>{_html_link('知乎原文', source_url)}</p>\n")
    if published_at is not None:
        lines.append(f"        <p>发布时间：{html.escape(published_at.date().isoformat())}</p>\n")
    if voteup_count:
        lines.append(f"        <p>{voteup_count} 赞同</p>\n")
    lines.append("      </section>\n")
    return "".join(lines)


def _article_context_markdown(
    article: Article,
    context: ColumnRenderContext | None,
) -> list[str]:
    lines: list[str] = []
    if article.columns:
        memberships = " · ".join(
            _markdown_link(column.title, column.url) for column in article.columns
        )
        lines.append(f"> 收录专栏：{memberships}")
    if context is not None:
        origin = _markdown_link(context.column.title, context.column.url)
        directory = _markdown_link(
            "查看完整目录",
            context.directory.markdown_href,
        )
        count = f" · 本栏目共 {context.item_count} 篇" if context.item_count else ""
        lines.append(f"> 本次归档自：{origin}{count} · {directory}")
        lines.append(f"> 专栏导航：{_article_navigation_markdown(context)}")
    return lines


def _article_context_html(
    article: Article,
    context: ColumnRenderContext | None,
) -> str:
    lines: list[str] = []
    if article.columns:
        memberships = " · ".join(_html_link(column.title, column.url) for column in article.columns)
        lines.append(f"        <p>收录专栏：{memberships}</p>\n")
    if context is not None:
        origin = _html_link(context.column.title, context.column.url)
        directory = _html_link("查看完整目录", context.directory.html_href)
        count = f" · 本栏目共 {context.item_count} 篇" if context.item_count else ""
        lines.append(f"        <p>本次归档自：{origin}{count} · {directory}</p>\n")
        lines.append(f"        <p>专栏导航：{_article_navigation_links_html(context)}</p>\n")
    if not lines:
        return ""
    return '      <aside class="archive-context">\n' + "".join(lines) + "      </aside>\n"


def _article_navigation_markdown(context: ColumnRenderContext | None) -> str:
    if context is None:
        return ""
    links: list[str] = []
    if context.previous is not None:
        links.append(
            _markdown_link(
                f"上一篇：{context.previous.title}",
                context.previous.markdown_href,
            )
        )
    links.append(_markdown_link("返回目录", context.directory.markdown_href))
    if context.next is not None:
        links.append(
            _markdown_link(
                f"下一篇：{context.next.title}",
                context.next.markdown_href,
            )
        )
    return " · ".join(links)


def _article_navigation_links_html(context: ColumnRenderContext) -> str:
    links: list[str] = []
    if context.previous is not None:
        links.append(
            _html_link(
                f"上一篇：{context.previous.title}",
                context.previous.html_href,
            )
        )
    links.append(_html_link("返回目录", context.directory.html_href))
    if context.next is not None:
        links.append(
            _html_link(
                f"下一篇：{context.next.title}",
                context.next.html_href,
            )
        )
    return " · ".join(links)


def _comments_to_markdown(
    thread: CommentThread,
    *,
    heading_level: int,
    paths: Mapping[str, str],
) -> str:
    heading_level = max(1, min(5, heading_level))
    lines = [
        f"{'#' * heading_level} 评论",
        "",
        (
            f"> 已抓取 {len(thread.comments)} 条一级评论"
            f"（接口返回顺序；一级最多 {thread.root_limit} 条，"
            f"每条二级最多 {thread.reply_limit} 条）"
        ),
    ]
    for comment in thread.comments:
        lines.extend(
            [
                "",
                *_comment_to_markdown(
                    comment,
                    heading_level=heading_level + 1,
                    paths=paths,
                ),
            ]
        )
    return "\n".join(lines)


def _comment_to_markdown(
    comment: Comment,
    *,
    heading_level: int,
    paths: Mapping[str, str],
) -> list[str]:
    heading_level = min(6, heading_level)
    author = comment.author.name if comment.author is not None else "匿名或已删除用户"
    lines = [f"{'#' * heading_level} {_markdown_single_line(author)} · {comment.like_count} 赞"]
    if comment.created_at is not None:
        lines.extend(["", f"> {comment.created_at.date().isoformat()}"])
    body = _blocks_to_markdown(comment.blocks, paths=paths).strip()
    if body:
        lines.extend(["", body])
    if comment.replies:
        reply_heading = min(6, heading_level + 1)
        lines.extend(["", f"{'#' * reply_heading} 二级回复"])
        for reply in comment.replies:
            lines.extend(
                [
                    "",
                    *_comment_to_markdown(
                        reply,
                        heading_level=min(6, reply_heading + 1),
                        paths=paths,
                    ),
                ]
            )
    return lines


def _comments_to_html(
    thread: CommentThread,
    *,
    heading_level: int,
    paths: Mapping[str, str],
) -> str:
    heading_level = max(1, min(5, heading_level))
    comments = "".join(
        _comment_to_html(
            comment,
            heading_level=heading_level + 1,
            reply=False,
            paths=paths,
        )
        for comment in thread.comments
    )
    return (
        '      <section class="comments">\n'
        f"        <h{heading_level}>评论</h{heading_level}>\n"
        '        <p class="comment-metadata">'
        f"已抓取 {len(thread.comments)} 条一级评论"
        f"（接口返回顺序；一级最多 {thread.root_limit} 条，"
        f"每条二级最多 {thread.reply_limit} 条）</p>\n"
        f"{comments}"
        "      </section>\n"
    )


def _comment_to_html(
    comment: Comment,
    *,
    heading_level: int,
    reply: bool,
    paths: Mapping[str, str],
) -> str:
    heading_level = min(6, heading_level)
    author = comment.author.name if comment.author is not None else "匿名或已删除用户"
    css_class = "reply" if reply else "comment"
    date = (
        f"          <time>{comment.created_at.date().isoformat()}</time>\n"
        if comment.created_at
        else ""
    )
    replies = "".join(
        _comment_to_html(
            child,
            heading_level=min(6, heading_level + 1),
            reply=True,
            paths=paths,
        )
        for child in comment.replies
    )
    reply_heading = (
        f"          <h{min(6, heading_level + 1)}>二级回复</h{min(6, heading_level + 1)}>\n"
        if comment.replies
        else ""
    )
    return (
        f'        <article class="{css_class}">\n'
        f"          <h{heading_level}>{html.escape(author)} · {comment.like_count} 赞</h{heading_level}>\n"
        f"{date}"
        f"{_blocks_to_html(comment.blocks, paths=paths, indent='          ')}\n"
        f"{reply_heading}"
        f"{replies}"
        "        </article>\n"
    )


def _articles_by_year(
    articles: Sequence[Article],
) -> list[tuple[str, list[Article]]]:
    grouped: dict[int | None, list[Article]] = {}
    for article in articles:
        year = article.published_at.year if article.published_at else None
        grouped.setdefault(year, []).append(article)
    ordered_years = sorted(
        grouped,
        key=lambda value: (value is not None, value or 0),
        reverse=True,
    )
    return [
        (f"{year} 年" if year is not None else "日期未知", grouped[year]) for year in ordered_years
    ]


def _html_document(
    title: str,
    body: str,
    *,
    stylesheet_href: str,
) -> str:
    escaped_title = html.escape(title)
    return (
        "<!doctype html>\n"
        '<html lang="zh-CN">\n'
        "  <head>\n"
        '    <meta charset="utf-8">\n'
        '    <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"    <title>{escaped_title}</title>\n"
        f'    <link rel="stylesheet" href="{html.escape(stylesheet_href, quote=True)}">\n'
        "  </head>\n"
        "  <body>\n"
        f"{body}"
        "  </body>\n"
        "</html>\n"
    )


def _inlines_plain_text(inlines: Sequence[Inline]) -> str:
    parts: list[str] = []
    for inline in inlines:
        if isinstance(inline, Text):
            parts.append(inline.text)
        elif isinstance(inline, Link):
            parts.append(inline.label)
        elif isinstance(inline, CodeSpan):
            parts.append(inline.code)
        elif isinstance(inline, InlineFormula):
            parts.append(inline.tex)
        elif isinstance(inline, LineBreak):
            parts.append("\n")
    return "".join(parts)


def _blocks_to_markdown(
    blocks: Sequence[Block],
    *,
    paths: Mapping[str, str],
) -> str:
    rendered = [_block_to_markdown(block, paths=paths) for block in blocks]
    return "\n\n".join(part for part in rendered if part)


def _block_to_markdown(block: Block, *, paths: Mapping[str, str]) -> str:
    if isinstance(block, Paragraph):
        return _inlines_to_markdown(block.inlines)
    if isinstance(block, Heading):
        level = max(1, min(6, block.level))
        return f"{'#' * level} {_inlines_to_markdown(block.inlines)}"
    if isinstance(block, Quote):
        nested = _blocks_to_markdown(block.blocks, paths=paths)
        return "\n".join(f"> {line}" if line else ">" for line in nested.splitlines())
    if isinstance(block, ListBlock):
        lines: list[str] = []
        for index, item in enumerate(block.items, start=1):
            marker = f"{index}." if block.ordered else "-"
            nested = _blocks_to_markdown(item, paths=paths)
            item_lines = nested.splitlines() or [""]
            lines.append(f"{marker} {item_lines[0]}")
            lines.extend(f"   {line}" for line in item_lines[1:])
        return "\n".join(lines)
    if isinstance(block, CodeBlock):
        fence = _backtick_fence(block.code, minimum=3)
        language = block.language if re.fullmatch(r"[A-Za-z0-9_+.-]*", block.language) else ""
        return f"{fence}{language}\n{block.code}\n{fence}"
    if isinstance(block, FormulaBlock):
        return f"$$\n{_markdown_formula_tex(block.tex)}\n$$"
    if isinstance(block, EmbeddedVideo):
        return _markdown_link(f"视频：{block.title or '查看原视频'}", block.source_url)
    if isinstance(block, MediaBlock):
        source = _media_source(block.asset, paths=paths)
        if not source:
            return block.asset.alt_text or block.caption
        if block.asset.kind is MediaKind.VIDEO:
            rendered = _markdown_link(
                f"视频：{block.asset.alt_text or block.caption or '播放或下载'}",
                source,
            )
            original = _media_original_source(block.asset)
            if original and original != source:
                rendered += f"\n\n{_markdown_link('原始视频链接', original)}"
            return rendered
        if _is_local_media_reference(source):
            rendered = (
                f"![{_escape_markdown_label(block.asset.alt_text)}]({_markdown_href(source)})"
            )
        else:
            label = block.asset.alt_text or block.caption or "媒体"
            rendered = _markdown_link(f"远程媒体未下载：{label}", source)
        return (
            f"{rendered}\n\n{_escape_markdown_text(block.caption)}" if block.caption else rendered
        )
    if isinstance(block, TableBlock):
        width = max(
            len(block.headers),
            max((len(row) for row in block.rows), default=0),
        )
        if width == 0:
            return ""
        headers = list(block.headers) or [()] * width
        headers.extend([()] * (width - len(headers)))
        lines = [
            "| "
            + " | ".join(_escape_table_cell(_inlines_to_markdown(cell)) for cell in headers)
            + " |",
            "| " + " | ".join("---" for _ in range(width)) + " |",
        ]
        for row in block.rows:
            cells = [*row, *([()] * (width - len(row)))]
            lines.append(
                "| "
                + " | ".join(_escape_table_cell(_inlines_to_markdown(cell)) for cell in cells)
                + " |"
            )
        return "\n".join(lines)
    if isinstance(block, Divider):
        return "---"
    raise TypeError(f"Unsupported block type: {type(block).__name__}")


def _inlines_to_markdown(inlines: Sequence[Inline]) -> str:
    rendered: list[str] = []
    for inline in inlines:
        if isinstance(inline, Text):
            value = _escape_markdown_text(inline.text)
            if inline.bold:
                value = f"**{value}**"
            if inline.italic:
                value = f"*{value}*"
            rendered.append(value)
        elif isinstance(inline, Link):
            rendered.append(_markdown_link(inline.label, inline.url))
        elif isinstance(inline, CodeSpan):
            fence = _backtick_fence(inline.code)
            padding = (
                " "
                if inline.code.startswith(("`", " ")) or inline.code.endswith(("`", " "))
                else ""
            )
            rendered.append(f"{fence}{padding}{inline.code}{padding}{fence}")
        elif isinstance(inline, InlineFormula):
            rendered.append(f"${_markdown_formula_tex(inline.tex)}$")
        elif isinstance(inline, LineBreak):
            rendered.append("  \n")
    return "".join(rendered)


def _blocks_to_html(
    blocks: Sequence[Block],
    *,
    paths: Mapping[str, str],
    indent: str = "      ",
) -> str:
    return "\n".join(_block_to_html(block, paths=paths, indent=indent) for block in blocks)


def _block_to_html(
    block: Block,
    *,
    paths: Mapping[str, str],
    indent: str,
) -> str:
    if isinstance(block, Paragraph):
        return f"{indent}<p>{_inlines_to_html(block.inlines)}</p>"
    if isinstance(block, Heading):
        level = max(1, min(6, block.level))
        return f"{indent}<h{level}>{_inlines_to_html(block.inlines)}</h{level}>"
    if isinstance(block, Quote):
        nested = _blocks_to_html(block.blocks, paths=paths, indent=f"{indent}  ")
        return f"{indent}<blockquote>\n{nested}\n{indent}</blockquote>"
    if isinstance(block, ListBlock):
        tag = "ol" if block.ordered else "ul"
        items = []
        for item in block.items:
            nested = _blocks_to_html(item, paths=paths, indent=f"{indent}    ")
            items.append(f"{indent}  <li>\n{nested}\n{indent}  </li>")
        return f"{indent}<{tag}>\n" + "\n".join(items) + f"\n{indent}</{tag}>"
    if isinstance(block, CodeBlock):
        language = (
            f' class="language-{html.escape(block.language, quote=True)}"' if block.language else ""
        )
        return f"{indent}<pre><code{language}>{html.escape(block.code)}</code></pre>"
    if isinstance(block, FormulaBlock):
        tex = html.escape(_safe_formula_trace(block.tex), quote=True)
        mathml = _formula_to_html(block.tex, display="block")
        return f'{indent}<div class="math-display" data-tex="{tex}">{mathml}</div>'
    if isinstance(block, EmbeddedVideo):
        link = _html_link(f"视频：{block.title or '查看原视频'}", block.source_url)
        return f"{indent}<p>{link}</p>"
    if isinstance(block, MediaBlock):
        source = _safe_url(_media_source(block.asset, paths=paths))
        if not source:
            return f"{indent}<p>{html.escape(block.asset.alt_text or block.caption)}</p>"
        if not _is_local_media_reference(source):
            label = block.asset.alt_text or block.caption or "媒体"
            remote = _html_link(f"远程媒体未下载：{label}", source)
            return f'{indent}<p class="remote-media">{remote}</p>'
        escaped_source = html.escape(source, quote=True)
        alt = html.escape(block.asset.alt_text, quote=True)
        if block.asset.kind is MediaKind.VIDEO:
            media_html = f'<video controls preload="metadata" src="{escaped_source}"></video>'
        else:
            media_html = f'<img src="{escaped_source}" alt="{alt}">'
        if block.caption:
            caption = html.escape(block.caption)
            return f"{indent}<figure>{media_html}<figcaption>{caption}</figcaption></figure>"
        return f"{indent}<figure>{media_html}</figure>"
    if isinstance(block, TableBlock):
        head = ""
        if block.headers:
            cells = "".join(f"<th>{_inlines_to_html(cell)}</th>" for cell in block.headers)
            head = f"<thead><tr>{cells}</tr></thead>"
        rows = "".join(
            "<tr>" + "".join(f"<td>{_inlines_to_html(cell)}</td>" for cell in row) + "</tr>"
            for row in block.rows
        )
        return f"{indent}<table>{head}<tbody>{rows}</tbody></table>"
    if isinstance(block, Divider):
        return f"{indent}<hr>"
    raise TypeError(f"Unsupported block type: {type(block).__name__}")


def _inlines_to_html(inlines: Sequence[Inline]) -> str:
    rendered: list[str] = []
    for inline in inlines:
        if isinstance(inline, Text):
            value = html.escape(inline.text)
            if inline.bold:
                value = f"<strong>{value}</strong>"
            if inline.italic:
                value = f"<em>{value}</em>"
            rendered.append(value)
        elif isinstance(inline, Link):
            rendered.append(_html_link(inline.label, inline.url))
        elif isinstance(inline, CodeSpan):
            rendered.append(f"<code>{html.escape(inline.code)}</code>")
        elif isinstance(inline, InlineFormula):
            tex = html.escape(_safe_formula_trace(inline.tex), quote=True)
            mathml = _formula_to_html(inline.tex, display="inline")
            rendered.append(f'<span class="math-inline" data-tex="{tex}">{mathml}</span>')
        elif isinstance(inline, LineBreak):
            rendered.append("<br>")
    return "".join(rendered)


def _formula_to_html(tex: str, *, display: str) -> str:
    """Convert trusted text to MathML, preserving readable TeX on malformed input."""

    try:
        converted = latex2mathml_converter.convert(tex, display=display)
        return _sanitize_mathml(converted)
    except Exception:
        return html.escape(_safe_formula_trace(tex))


def _sanitize_mathml(markup: str) -> str:
    root = ET.fromstring(markup)
    for element in root.iter():
        for attribute in tuple(element.attrib):
            local_name = attribute.rsplit("}", maxsplit=1)[-1].split(":")[-1].casefold()
            if local_name in {"href", "src", "style"} or local_name.startswith("on"):
                del element.attrib[attribute]
    return ET.tostring(root, encoding="unicode", short_empty_elements=True)


def _safe_formula_trace(tex: str) -> str:
    return re.sub(
        r"(?i)\b(?:javascript|vbscript|data)\s*:",
        "blocked:",
        tex,
    )


def _markdown_formula_tex(tex: str) -> str:
    return _safe_formula_trace(tex).replace("<", r"\lt ").replace(">", r"\gt ")


def _combined_paths(
    image_paths: Mapping[str, str] | None,
    media_paths: Mapping[str, str] | None,
) -> Mapping[str, str]:
    if not image_paths:
        return media_paths or {}
    if not media_paths:
        return image_paths
    return {**image_paths, **media_paths}


def _media_source(asset: MediaAsset, *, paths: Mapping[str, str]) -> str:
    if asset.archive_path:
        return asset.archive_path
    for rendition in asset.renditions:
        if local := paths.get(rendition.source_url):
            return local
    if local := paths.get(asset.id):
        return local
    return asset.renditions[0].source_url if asset.renditions else ""


def _media_original_source(asset: MediaAsset) -> str:
    return asset.renditions[0].source_url if asset.renditions else ""


def _cover_to_markdown(
    source_url: str | None,
    title: str,
    *,
    paths: Mapping[str, str],
) -> str:
    if not source_url:
        return ""
    rendered_source = _safe_url(paths.get(source_url, source_url))
    if rendered_source is None:
        return ""
    if not _is_local_media_reference(rendered_source):
        return _markdown_link(f"远程封面未下载：{title}", rendered_source)
    alt = _escape_markdown_label(f"{title}封面")
    image = f"![{alt}]({_markdown_href(rendered_source)})"
    original = _safe_url(source_url)
    if original is None:
        return image
    return f"[{image}]({_markdown_href(original)})"


def _cover_to_html(
    source_url: str | None,
    title: str,
    *,
    paths: Mapping[str, str],
) -> str:
    if not source_url:
        return ""
    rendered_source = _safe_url(paths.get(source_url, source_url))
    if rendered_source is None:
        return ""
    if not _is_local_media_reference(rendered_source):
        link = _html_link(f"远程封面未下载：{title}", rendered_source)
        return f'      <p class="remote-media">{link}</p>\n'
    image = (
        '      <img class="cover" '
        f'src="{html.escape(rendered_source, quote=True)}" '
        f'alt="{html.escape(f"{title}封面", quote=True)}">\n'
    )
    original = _safe_url(source_url)
    if original is None:
        return image
    return (
        f'      <a class="cover-link" href="{html.escape(original, quote=True)}">\n'
        f"{image}"
        "      </a>\n"
    )


def _markdown_link(label: str, url: str) -> str:
    safe = _safe_url(url)
    if safe is None:
        return _escape_markdown_label(label)
    return f"[{_escape_markdown_label(label)}]({_markdown_href(safe)})"


def _html_link(label: str, url: str) -> str:
    safe = _safe_url(url)
    escaped_label = html.escape(label)
    if safe is None:
        return escaped_label
    return f'<a href="{html.escape(safe, quote=True)}">{escaped_label}</a>'


def _safe_url(value: str) -> str | None:
    candidate = value.strip()
    if not candidate or any(ord(character) < 32 for character in candidate):
        return None
    parsed = urlsplit(candidate)
    if parsed.scheme.lower() not in {"", "http", "https", "mailto"}:
        return None
    return candidate


def _is_local_media_reference(value: str) -> bool:
    """Return whether a media reference is an inert archive-local path."""

    parsed = urlsplit(value)
    return (
        not parsed.scheme
        and not parsed.netloc
        and not value.startswith(("/", "\\"))
        and "\\" not in value
    )


def _markdown_href(value: str) -> str:
    return value.replace("\\", "%5C").replace(" ", "%20").replace("(", "%28").replace(")", "%29")


def _escape_markdown_label(value: str) -> str:
    return _markdown_single_line(value)


def _escape_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def _escape_markdown_text(value: str) -> str:
    escaped = re.sub(r"([\\`*_[\]<>])", r"\\\1", value)
    escaped = re.sub(r"(?m)^([ \t]{0,3})([#>])(?=\s)", r"\1\\\2", escaped)
    escaped = re.sub(r"(?m)^([ \t]{0,3})([-+])(?=\s)", r"\1\\\2", escaped)
    return re.sub(
        r"(?m)^([ \t]{0,3})(\d{1,9})([.)])(?=\s)",
        r"\1\2\\\3",
        escaped,
    )


def _markdown_single_line(value: str) -> str:
    normalized = " ".join(value.replace("\r\n", "\n").replace("\r", "\n").splitlines())
    return _escape_markdown_text(normalized)


def _backtick_fence(value: str, *, minimum: int = 1) -> str:
    longest = max((len(match.group(0)) for match in re.finditer(r"`+", value)), default=0)
    return "`" * max(minimum, longest + 1)
