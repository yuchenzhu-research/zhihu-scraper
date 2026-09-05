import os
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from zhihu_scraper.archive import LocalArchive
from zhihu_scraper.domain import (
    Answer,
    Article,
    Author,
    Column,
    ColumnArchive,
    ColumnRef,
    Comment,
    CommentThread,
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
from zhihu_scraper.settings import ArchiveSettings

NOW = datetime(2026, 7, 26, tzinfo=UTC)
AUTHOR = Author(id="author", name="作者")


class FakeDownloader:
    def __init__(self):
        self.calls = []

    def __call__(self, source_url, destination, *, expected_size=None):
        self.calls.append((source_url, destination))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"media")
        return MediaDownloadReceipt(
            source_url=source_url,
            destination=destination,
            resumed_from=0,
            bytes_total=5,
        )


class LocalArchiveLayoutTests(unittest.TestCase):
    def test_column_catalog_is_published_only_after_all_documents_and_styles_are_saved(self):
        first = Article(
            id="1",
            title="第一篇",
            source_url="https://zhuanlan.zhihu.com/p/1",
            author=AUTHOR,
            published_at=NOW,
            blocks=(Paragraph((Text("第一篇正文"),)),),
        )
        second = replace(first, id="2", title="第二篇", source_url="https://zhuanlan.zhihu.com/p/2")
        column = ColumnArchive(
            column=Column("test", "测试专栏", "https://www.zhihu.com/column/test", "", AUTHOR, 2),
            articles=(first, second),
            archived_at=NOW,
        )
        for existing, failed_filename in (
            (False, "第二篇.html"),
            (True, "第二篇.html"),
            (False, "archive.css"),
            (True, "archive.css"),
        ):
            with self.subTest(existing=existing, failed_filename=failed_filename):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    root = Path(temporary_directory)
                    sink = LocalArchive(root, html=True, media_download=False)
                    catalogs = tuple(
                        root / "测试专栏" / f"测试专栏{suffix}" for suffix in (".md", ".html")
                    )
                    if existing:
                        sink.archive(replace(column, articles=(first,)))
                    before = tuple(
                        path.read_bytes() if path.exists() else None for path in catalogs
                    )
                    replace_file = os.replace

                    def fail_file_write(source, destination):
                        if Path(destination).name == failed_filename:
                            raise OSError("模拟文件写入失败")
                        return replace_file(source, destination)

                    with patch("zhihu_scraper.archive.os.replace", side_effect=fail_file_write):
                        with self.assertRaisesRegex(OSError, "模拟文件写入失败"):
                            sink.archive(column)

                    self.assertEqual(
                        before,
                        tuple(path.read_bytes() if path.exists() else None for path in catalogs),
                    )
                    self.assertFalse(any(root.rglob("*.tmp")))
                    retried = sink.archive(column)
                    self.assertIn(
                        "内容/第二篇.md", retried.markdown_path.read_text(encoding="utf-8")
                    )
                    self.assertIn("内容/第二篇.html", retried.html_path.read_text(encoding="utf-8"))
                    self.assertTrue(all(path.exists() for path in retried.child_html_paths))

    def test_enabling_html_preserves_an_existing_unidentified_file(self):
        article = Article(
            id="1",
            title="归档标题",
            source_url="https://zhuanlan.zhihu.com/p/1",
            author=AUTHOR,
            published_at=NOW,
            blocks=(Paragraph((Text("正文"),)),),
        )
        column = ColumnArchive(
            column=Column("test", "专栏", "https://www.zhihu.com/column/test", "", AUTHOR, 1),
            articles=(article,),
            archived_at=NOW,
        )
        for target in (article, column):
            with self.subTest(target=type(target).__name__):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    root = Path(temporary_directory)
                    original = LocalArchive(root, media_download=False).archive(target)
                    original_page = (
                        original.child_markdown_paths[0]
                        if original.child_markdown_paths
                        else original.markdown_path
                    )
                    user_file = original_page.with_suffix(".html")
                    user_file.write_text("用户已有 HTML", encoding="utf-8")

                    updated = LocalArchive(root, html=True, media_download=False).archive(target)
                    updated_page = (
                        updated.child_html_paths[0]
                        if updated.child_html_paths
                        else updated.html_path
                    )
                    self.assertEqual(original.entry_directory, updated.entry_directory)
                    self.assertNotEqual(user_file, updated_page)
                    self.assertEqual("用户已有 HTML", user_file.read_text(encoding="utf-8"))
                    self.assertIn("正文", updated_page.read_text(encoding="utf-8"))

    def test_archive_identity_uses_the_zhihu_id_across_source_url_variants(self):
        article = Article(
            id="123",
            title="稳定标识",
            source_url="http://www.zhuanlan.zhihu.com/p/123/?from=old",
            author=AUTHOR,
            published_at=NOW,
            blocks=(Paragraph((Text("正文"),)),),
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            original = LocalArchive(root, markdown=False, html=True, media_download=False).archive(
                article
            )
            updated = LocalArchive(root, media_download=False).archive(
                replace(article, source_url="https://zhuanlan.zhihu.com/p/123", title="新标题")
            )
            self.assertEqual(original.entry_directory, updated.entry_directory)
            self.assertEqual(original.html_path.stem, updated.markdown_path.stem)

    def test_existing_unidentified_directories_are_not_overwritten(self):
        article = Article(
            id="1",
            title="同名标题",
            source_url="https://zhuanlan.zhihu.com/p/1",
            author=AUTHOR,
            published_at=NOW,
            blocks=(Paragraph((Text("归档正文"),)),),
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            occupied = (root / article.title, root / f"{article.title}--article-1")
            for directory in occupied:
                directory.mkdir()
                (directory / f"{article.title}.md").write_text("用户已有文件", encoding="utf-8")

            sink = LocalArchive(root, media_download=False)
            receipt = sink.archive(article)
            repeated = sink.archive(article)

            self.assertNotIn(receipt.entry_directory, occupied)
            self.assertEqual(receipt.markdown_path, repeated.markdown_path)
            self.assertIn("归档正文", receipt.markdown_path.read_text(encoding="utf-8"))
            for directory in occupied:
                self.assertEqual(
                    "用户已有文件", (directory / f"{article.title}.md").read_text(encoding="utf-8")
                )

    def test_renaming_an_archive_preserves_its_directory_and_document_stem(self):
        article = Article(
            id="1",
            title="原始标题",
            source_url="https://zhuanlan.zhihu.com/p/1",
            author=AUTHOR,
            published_at=NOW,
            blocks=(Paragraph((Text("原始正文"),)),),
        )
        column = ColumnArchive(
            column=Column("test", "原始标题", "https://www.zhihu.com/column/test", "", AUTHOR, 1),
            articles=(article,),
            archived_at=NOW,
        )
        renamed_article = replace(article, title="更新标题")
        renamed_column = replace(
            column,
            column=replace(column.column, title="更新标题"),
            articles=(renamed_article,),
        )
        for original_target, renamed_target in (
            (article, renamed_article),
            (column, renamed_column),
        ):
            for markdown, html in ((True, False), (False, True)):
                with self.subTest(target=type(original_target).__name__, markdown=markdown):
                    with tempfile.TemporaryDirectory() as temporary_directory:
                        root = Path(temporary_directory)
                        original = LocalArchive(
                            root, markdown=markdown, html=html, media_download=False
                        ).archive(original_target)
                        original_document = original.markdown_path or original.html_path
                        original_children = (
                            original.child_markdown_paths or original.child_html_paths
                        )
                        refreshed = LocalArchive(root, html=True, media_download=False).archive(
                            renamed_target
                        )

                        self.assertEqual(original.entry_directory, refreshed.entry_directory)
                        self.assertEqual(original_document.stem, refreshed.markdown_path.stem)
                        self.assertEqual(original_document.stem, refreshed.html_path.stem)
                        self.assertEqual(1, len(list(root.iterdir())))
                        self.assertIn(
                            "更新标题", refreshed.markdown_path.read_text(encoding="utf-8")
                        )
                        self.assertIn("更新标题", refreshed.html_path.read_text(encoding="utf-8"))
                        if original_children:
                            self.assertEqual(
                                original_children[0].stem, refreshed.child_markdown_paths[0].stem
                            )
                            self.assertEqual(
                                original_children[0].stem, refreshed.child_html_paths[0].stem
                            )
                            child = refreshed.child_markdown_paths[0].read_text(encoding="utf-8")
                            self.assertIn("../原始标题.md", child)

    def test_column_rearchive_preserves_article_paths_when_names_collide(self):
        first = Article(
            id="1",
            title="同名文章",
            source_url="https://zhuanlan.zhihu.com/p/1",
            author=AUTHOR,
            published_at=NOW,
            blocks=(Paragraph((Text("第一篇正文"),)),),
        )
        second = replace(
            first,
            id="2",
            source_url="https://zhuanlan.zhihu.com/p/2",
            blocks=(Paragraph((Text("第二篇正文"),)),),
        )
        column = ColumnArchive(
            column=Column("test", "测试专栏", "https://www.zhihu.com/column/test", "", AUTHOR, 2),
            articles=(first, second),
            archived_at=NOW,
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            sink = LocalArchive(Path(temporary_directory), html=True, media_download=False)
            original = sink.archive(column)
            reordered = sink.archive(replace(column, articles=(second, first)))
            self.assertEqual(
                tuple(reversed(original.child_markdown_paths)), reordered.child_markdown_paths
            )
            self.assertEqual(tuple(reversed(original.child_html_paths)), reordered.child_html_paths)

            remaining = sink.archive(replace(column, articles=(second,)))
            self.assertEqual((original.child_markdown_paths[1],), remaining.child_markdown_paths)
            self.assertEqual((original.child_html_paths[1],), remaining.child_html_paths)
            self.assertIn(
                "第一篇正文", original.child_markdown_paths[0].read_text(encoding="utf-8")
            )
            self.assertIn(
                "第二篇正文", remaining.child_markdown_paths[0].read_text(encoding="utf-8")
            )
            self.assertEqual(2, len(list(original.child_markdown_paths[0].parent.glob("*.md"))))
            self.assertIn(
                "内容/同名文章--article-2.md", remaining.markdown_path.read_text(encoding="utf-8")
            )

    def test_only_whole_columns_create_the_content_directory(self):
        column_ref = ColumnRef(
            token="machinelearningpku",
            title="机器学习",
            url="https://www.zhihu.com/column/machinelearningpku",
        )
        first = Article(
            id="1",
            title="同名:文章",
            source_url="https://zhuanlan.zhihu.com/p/1",
            author=AUTHOR,
            published_at=datetime(2025, 1, 1, tzinfo=UTC),
            blocks=(Paragraph((Text("第一篇正文"),)),),
            columns=(column_ref,),
        )
        second = Article(
            id="2",
            title="同名/文章",
            source_url="https://zhuanlan.zhihu.com/p/2",
            author=AUTHOR,
            published_at=datetime(2024, 1, 1, tzinfo=UTC),
            blocks=(Paragraph((Text("第二篇正文"),)),),
            columns=(column_ref,),
        )
        archive = ColumnArchive(
            column=Column(
                token=column_ref.token,
                title=column_ref.title,
                source_url=column_ref.url,
                description="专栏说明",
                author=AUTHOR,
                item_count=81,
            ),
            articles=(first, second),
            archived_at=NOW,
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            receipt = LocalArchive(root, media_download=False).archive(archive)

            self.assertEqual(root / "机器学习", receipt.entry_directory)
            self.assertEqual(root / "机器学习" / "机器学习.md", receipt.markdown_path)
            self.assertIsNone(receipt.html_path)
            self.assertFalse((root / "zhihu.db").exists())
            self.assertEqual(2, len(receipt.child_markdown_paths))
            self.assertEqual(0, len(receipt.child_html_paths))
            self.assertTrue(
                all(path.parent.name == "内容" for path in receipt.child_markdown_paths)
            )
            self.assertEqual(
                len({path.name.casefold() for path in receipt.child_markdown_paths}),
                2,
            )
            self.assertFalse((root / "机器学习" / "assets").exists())
            self.assertFalse((root / "机器学习" / "media").exists())

            catalog = receipt.markdown_path.read_text(encoding="utf-8")
            first_page = receipt.child_markdown_paths[0].read_text(encoding="utf-8")
            self.assertIn("本栏目共 81 篇", catalog)
            self.assertIn("内容/同名_文章.md", catalog)
            self.assertNotIn("HTML", catalog)
            self.assertIn("本次归档自", first_page)
            self.assertIn("本栏目共 81 篇", first_page)
            self.assertIn("查看完整目录", first_page)
            self.assertIn("下一篇", first_page)
            self.assertNotIn("第一篇正文", catalog)

    def test_standalone_article_has_no_content_directory_and_uses_local_media(self):
        source_url = "https://pic.example/original.png"
        article = Article(
            id="3",
            title="单篇文章",
            source_url="https://zhuanlan.zhihu.com/p/3",
            author=AUTHOR,
            published_at=NOW,
            blocks=(
                MediaBlock(
                    MediaAsset(
                        id="image",
                        kind=MediaKind.IMAGE,
                        renditions=(MediaRendition(source_url),),
                        alt_text="图片",
                    )
                ),
            ),
        )
        downloader = FakeDownloader()

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            receipt = LocalArchive(root, downloader=downloader).archive(article)

            self.assertFalse((receipt.entry_directory / "内容").exists())
            self.assertEqual(1, len(downloader.calls))
            self.assertTrue((receipt.entry_directory / "media").is_dir())
            markdown = receipt.markdown_path.read_text(encoding="utf-8")
            self.assertIn("](media/", markdown)
            self.assertNotIn(source_url, markdown.split("##", 1)[-1])
            self.assertTrue(receipt.media_downloads[0].destination.is_file())

    def test_column_links_percent_encode_url_significant_filename_characters(self):
        column_ref = ColumnRef(
            token="safe-links",
            title="链接测试",
            url="https://www.zhihu.com/column/safe-links",
        )
        article = Article(
            id="special",
            title="C# 100% (入门)",
            source_url="https://zhuanlan.zhihu.com/p/100",
            author=AUTHOR,
            published_at=NOW,
            blocks=(Paragraph((Text("正文"),)),),
            columns=(column_ref,),
        )
        archive = ColumnArchive(
            column=Column(
                token=column_ref.token,
                title=column_ref.title,
                source_url=column_ref.url,
                description="",
                author=AUTHOR,
                item_count=1,
            ),
            articles=(article,),
            archived_at=NOW,
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            receipt = LocalArchive(
                Path(temporary_directory), html=True, media_download=False
            ).archive(archive)
            markdown = receipt.markdown_path.read_text(encoding="utf-8")
            rendered_html = receipt.html_path.read_text(encoding="utf-8")
            child_markdown = receipt.child_markdown_paths[0]
            child_html = receipt.child_html_paths[0]

        expected_stem = "C%23%20100%25%20%28入门%29"
        self.assertEqual(child_markdown.name, "C# 100% (入门).md")
        self.assertEqual(child_html.name, "C# 100% (入门).html")
        self.assertIn(f"内容/{expected_stem}.md", markdown)
        self.assertIn(f'内容/{expected_stem}.html"', rendered_html)

    def test_settings_proxy_is_used_for_media_downloads(self):
        source_url = "https://pic.example/proxied.png"
        article = Article(
            id="proxied",
            title="代理媒体",
            source_url="https://zhuanlan.zhihu.com/p/5",
            author=AUTHOR,
            published_at=NOW,
            blocks=(
                MediaBlock(
                    MediaAsset(
                        id="proxied-image",
                        kind=MediaKind.IMAGE,
                        renditions=(MediaRendition(source_url),),
                    )
                ),
            ),
        )
        proxy = "http://127.0.0.1:7890"

        def fake_download(
            source,
            destination,
            *,
            proxy=None,
            timeout=30.0,
            max_retries=0,
            expected_size=None,
        ):
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"media")
            return MediaDownloadReceipt(source, destination, 0, 5)

        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            patch("zhihu_scraper.archive.download_media", side_effect=fake_download) as download,
        ):
            settings = ArchiveSettings(
                output_dir=Path(temporary_directory),
                proxy=proxy,
            )
            LocalArchive.from_settings(settings).archive(article)

        self.assertEqual(download.call_count, 1)
        self.assertEqual(
            download.call_args.kwargs,
            {
                "proxy": proxy,
                "timeout": 30.0,
                "max_retries": 3,
            },
        )

    def test_archive_requires_at_least_one_readable_output(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaisesRegex(ValueError, "Markdown 或 HTML"):
                LocalArchive(
                    Path(temporary_directory),
                    markdown=False,
                    html=False,
                    media_download=False,
                )

    def test_rearchive_without_optional_fetches_reflects_only_the_current_run(self):
        source_url = "https://pic.example/preserved.png"
        initial = Article(
            id="preserved",
            title="保留本地归档",
            source_url="https://zhuanlan.zhihu.com/p/preserved",
            author=AUTHOR,
            published_at=NOW,
            blocks=(
                MediaBlock(
                    MediaAsset(
                        id="preserved-image",
                        kind=MediaKind.IMAGE,
                        renditions=(MediaRendition(source_url),),
                        alt_text="已下载图片",
                    )
                ),
            ),
            comments=CommentThread(
                comments=(
                    Comment(
                        id="preserved-comment",
                        author=AUTHOR,
                        blocks=(Paragraph((Text("已抓评论不能丢"),)),),
                        created_at=NOW,
                        like_count=1,
                    ),
                ),
                order="api",
                roots_complete=True,
            ),
        )
        refreshed = Article(
            id=initial.id,
            title=initial.title,
            source_url=initial.source_url,
            author=initial.author,
            published_at=initial.published_at,
            blocks=initial.blocks,
            comments=None,
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first = LocalArchive(root, html=True, downloader=FakeDownloader()).archive(initial)
            second = LocalArchive(root, html=True, media_download=False).archive(refreshed)
            markdown = second.markdown_path.read_text(encoding="utf-8")
            rendered_html = second.html_path.read_text(encoding="utf-8")
            self.assertTrue(first.media_downloads[0].destination.is_file())

        self.assertNotIn("已抓评论不能丢", markdown)
        self.assertNotIn("已抓评论不能丢", rendered_html)
        self.assertIn(source_url, markdown)
        self.assertIn(source_url, rendered_html)

    def test_answer_and_its_question_with_the_same_title_do_not_overwrite_each_other(self):
        title = "数据挖掘、机器学习、深度学习这些概念有区别吗？"
        question_url = "https://www.zhihu.com/question/30557267"
        answer = Answer(
            id="48623150",
            question=QuestionRef(
                id="30557267",
                title=title,
                url=question_url,
            ),
            source_url=f"{question_url}/answer/48623150",
            author=AUTHOR,
            published_at=NOW,
            blocks=(Paragraph((Text("单个回答正文"),)),),
        )
        question = QuestionArchive(
            question=Question(
                id="30557267",
                title=title,
                source_url=question_url,
                detail=(Paragraph((Text("问题详情"),)),),
                answer_count=1,
            ),
            answers=(answer,),
            archived_at=NOW,
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            local_archive = LocalArchive(root, media_download=False)
            answer_receipt = local_archive.archive(answer)
            question_receipt = local_archive.archive(question)

            self.assertNotEqual(
                answer_receipt.entry_directory,
                question_receipt.entry_directory,
            )
            self.assertEqual(root / title, answer_receipt.entry_directory)
            self.assertEqual(
                root / f"{title}--question-30557267",
                question_receipt.entry_directory,
            )
            self.assertIn(
                "单个回答正文",
                answer_receipt.markdown_path.read_text(encoding="utf-8"),
            )
            self.assertIn(
                "问题详情",
                question_receipt.markdown_path.read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
