import io
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import unquote, urljoin

from bs4 import BeautifulSoup
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Link

from zhihu_scraper.archive import LocalArchive
from zhihu_scraper.domain import Article, Author, Column, ColumnArchive, Paragraph, Text
from zhihu_scraper.pdf_export import PdfDocument, PdfExportError, PlaywrightPdfBrowser, export_pdfs
from zhihu_scraper.platform import OperatingSystem, RuntimePlatform
from zhihu_scraper.settings import ArchiveSettings


class RecordingPdfBrowser:
    def __init__(self, fail_title=None):
        self.documents = []
        self.closed = False
        self.fail_title = fail_title

    def render(self, html_path, *, resource_root):
        markup = html_path.read_text(encoding="utf-8")
        self.documents.append((html_path, markup))
        if (
            self.fail_title is not None
            and BeautifulSoup(markup, "html.parser").title.string == self.fail_title
        ):
            raise RuntimeError("模拟指定文档导出失败")
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        for link in BeautifulSoup(markup, "html.parser").find_all("a", href=True):
            writer.add_annotation(
                0, Link(rect=(0, 0, 100, 20), url=urljoin(html_path.as_uri(), str(link["href"])))
            )
        output = io.BytesIO()
        writer.write(output)
        return output.getvalue()

    def close(self):
        self.closed = True


