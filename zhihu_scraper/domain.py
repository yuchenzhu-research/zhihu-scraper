"""Normalized domain contracts for the rebuilt archive core."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class Author:
    id: str | None
    name: str
    url: str | None = None


@dataclass(frozen=True, slots=True)
class Text:
    text: str
    bold: bool = False
    italic: bool = False


@dataclass(frozen=True, slots=True)
class Link:
    label: str
    url: str


@dataclass(frozen=True, slots=True)
class CodeSpan:
    code: str


@dataclass(frozen=True, slots=True)
class InlineFormula:
    tex: str


@dataclass(frozen=True, slots=True)
class LineBreak:
    pass


Inline = Text | Link | CodeSpan | InlineFormula | LineBreak
TableCell = tuple[Inline, ...]


@dataclass(frozen=True, slots=True)
class Paragraph:
    inlines: tuple[Inline, ...]


@dataclass(frozen=True, slots=True)
class Heading:
    level: int
    inlines: tuple[Inline, ...]


@dataclass(frozen=True, slots=True)
class Quote:
    blocks: tuple[Block, ...]


@dataclass(frozen=True, slots=True)
class ListBlock:
    ordered: bool
    items: tuple[tuple[Block, ...], ...]


@dataclass(frozen=True, slots=True)
class CodeBlock:
    code: str
    language: str = ""


@dataclass(frozen=True, slots=True)
class FormulaBlock:
    tex: str


class MediaKind(StrEnum):
    IMAGE = "image"
    ANIMATION = "animation"
    VIDEO = "video"


@dataclass(frozen=True, slots=True)
class MediaRendition:
    source_url: str
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    bitrate: int | None = None
    size_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class MediaAsset:
    id: str
    kind: MediaKind
    renditions: tuple[MediaRendition, ...]
    alt_text: str = ""
    archive_path: str | None = None


@dataclass(frozen=True, slots=True)
class MediaBlock:
    asset: MediaAsset
    caption: str = ""


@dataclass(frozen=True, slots=True)
class EmbeddedVideo:
    """A video card whose page is distinct from its downloadable media."""

    video_id: str
    source_url: str
    title: str = ""


@dataclass(frozen=True, slots=True)
class TableBlock:
    headers: tuple[TableCell, ...]
    rows: tuple[tuple[TableCell, ...], ...]


@dataclass(frozen=True, slots=True)
class Divider:
    pass


Block = (
    Paragraph
    | Heading
    | Quote
    | ListBlock
    | CodeBlock
    | FormulaBlock
    | MediaBlock
    | EmbeddedVideo
    | TableBlock
    | Divider
)
ContentBlock = Block


@dataclass(frozen=True, slots=True)
class ColumnRef:
    token: str
    title: str
    url: str


@dataclass(frozen=True, slots=True)
class Comment:
    id: str
    author: Author | None
    blocks: tuple[Block, ...]
    created_at: datetime | None
    like_count: int
    replies: tuple[Comment, ...] = ()
    replies_complete: bool = False


@dataclass(frozen=True, slots=True)
class CommentThread:
    comments: tuple[Comment, ...]
    order: str
    roots_complete: bool = False
    root_limit: int = 10
    reply_limit: int = 10


@dataclass(frozen=True, slots=True)
class Article:
    id: str
    title: str
    source_url: str
    author: Author
    published_at: datetime | None
    blocks: tuple[Block, ...]
    updated_at: datetime | None = None
    voteup_count: int = 0
    cover_url: str | None = None
    columns: tuple[ColumnRef, ...] = ()
    comments: CommentThread | None = None


@dataclass(frozen=True, slots=True)
class QuestionRef:
    id: str
    title: str
    url: str


@dataclass(frozen=True, slots=True)
class Answer:
    id: str
    question: QuestionRef
    source_url: str
    author: Author
    published_at: datetime | None
    blocks: tuple[Block, ...]
    updated_at: datetime | None = None
    voteup_count: int = 0
    comments: CommentThread | None = None

    @property
    def title(self) -> str:
        return self.question.title


@dataclass(frozen=True, slots=True)
class Question:
    id: str
    title: str
    source_url: str
    detail: tuple[Block, ...] = ()
    author: Author | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    answer_count: int = 0
    follower_count: int = 0


@dataclass(frozen=True, slots=True)
class QuestionArchive:
    question: Question
    answers: tuple[Answer, ...]
    archived_at: datetime

    @property
    def id(self) -> str:
        return self.question.id

    @property
    def title(self) -> str:
        return self.question.title

    @property
    def source_url(self) -> str:
        return self.question.source_url


@dataclass(frozen=True, slots=True)
class Column:
    token: str
    title: str
    source_url: str
    description: str
    author: Author | None
    item_count: int


@dataclass(frozen=True, slots=True)
class ColumnArchive:
    column: Column
    articles: tuple[Article, ...]
    archived_at: datetime

    @property
    def id(self) -> str:
        return self.column.token

    @property
    def title(self) -> str:
        return self.column.title

    @property
    def source_url(self) -> str:
        return self.column.source_url


@dataclass(frozen=True, slots=True)
class Video:
    id: str
    title: str
    source_url: str
    author: Author
    published_at: datetime | None
    description: tuple[Block, ...]
    asset: MediaAsset
    updated_at: datetime | None = None
    cover_url: str | None = None
    voteup_count: int = 0
    comments: CommentThread | None = None


ArchiveTarget = Article | Answer | QuestionArchive | ColumnArchive | Video
