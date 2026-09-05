"""Normalize Zhihu rich-text HTML into a small semantic content tree.

Only this module knows about Zhihu's HTML. Renderers and storage operate on
the domain objects, which keeps presentation changes away from acquisition.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup, NavigableString, Tag

from .domain import (
    Block,
    CodeBlock,
    CodeSpan,
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
    MediaRendition,
    Paragraph,
    Quote,
    TableBlock,
    Text,
)

_REMOVED_TAGS = {
    "script",
    "style",
    "noscript",
    "iframe",
    "object",
    "embed",
    "form",
    "button",
}
_BLOCK_TAGS = {
    "p",
    "div",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "pre",
    "blockquote",
    "ul",
    "ol",
    "table",
    "figure",
    "hr",
}
_DANGEROUS_SCHEMES = {"javascript", "data", "vbscript"}


def parse_rich_text(
    fragment: str,
    *,
    base_url: str = "https://www.zhihu.com/",
) -> tuple[Block, ...]:
    """Parse a trusted-or-untrusted HTML fragment without retaining raw HTML."""

    soup = BeautifulSoup(fragment or "", "html.parser")
    for unwanted in soup.find_all(_REMOVED_TAGS):
        unwanted.decompose()
    return tuple(_parse_block_children(soup.children, base_url=base_url))


def _parse_block_children(
    nodes: Iterable[object],
    *,
    base_url: str,
) -> list[Block]:
    blocks: list[Block] = []
    loose_inlines: list[Inline] = []

    def flush_loose_text() -> None:
        normalized = _trim_inline_edges(loose_inlines)
        if _has_visible_inline(normalized):
            blocks.append(Paragraph(tuple(normalized)))
        loose_inlines.clear()

    for node in nodes:
        if isinstance(node, NavigableString):
            text = _inline_text(str(node))
            if text:
                loose_inlines.append(Text(text))
            continue
        if not isinstance(node, Tag) or node.name in _REMOVED_TAGS:
            continue

        name = node.name.casefold()
        if video := _video_from_node(node, base_url=base_url):
            flush_loose_text()
            blocks.append(video)
        elif name == "p":
            flush_loose_text()
            blocks.extend(_parse_paragraph(node, base_url=base_url))
        elif name == "div":
            flush_loose_text()
            if _is_display_formula_node(node):
                formula = _first_formula(node)
                if formula:
                    blocks.append(FormulaBlock(_normalize_formula(formula)))
            else:
                blocks.extend(_parse_block_children(node.children, base_url=base_url))
        elif name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            flush_loose_text()
            inlines = _trim_inline_edges(_parse_inline_children(node.children, base_url=base_url))
            if _has_visible_inline(inlines):
                blocks.append(Heading(level=int(name[1]), inlines=tuple(inlines)))
        elif name == "pre":
            flush_loose_text()
            blocks.append(_parse_code_block(node))
        elif name == "blockquote":
            flush_loose_text()
            nested = tuple(_parse_block_children(node.children, base_url=base_url))
            if nested:
                blocks.append(Quote(nested))
        elif name in {"ul", "ol"}:
            flush_loose_text()
            blocks.append(_parse_list(node, base_url=base_url))
        elif name == "table":
            flush_loose_text()
            table = _parse_table(node, base_url=base_url)
            if table.headers or table.rows:
                blocks.append(table)
        elif name == "figure":
            flush_loose_text()
            figure_blocks = _parse_figure(node)
            blocks.extend(figure_blocks or _parse_block_children(node.children, base_url=base_url))
        elif name == "hr":
            flush_loose_text()
            blocks.append(Divider())
        elif name == "img":
            flush_loose_text()
            formula = _formula_from_node(node)
            if formula:
                blocks.append(FormulaBlock(_normalize_formula(formula)))
            elif media := _media_from_image(node):
                blocks.append(MediaBlock(media))
        elif name in _BLOCK_TAGS:
            flush_loose_text()
            blocks.extend(_parse_block_children(node.children, base_url=base_url))
        else:
            loose_inlines.extend(_parse_inline_node(node, base_url=base_url))

    flush_loose_text()
    return blocks


def _parse_paragraph(node: Tag, *, base_url: str) -> list[Block]:
    if _is_display_formula_node(node):
        formula = _first_formula(node)
        if formula:
            return [FormulaBlock(_normalize_formula(formula))]

    blocks: list[Block] = []
    inlines: list[Inline] = []

    def flush_inlines() -> None:
        normalized = _trim_inline_edges(inlines)
        if _has_visible_inline(normalized):
            blocks.append(Paragraph(tuple(normalized)))
        inlines.clear()

    for child in node.children:
        if isinstance(child, Tag) and (video := _video_from_node(child, base_url=base_url)):
            flush_inlines()
            blocks.append(video)
            continue
        if isinstance(child, Tag) and child.name == "img" and not _formula_from_node(child):
            flush_inlines()
            media = _media_from_image(child)
            if media:
                blocks.append(MediaBlock(media))
            continue
        inlines.extend(_parse_inline_node(child, base_url=base_url))
    flush_inlines()
    return blocks


def _parse_inline_children(
    nodes: Iterable[object],
    *,
    base_url: str,
) -> list[Inline]:
    inlines: list[Inline] = []
    for node in nodes:
        inlines.extend(_parse_inline_node(node, base_url=base_url))
    return inlines


def _parse_inline_node(
    node: object,
    *,
    base_url: str,
    bold: bool = False,
    italic: bool = False,
) -> list[Inline]:
    if isinstance(node, NavigableString):
        text = _inline_text(str(node))
        return [Text(text, bold=bold, italic=italic)] if text else []
    if not isinstance(node, Tag) or node.name in _REMOVED_TAGS:
        return []

    name = node.name.casefold()
    formula = _formula_from_node(node)
    if formula:
        return [InlineFormula(_normalize_formula(formula))]
    if name == "br":
        return [LineBreak()]
    if name == "a":
        raw_url = str(node.get("href") or "").strip()
        label = _block_text(node.get_text(" ", strip=True)) or raw_url
        safe_url = _safe_link(raw_url, base_url=base_url)
        return [Link(label=label, url=safe_url)] if safe_url else [Text(label)]
    if name == "code":
        return [CodeSpan(node.get_text())]
    if name in {"strong", "b"}:
        return _parse_styled_children(
            node,
            base_url=base_url,
            bold=True,
            italic=italic,
        )
    if name in {"em", "i"}:
        return _parse_styled_children(
            node,
            base_url=base_url,
            bold=bold,
            italic=True,
        )
    if name == "img":
        return []
    return _parse_styled_children(
        node,
        base_url=base_url,
        bold=bold,
        italic=italic,
    )


def _parse_styled_children(
    node: Tag,
    *,
    base_url: str,
    bold: bool,
    italic: bool,
) -> list[Inline]:
    inlines: list[Inline] = []
    for child in node.children:
        inlines.extend(
            _parse_inline_node(
                child,
                base_url=base_url,
                bold=bold,
                italic=italic,
            )
        )
    return inlines


def _parse_code_block(node: Tag) -> CodeBlock:
    code_node = node.find("code")
    code = (code_node or node).get_text()
    language = ""
    if code_node:
        language = next(
            (
                str(css_class).removeprefix("language-")
                for css_class in _css_classes(code_node)
                if str(css_class).startswith("language-")
            ),
            "",
        )
    return CodeBlock(code=code.strip("\n"), language=language)


def _parse_list(node: Tag, *, base_url: str) -> ListBlock:
    items: list[tuple[Block, ...]] = []
    for item in node.find_all("li", recursive=False):
        item_blocks = tuple(_parse_block_children(item.children, base_url=base_url))
        if not item_blocks:
            inlines = _trim_inline_edges(_parse_inline_children(item.children, base_url=base_url))
            item_blocks = (Paragraph(tuple(inlines)),) if _has_visible_inline(inlines) else ()
        items.append(item_blocks)
    return ListBlock(ordered=node.name == "ol", items=tuple(items))


def _parse_table(node: Tag, *, base_url: str) -> TableBlock:
    rows = [
        tuple(
            tuple(
                _trim_inline_edges(
                    _parse_inline_children(
                        cell.children,
                        base_url=base_url,
                    )
                )
            )
            for cell in row.find_all(["th", "td"])
        )
        for row in node.find_all("tr")
    ]
    rows = [row for row in rows if row]
    header_row = node.find("tr")
    has_headers = bool(header_row and header_row.find("th"))
    headers = rows[0] if rows and has_headers else ()
    data_rows = rows[1:] if headers else rows
    return TableBlock(headers=headers, rows=tuple(data_rows))


def _parse_figure(node: Tag) -> list[Block]:
    formula = _first_formula(node)
    if formula and _is_display_formula_node(node):
        return [FormulaBlock(_normalize_formula(formula))]
    image = node.find("img")
    if image is None:
        return []
    if formula := _formula_from_node(image):
        return [FormulaBlock(_normalize_formula(formula))]
    media = _media_from_image(image)
    if media is None:
        return []
    caption_node = node.find("figcaption")
    caption = _block_text(caption_node.get_text(" ", strip=True)) if caption_node else ""
    return [MediaBlock(asset=media, caption=caption)]


def _formula_from_node(node: Tag) -> str:
    classes = set(_css_classes(node))
    if "ztext-math" in classes:
        for attribute in ("data-tex", "data-formula", "alt"):
            value = node.get(attribute)
            if value:
                return str(value).strip()
    if node.name == "img":
        for attribute in ("data-original", "data-actualsrc", "src"):
            source = str(node.get(attribute) or "")
            if "zhihu.com/equation" not in source:
                continue
            values = parse_qs(urlparse(source).query).get("tex", [])
            if values:
                return values[0].strip()
    return ""


def _css_classes(node: Tag) -> tuple[str, ...]:
    value = node.get("class")
    if isinstance(value, str):
        return tuple(value.split())
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    return ()


def _first_formula(node: Tag) -> str:
    if own := _formula_from_node(node):
        return own
    for candidate in node.find_all(class_="ztext-math"):
        if formula := _formula_from_node(candidate):
            return formula
    return ""


def _is_display_formula_node(node: Tag) -> bool:
    visible_children = [
        child
        for child in node.children
        if not (isinstance(child, NavigableString) and not str(child).strip())
    ]
    if len(visible_children) != 1 or not isinstance(visible_children[0], Tag):
        return False
    return bool(_formula_from_node(visible_children[0]))


def _media_from_image(image: Tag) -> MediaAsset | None:
    urls: list[str] = []
    for attribute in ("data-original", "data-actualsrc", "src"):
        candidate = str(image.get(attribute) or "").strip()
        if candidate and not candidate.casefold().startswith("data:") and candidate not in urls:
            urls.append(candidate)
    if not urls:
        return None

    width = _optional_int(image.get("data-rawwidth") or image.get("width"))
    height = _optional_int(image.get("data-rawheight") or image.get("height"))
    renditions = tuple(
        MediaRendition(
            source_url=url,
            width=width if index == 0 else None,
            height=height if index == 0 else None,
        )
        for index, url in enumerate(urls)
    )
    original_path = urlparse(urls[0]).path.casefold()
    kind = MediaKind.ANIMATION if original_path.endswith((".gif", ".webp")) else MediaKind.IMAGE
    asset_id = hashlib.sha256(urls[0].encode("utf-8")).hexdigest()[:20]
    return MediaAsset(
        id=asset_id,
        kind=kind,
        renditions=renditions,
        alt_text=str(image.get("alt") or ""),
    )


def _video_from_node(node: Tag, *, base_url: str) -> Block | None:
    raw_id = str(node.get("data-lens-id") or "").strip()
    is_card = "video-box" in _css_classes(node)
    if not raw_id and not is_card and node.name != "video":
        return None
    title = _block_text(str(node.get("title") or node.get_text(" ", strip=True)))
    renditions = []
    fallback_url = ""
    candidates = (node, *node.find_all("source", recursive=False)) if node.name == "video" else ()
    for candidate in candidates:
        source_url = _safe_link(str(candidate.get("src") or ""), base_url=base_url)
        if not source_url:
            continue
        fallback_url = fallback_url or source_url
        parsed = urlparse(source_url)
        if parsed.scheme not in {"http", "https"} or not parsed.path.casefold().endswith(
            (".mp4", ".webm", ".mov", ".m4v")
        ):
            continue
        renditions.append(
            MediaRendition(
                source_url=source_url,
                mime_type=str(candidate.get("type") or "") or None,
                width=_optional_int(node.get("width")),
                height=_optional_int(node.get("height")),
            )
        )
    if renditions:
        asset_id = hashlib.sha256(renditions[0].source_url.encode()).hexdigest()[:20]
        return MediaBlock(
            MediaAsset(
                id=f"inline-video-{asset_id}",
                kind=MediaKind.VIDEO,
                renditions=tuple(renditions),
                alt_text=title,
            )
        )
    if raw_id or is_card:
        source_url = _safe_link(str(node.get("href") or ""), base_url=base_url)
        parsed = urlparse(source_url)
        trusted_page = (
            parsed.scheme in {"http", "https"}
            and parsed.hostname in {"www.zhihu.com", "zhihu.com"}
            and parsed.username is None
            and parsed.password is None
        )
        video_id = raw_id if re.fullmatch(r"[0-9]{1,30}", raw_id) else ""
        if not raw_id and trusted_page:
            match = re.fullmatch(r"/video/([0-9]{1,30})/?", parsed.path)
            video_id = match.group(1) if match else ""
        if video_id:
            return EmbeddedVideo(
                video_id=video_id,
                source_url=source_url
                if trusted_page
                else f"https://www.zhihu.com/video/{video_id}",
                title=title,
            )
    if fallback_url:
        return Paragraph((Link(title or "视频页面", fallback_url),))
    return None


def _safe_link(raw_url: str, *, base_url: str) -> str:
    if not raw_url:
        return ""
    absolute = urljoin(base_url, raw_url)
    scheme = urlparse(absolute).scheme.casefold()
    if scheme in _DANGEROUS_SCHEMES or scheme not in {"http", "https", "mailto"}:
        return ""
    return absolute


def _normalize_formula(formula: str) -> str:
    normalized = formula.strip()
    if normalized.startswith(r"\[") and normalized.endswith(r"\]"):
        normalized = normalized[2:-2].strip()
    return normalized


def _inline_text(value: str) -> str:
    return re.sub(r"\s+", " ", value)


def _block_text(value: str) -> str:
    return _inline_text(value).strip()


def _trim_inline_edges(inlines: list[Inline]) -> list[Inline]:
    if inlines and isinstance(inlines[0], Text):
        first = inlines[0]
        inlines[0] = Text(first.text.lstrip(), bold=first.bold, italic=first.italic)
    if inlines and isinstance(inlines[-1], Text):
        last = inlines[-1]
        inlines[-1] = Text(last.text.rstrip(), bold=last.bold, italic=last.italic)
    return [inline for inline in inlines if not isinstance(inline, Text) or inline.text]


def _has_visible_inline(inlines: Iterable[Inline]) -> bool:
    return any(not isinstance(inline, Text) or bool(inline.text) for inline in inlines)


def _optional_int(value: object) -> int | None:
    try:
        return int(str(value)) if value is not None else None
    except (TypeError, ValueError):
        return None