class PdfArchiveTests(unittest.TestCase):
    def test_a_user_pdf_that_cites_zhihu_is_not_claimed_as_an_archive(self):
        article = Article(
            id="1",
            title="已有资料",
            source_url="https://zhuanlan.zhihu.com/p/1",
            author=Author("author", "作者"),
            published_at=None,
            blocks=(Paragraph((Text("正文"),)),),
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            user_directory = root / article.title
            user_directory.mkdir()
            user_pdf = user_directory / f"{article.title}.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=595, height=842)
            writer.add_annotation(0, Link(rect=(0, 0, 100, 20), url=article.source_url))
            writer.write(user_pdf)
            original = user_pdf.read_bytes()
            receipt = LocalArchive(
                root,
                markdown=False,
                pdf=True,
                media_download=False,
                pdf_exporter=partial(export_pdfs, browser_factory=RecordingPdfBrowser),
            ).archive(article)
            self.assertNotEqual(user_directory, receipt.entry_directory)
            self.assertEqual(original, user_pdf.read_bytes())

    def test_failing_a_child_pdf_does_not_publish_any_new_column_catalog(self):
        article = Article(
            id="1",
            title="第一篇",
            source_url="https://zhuanlan.zhihu.com/p/1",
            author=Author("author", "作者"),
            published_at=None,
            blocks=(Paragraph((Text("正文"),)),),
        )
        column = ColumnArchive(
            column=Column("test", "测试专栏", "https://www.zhihu.com/column/test", "", None, 1),
            articles=(article,),
            archived_at=datetime(2026, 9, 5, tzinfo=UTC),
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first = LocalArchive(
                root,
                html=True,
                pdf=True,
                media_download=False,
                pdf_exporter=partial(export_pdfs, browser_factory=RecordingPdfBrowser),
            ).archive(column)
            catalogs = (first.markdown_path, first.html_path, first.pdf_path)
            before = [path.read_bytes() for path in catalogs]
            failure = RecordingPdfBrowser(fail_title="第二篇")
            changed = replace(
                column,
                articles=(
                    article,
                    replace(
                        article, id="2", title="第二篇", source_url="https://zhuanlan.zhihu.com/p/2"
                    ),
                ),
            )
            with self.assertRaises(PdfExportError):
                LocalArchive(
                    root,
                    html=True,
                    pdf=True,
                    media_download=False,
                    pdf_exporter=partial(export_pdfs, browser_factory=lambda: failure),
                ).archive(changed)
            self.assertEqual(before, [path.read_bytes() for path in catalogs])
            self.assertFalse(list(root.rglob(".pdf-*")))
            self.assertTrue(failure.closed)

    def test_failed_export_keeps_the_original_pdf_and_removes_temporary_files(self):
        article = Article(
            id="1",
            title="失败测试",
            source_url="https://zhuanlan.zhihu.com/p/1",
            author=Author("author", "作者"),
            published_at=None,
            blocks=(Paragraph((Text("正文"),)),),
        )
        for failure in (RuntimeError("printing failed"), b"not a PDF"):
            with self.subTest(failure=type(failure).__name__):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    root = Path(temporary_directory)
                    original_browser = RecordingPdfBrowser()
                    original = LocalArchive(
                        root,
                        markdown=False,
                        pdf=True,
                        media_download=False,
                        pdf_exporter=partial(export_pdfs, browser_factory=lambda: original_browser),
                    ).archive(article)
                    old_pdf = original.pdf_path.read_bytes()
                    browser = RecordingPdfBrowser()
                    with patch.object(
                        browser,
                        "render",
                        side_effect=failure if isinstance(failure, Exception) else None,
                        return_value=failure,
                    ):
                        with self.assertRaises(PdfExportError):
                            LocalArchive(
                                root,
                                markdown=False,
                                pdf=True,
                                media_download=False,
                                pdf_exporter=partial(export_pdfs, browser_factory=lambda: browser),
                            ).archive(article)
                    self.assertTrue(browser.closed)
                    self.assertEqual(old_pdf, original.pdf_path.read_bytes())
                    self.assertEqual([original.pdf_path], list(original.entry_directory.iterdir()))

    def test_remote_resources_are_removed_and_local_images_stay_inside_the_archive(self):
        browser = RecordingPdfBrowser()
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            image = root / "media" / "image.png"
            image.parent.mkdir()
            image.write_bytes(b"test image")
            html = """<html><head><link rel="stylesheet" href="https://remote.example/style.css"></head>
            <body><img src="https://remote.example/picture.png"><img src="media/image.png">
            <img src="../../private.png"><a href="https://www.zhihu.com/question/1">原文</a></body></html>"""
            export_pdfs(
                (PdfDocument(root / "test.pdf", html),),
                resource_root=root,
                browser_factory=lambda: browser,
            )
            prepared = browser.documents[0][1]
            soup = BeautifulSoup(prepared, "html.parser")
            self.assertEqual(
                [image.resolve().as_uri()], [node["src"] for node in soup.find_all("img")]
            )
            self.assertFalse(soup.find_all("link"))
            self.assertIn("Content-Security-Policy", prepared)
            self.assertIn("https://www.zhihu.com/question/1", prepared)

    def test_browser_falls_back_to_managed_chromium_blocks_network_and_closes_resources(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            executable = root / "chrome"
            executable.touch()
            runtime = RuntimePlatform(OperatingSystem.LINUX, root, (executable,))
            manager = MagicMock()
            playwright = manager.start.return_value
            browser = MagicMock()
            context = browser.new_context.return_value
            page = context.new_page.return_value
            page.pdf.return_value = b"%PDF-1.7\n%%EOF"
            playwright.chromium.launch.side_effect = [RuntimeError("Chrome unavailable"), browser]
            adapter = PlaywrightPdfBrowser(runtime_platform=runtime)
            with patch("playwright.sync_api.sync_playwright", return_value=manager):
                adapter.render(root / "document.html", resource_root=root)
                route_handler = context.route.call_args.args[1]
                for url in (
                    "https://remote.example/",
                    "http://127.0.0.1/",
                    "wss://remote.example/",
                ):
                    route = MagicMock()
                    route.request.url = url
                    route_handler(route)
                    route.abort.assert_called_once()
                    route.continue_.assert_not_called()
                page_handler = page.route.call_args.args[1]
                outside = MagicMock()
                outside.request.url = (root.parent / "outside.html").as_uri()
                page_handler(outside)
                outside.abort.assert_called_once()
                adapter.close()
            self.assertEqual(2, playwright.chromium.launch.call_count)
            self.assertIn("executable_path", playwright.chromium.launch.call_args_list[0].kwargs)
            self.assertNotIn("executable_path", playwright.chromium.launch.call_args_list[1].kwargs)
            self.assertTrue(browser.new_context.call_args.kwargs["offline"])
            self.assertFalse(browser.new_context.call_args.kwargs["java_script_enabled"])
            self.assertEqual("block", browser.new_context.call_args.kwargs["service_workers"])
            page.close.assert_called_once()
            context.close.assert_called_once()
            browser.close.assert_called_once()
            playwright.stop.assert_called_once()

    def test_pdf_only_column_has_portable_navigation_and_stable_names_after_rename(self):
        article = Article(
            id="1",
            title="第一篇",
            source_url="https://zhuanlan.zhihu.com/p/1",
            author=Author("author", "作者"),
            published_at=None,
            blocks=(Paragraph((Text("中文正文"),)),),
        )
        column = ColumnArchive(
            column=Column("test", "测试专栏", "https://www.zhihu.com/column/test", "", None, 2),
            articles=(
                article,
                replace(
                    article, id="2", title="第二篇", source_url="https://zhuanlan.zhihu.com/p/2"
                ),
            ),
            archived_at=datetime(2026, 9, 5, tzinfo=UTC),
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            browser = RecordingPdfBrowser()
            sink = LocalArchive(
                Path(temporary_directory),
                markdown=False,
                pdf=True,
                media_download=False,
                pdf_exporter=partial(export_pdfs, browser_factory=lambda: browser),
            )
            first = sink.archive(column)
            self.assertEqual(2, len(first.child_pdf_paths))
            self.assertIsNotNone(first.pdf_path)
            self.assertEqual(3, len(browser.documents))
            with first.pdf_path.open("rb") as source:
                actions = [
                    annotation.get_object()["/A"]["/URI"]
                    for annotation in PdfReader(source).pages[0]["/Annots"]
                ]
                self.assertIn("内容/第一篇.pdf", [unquote(uri) for uri in actions])
                self.assertIn("内容/第二篇.pdf", [unquote(uri) for uri in actions])
            with first.child_pdf_paths[0].open("rb") as source:
                actions = [
                    annotation.get_object()["/A"]["/URI"]
                    for annotation in PdfReader(source).pages[0]["/Annots"]
                ]
                self.assertIn("../测试专栏.pdf", [unquote(uri) for uri in actions])
                self.assertIn("第二篇.pdf", [unquote(uri) for uri in actions])
            refreshed = sink.archive(
                replace(column, column=replace(column.column, title="专栏新名"))
            )
            self.assertEqual(first.pdf_path, refreshed.pdf_path)
            self.assertEqual(first.child_pdf_paths, refreshed.child_pdf_paths)
            self.assertFalse(list(first.entry_directory.rglob("*.html")))
            self.assertFalse((first.entry_directory / "assets").exists())

    def test_pdf_only_archive_uses_temporary_html_and_closes_its_browser(self):
        article = Article(
            id="1",
            title="PDF 归档",
            source_url="https://zhuanlan.zhihu.com/p/1",
            author=Author("author", "作者"),
            published_at=None,
            blocks=(Paragraph((Text("中文正文"),)),),
        )
        browser = RecordingPdfBrowser()
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings = ArchiveSettings(
                output_dir=Path(temporary_directory),
                markdown=False,
                html=False,
                pdf=True,
                media_download=False,
            )
            receipt = LocalArchive.from_settings(
                settings,
                pdf_exporter=partial(export_pdfs, browser_factory=lambda: browser),
            ).archive(article)

            self.assertIsNone(receipt.markdown_path)
            self.assertIsNone(receipt.html_path)
            self.assertTrue(receipt.pdf_path.read_bytes().startswith(b"%PDF-"))
            self.assertEqual([receipt.pdf_path], list(receipt.entry_directory.iterdir()))
            self.assertTrue(browser.closed)
            self.assertIn("中文正文", browser.documents[0][1])
            self.assertIn("<style", browser.documents[0][1])
            self.assertFalse(browser.documents[0][0].exists())
