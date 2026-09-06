from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath
from unittest.mock import patch

import pytest

from zhihu_scraper.archive import LocalArchive
from zhihu_scraper.domain import (
    Answer,
    Article,
    Author,
    Column,
    ColumnArchive,
    MediaAsset,
    MediaBlock,
    MediaKind,
    MediaRendition,
    Paragraph,
    Question,
    QuestionArchive,
    QuestionRef,
    Text,
)
from zhihu_scraper.media import MediaDownloadReceipt
from zhihu_scraper.platform import ArchivePathError, RuntimePlatform
from zhihu_scraper.render import MarkdownRenderer

NOW = datetime(2026, 9, 5, tzinfo=UTC)
AUTHOR = Author("author", "作者")
IMAGE = MediaAsset(
    "🧠" + "a" * 100,
    MediaKind.IMAGE,
    (MediaRendition("https://pic1.zhimg.com/archive.webp", mime_type="image/webp"),),
)


def utf16_units(path: Path) -> int:
    return len(str(path).encode("utf-16-le")) // 2


def output_at_depth(base: Path, units: int) -> Path:
    padding = units - utf16_units(base) - 1
    assert padding > 0, "The system temporary directory must leave room for the archive root."
    return base / ("d" * padding)


def fake_downloader(url: str, destination: Path, *, expected_size=None) -> MediaDownloadReceipt:
    assert destination.name.isascii()
    assert len(destination.name) == 64
    resume_temporary = destination.with_name(f"{destination.name}.part.resume.tmp")
    assert utf16_units(resume_temporary) <= 259
    destination.parent.mkdir(parents=True, exist_ok=True)
    resume_temporary.write_bytes(b"resume")
    resume_temporary.unlink()
    destination.write_bytes(b"media")
    return MediaDownloadReceipt(url, destination, resumed_from=0, bytes_total=5)


def assert_portable_archive(root: Path) -> None:
    for path in root.rglob("*"):
        assert utf16_units(path) <= 259, path
        if path.suffix in {".md", ".html"}:
            assert utf16_units(path.with_name(f".{path.name}.tmp")) <= 259, path


@pytest.fixture
def windows_runtime():
    runtime = RuntimePlatform.for_system(
        "Windows", home_directory=PureWindowsPath("C:/Users/Ada"), environment={}
    )
    with patch("zhihu_scraper.platform.RuntimePlatform.detect", return_value=runtime):
        yield runtime


@pytest.mark.parametrize("root_units", (110, 145))
@pytest.mark.parametrize(
    "title",
    ("Readable-title-" * 40, "中文标题" * 100, "🧠数学" * 100),
    ids=("ascii", "chinese", "emoji"),
)
def test_real_column_paths_fit_windows_budget_with_unicode_and_media(
    windows_runtime,
    root_units: int,
    title: str,
) -> None:
    article = Article(
        "1",
        title,
        "https://zhuanlan.zhihu.com/p/1",
        AUTHOR,
        NOW,
        (MediaBlock(IMAGE),),
    )
    target = ColumnArchive(
        Column("test", title, "https://www.zhihu.com/column/test", "", AUTHOR, 1),
        (article,),
        NOW,
    )
    with tempfile.TemporaryDirectory(prefix="z") as directory:
        root = output_at_depth(Path(directory), root_units)
        receipt = LocalArchive(root, html=True, downloader=fake_downloader).archive(target)

        assert receipt.markdown_path.is_file()
        assert receipt.child_html_paths[0].parent.name == "内容"
        assert receipt.child_html_paths[0].is_file()
        assert len(receipt.media_downloads) == 1
        assert_portable_archive(root)


@pytest.mark.parametrize("kind", ("question", "pdf_column"))
def test_recovery_fragment_paths_also_fit_windows_budget(windows_runtime, kind: str) -> None:
    title = "🧠长标题" * 100
    if kind == "question":
        target = QuestionArchive(
            Question("10", title, "https://www.zhihu.com/question/10"),
            (),
            NOW,
        )
        item = Answer(
            "20",
            QuestionRef("10", title, "https://www.zhihu.com/question/10"),
            "https://www.zhihu.com/question/10/answer/20",
            Author("author", title),
            NOW,
            (MediaBlock(IMAGE),),
        )
    else:
        target = ColumnArchive(
            Column("test", title, "https://www.zhihu.com/column/test", "", AUTHOR, 1),
            (),
            NOW,
        )
        item = Article(
            "1", title, "https://zhuanlan.zhihu.com/p/1", AUTHOR, NOW, (MediaBlock(IMAGE),)
        )

    with tempfile.TemporaryDirectory(prefix="z") as directory:
        root = output_at_depth(Path(directory), 145)
        archive = LocalArchive(
            root,
            markdown=kind == "question",
            pdf=kind == "pdf_column",
            downloader=fake_downloader,
        )
        batch = archive.begin_batch(target)
        receipt = batch.write_item(item)
        batch.interrupt()

        assert receipt.markdown_path.is_file()
        assert receipt.markdown_path.parent.name == (
            "回答片段" if kind == "question" else "归档片段"
        )
        assert_portable_archive(root)


def test_existing_overlong_document_is_preserved_without_silent_renaming(windows_runtime) -> None:
    article = Article(
        "1",
        "Updated title",
        "https://zhuanlan.zhihu.com/p/1",
        AUTHOR,
        NOW,
        (Paragraph((Text("original body"),)),),
    )
    with tempfile.TemporaryDirectory(prefix="z") as directory:
        root = output_at_depth(Path(directory), 145)
        existing_directory = root / "kept"
        existing_directory.mkdir(parents=True)
        stem_length = 257 - utf16_units(existing_directory) - len("/.md")
        existing = existing_directory / ("l" * stem_length + ".md")
        original = MarkdownRenderer().render(article).encode("utf-8")
        existing.write_bytes(original)
        before = {path.relative_to(root) for path in root.rglob("*")}

        with pytest.raises(ArchivePathError):
            LocalArchive(root, html=True, media_download=False).archive(article)

        assert existing.read_bytes() == original
        assert {path.relative_to(root) for path in root.rglob("*")} == before


def test_existing_deep_entry_rejects_media_before_overwriting_its_document(windows_runtime) -> None:
    article = Article(
        "1",
        "Updated title",
        "https://zhuanlan.zhihu.com/p/1",
        AUTHOR,
        NOW,
        (MediaBlock(IMAGE),),
    )
    with tempfile.TemporaryDirectory(prefix="z") as directory:
        root = output_at_depth(Path(directory), 145)
        existing_directory = root / ("kept-" * 12)
        existing_directory.mkdir(parents=True)
        existing = existing_directory / "short.md"
        original = MarkdownRenderer().render(article).encode("utf-8")
        existing.write_bytes(original)
        before = {path.relative_to(root) for path in root.rglob("*")}

        with pytest.raises(ArchivePathError):
            LocalArchive(root, downloader=fake_downloader).archive(article)

        assert existing.read_bytes() == original
        assert {path.relative_to(root) for path in root.rglob("*")} == before


def test_overdeep_root_is_rejected_before_archive_directories_are_created(windows_runtime) -> None:
    with tempfile.TemporaryDirectory(prefix="z") as directory:
        root = output_at_depth(Path(directory), 180)
        with pytest.raises(ArchivePathError):
            LocalArchive(root)
        assert not root.exists()
