import io
import tempfile
import unittest
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from zhihu_scraper.archive import LocalArchive
from zhihu_scraper.assets import (
    MediaArchiveRole,
    PrimaryVideoDownloadError,
    archive_assets,
)
from zhihu_scraper.domain import (
    Answer,
    Article,
    Author,
    Column,
    ColumnArchive,
    Comment,
    CommentThread,
    ListBlock,
    MediaAsset,
    MediaBlock,
    MediaKind,
    MediaRendition,
    Paragraph,
    Question,
    QuestionArchive,
    QuestionRef,
    Quote,
    Text,
    Video,
)
from zhihu_scraper.media import MediaDownloadError, MediaDownloadReceipt, download_media

NOW = datetime(2026, 7, 27, tzinfo=UTC)
AUTHOR = Author(id="writer", name="作者")


class RecordingDownloader:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Path]] = []

    def __call__(
        self, source_url: str, destination: Path, *, expected_size=None
    ) -> MediaDownloadReceipt:
        self.calls.append((source_url, destination))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source_url.encode())
        return MediaDownloadReceipt(
            source_url=source_url,
            destination=destination,
            resumed_from=0,
            bytes_total=destination.stat().st_size,
        )


def image(
    asset_id: str,
    source_url: str,
    *,
    alternate_url: str | None = None,
    kind: MediaKind = MediaKind.IMAGE,
) -> MediaAsset:
    renditions = [
        MediaRendition(source_url, mime_type="image/gif" if kind is MediaKind.ANIMATION else None)
    ]
    if alternate_url is not None:
        renditions.append(MediaRendition(alternate_url, width=2000, height=1200))
    return MediaAsset(id=asset_id, kind=kind, renditions=tuple(renditions))


class AssetPipelineTests(unittest.TestCase):
    def test_known_asset_length_repairs_a_truncated_cached_file(self):
        from unittest.mock import patch

        source_url = "https://pic1.zhimg.com/sized.png"
        asset = MediaAsset("sized", MediaKind.IMAGE, (MediaRendition(source_url, size_bytes=5),))
        article = Article(
            "1", "带尺寸图片", "https://zhuanlan.zhihu.com/p/1", AUTHOR, NOW, (MediaBlock(asset),)
        )
        requests = []

        @contextmanager
        def transport(request):
            requests.append(request)
            yield SimpleNamespace(
                status=200, headers={"Content-Length": "5"}, read=io.BytesIO(b"image").read
            )

        def downloader(url, destination, *, expected_size=None):
            return download_media(
                url, destination, transport=transport, expected_size=expected_size
            )

        with (
            tempfile.TemporaryDirectory() as directory,
            patch("zhihu_scraper.media._resolve_media_host"),
        ):
            media = Path(directory) / "media"
            initial = archive_assets(article, media, downloader=downloader)
            destination = initial.downloads[0].destination
            destination.write_bytes(b"x")
            archive_assets(article, media, downloader=downloader)
            self.assertEqual(b"image", destination.read_bytes())
            self.assertEqual(2, len(requests))

    def test_changed_cover_source_downloads_new_bytes_for_the_same_article(self):
        old_url = "https://pic1.zhimg.com/old.jpg"
        for new_url in (
            "https://pic1.zhimg.com/new.jpg",
            "https://pic2.zhimg.com/old.jpg",
            "https://pic1.zhimg.com/old.jpg?width=100",
        ):
            with self.subTest(new_url=new_url):
                article = Article(
                    id="updated-cover",
                    title="更新封面",
                    source_url="https://zhuanlan.zhihu.com/p/updated-cover",
                    author=AUTHOR,
                    published_at=NOW,
                    blocks=(),
                    cover_url=old_url,
                )
                requested_urls = []

                @contextmanager
                def transport(request):
                    requested_urls.append(request.full_url)
                    body = b"old cover" if request.full_url == old_url else b"new cover"
                    with io.BytesIO(body) as response_body:
                        yield SimpleNamespace(
                            status=200,
                            headers={"Content-Length": str(len(body))},
                            read=response_body.read,
                        )

                def downloader(source_url, destination):
                    return download_media(source_url, destination, transport=transport)

                with tempfile.TemporaryDirectory() as temporary_directory:
                    root = Path(temporary_directory)
                    old_result = archive_assets(article, root / "media", downloader=downloader)
                    new_result = archive_assets(
                        replace(article, cover_url=new_url), root / "media", downloader=downloader
                    )

                    self.assertEqual(
                        (root / new_result.source_paths[new_url]).read_bytes(), b"new cover"
                    )
                    self.assertEqual(
                        (root / old_result.source_paths[old_url]).read_bytes(), b"old cover"
                    )
                    self.assertEqual(requested_urls, [old_url, new_url])
                    self.assertEqual(new_result.downloads[0].source_url, new_url)

    def test_signed_cover_refresh_reuses_a_completed_download(self):
        old_url = "https://pic1.zhimg.com/cover.jpg?pkey=old&expiration=1"
        new_url = "https://pic1.zhimg.com/cover.jpg?pkey=new&expiration=2"
        article = Article(
            id="signed-cover",
            title="签名更新",
            source_url="https://zhuanlan.zhihu.com/p/signed-cover",
            author=AUTHOR,
            published_at=NOW,
            blocks=(),
            cover_url=old_url,
        )
        requested_urls = []

        @contextmanager
        def transport(request):
            requested_urls.append(request.full_url)
            with io.BytesIO(b"cover") as response_body:
                yield SimpleNamespace(
                    status=200, headers={"Content-Length": "5"}, read=response_body.read
                )

        def downloader(source_url, destination):
            return download_media(source_url, destination, transport=transport)

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first = archive_assets(article, root / "media", downloader=downloader)
            refreshed = archive_assets(
                replace(article, cover_url=new_url), root / "media", downloader=downloader
            )

            self.assertEqual((root / refreshed.source_paths[new_url]).read_bytes(), b"cover")
            self.assertEqual(first.source_paths[old_url], refreshed.source_paths[new_url])
            self.assertEqual(requested_urls, [old_url])

    def test_signed_refresh_resumes_partial_media_but_changed_path_starts_new_download(self):
        old_url = "https://pic1.zhimg.com/old.jpg?pkey=old&expiration=1"
        for new_url, should_resume in (
            ("https://pic1.zhimg.com/old.jpg?pkey=new&expiration=2", True),
            ("https://pic1.zhimg.com/new.jpg?pkey=new&expiration=2", False),
        ):
            with self.subTest(new_url=new_url):
                article = Article(
                    id="partial-cover",
                    title="续传封面",
                    source_url="https://zhuanlan.zhihu.com/p/partial-cover",
                    author=AUTHOR,
                    published_at=NOW,
                    blocks=(),
                    cover_url=old_url,
                )
                requests = []

                @contextmanager
                def transport(request):
                    requests.append(request)
                    if len(requests) == 1:
                        chunks = iter((b"old",))

                        def interrupted_read(_size):
                            try:
                                return next(chunks)
                            except StopIteration:
                                raise ConnectionResetError("interrupted") from None

                        yield SimpleNamespace(
                            status=200,
                            headers={"Content-Length": "9", "ETag": '"cover-v1"'},
                            read=interrupted_read,
                        )
                    else:
                        body = b" cover" if should_resume else b"new cover"
                        headers = {"Content-Length": str(len(body))}
                        if should_resume:
                            headers["Content-Range"] = "bytes 3-8/9"
                            headers["ETag"] = '"cover-v1"'
                        with io.BytesIO(body) as response_body:
                            yield SimpleNamespace(
                                status=206 if should_resume else 200,
                                headers=headers,
                                read=response_body.read,
                            )

                def downloader(source_url, destination):
                    return download_media(
                        source_url, destination, transport=transport, max_retries=0
                    )

                with tempfile.TemporaryDirectory() as temporary_directory:
                    root = Path(temporary_directory)
                    interrupted = archive_assets(article, root / "media", downloader=downloader)
                    self.assertEqual(len(interrupted.failures), 1)
                    refreshed = archive_assets(
                        replace(article, cover_url=new_url), root / "media", downloader=downloader
                    )

                    self.assertEqual(
                        requests[1].get_header("Range"), "bytes=3-" if should_resume else None
                    )
                    self.assertEqual(refreshed.downloads[0].resumed_from, 3 if should_resume else 0)
                    self.assertEqual(
                        (root / refreshed.source_paths[new_url]).read_bytes(),
                        b"old cover" if should_resume else b"new cover",
                    )

    def test_one_failed_image_keeps_remote_url_and_does_not_block_other_outputs(self):
        failed_url = "https://pic.example/missing.png"
        downloaded_url = "https://pic.example/available.png"
        article = Article(
            id="partial-media",
            title="部分媒体下载失败",
            source_url="https://zhuanlan.zhihu.com/p/partial-media",
            author=AUTHOR,
            published_at=NOW,
            blocks=(
                MediaBlock(image("missing-image", failed_url)),
                MediaBlock(image("available-image", downloaded_url)),
            ),
        )

        class OneFailureDownloader(RecordingDownloader):
            def __call__(
                self,
                source_url: str,
                destination: Path,
            ) -> MediaDownloadReceipt:
                self.calls.append((source_url, destination))
                if source_url == failed_url:
                    raise MediaDownloadError("unexpected HTTP status 404")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(source_url.encode())
                return MediaDownloadReceipt(
                    source_url=source_url,
                    destination=destination,
                    resumed_from=0,
                    bytes_total=destination.stat().st_size,
                )

        with tempfile.TemporaryDirectory() as temporary_directory:
            receipt = LocalArchive(
                Path(temporary_directory),
                html=True,
                downloader=OneFailureDownloader(),
            ).archive(article)

            self.assertTrue(receipt.markdown_path.is_file())
            self.assertTrue(receipt.html_path.is_file())
            markdown = receipt.markdown_path.read_text(encoding="utf-8")
            rendered_html = receipt.html_path.read_text(encoding="utf-8")
            self.assertIn(failed_url, markdown)
            self.assertNotIn(downloaded_url, markdown)
            self.assertNotIn(f'<img src="{failed_url}"', rendered_html)
            self.assertIn(f'href="{failed_url}"', rendered_html)
            self.assertEqual(1, len(receipt.media_downloads))
            self.assertEqual(1, len(receipt.media_failures))
            failure = receipt.media_failures[0]
            self.assertEqual("missing-image", failure.asset_id)
            self.assertEqual(failed_url, failure.source_url)
            self.assertEqual(MediaArchiveRole.CONTENT, failure.role)
            self.assertIn("404", failure.display_message)

    def test_private_media_failure_is_never_embedded_as_an_automatic_browser_request(self):
        private_url = "http://127.0.0.1:8080/private.png"
        article = Article(
            id="private-media",
            title="私网媒体防护",
            source_url="https://zhuanlan.zhihu.com/p/private-media",
            author=AUTHOR,
            published_at=NOW,
            blocks=(MediaBlock(image("private-image", private_url)),),
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            receipt = LocalArchive(Path(temporary_directory), html=True).archive(article)
            markdown = receipt.markdown_path.read_text(encoding="utf-8")
            rendered_html = receipt.html_path.read_text(encoding="utf-8")

        self.assertEqual(1, len(receipt.media_failures))
        self.assertIn("远程媒体未下载", markdown)
        self.assertNotIn("![", markdown)
        self.assertIn(f'href="{private_url}"', rendered_html)
        self.assertNotIn(f'src="{private_url}"', rendered_html)

    def test_failed_animation_and_cover_are_reported_without_blocking_other_assets(self):
        animation_url = "https://pic.example/missing.gif"
        image_url = "https://pic.example/available.webp"
        cover_url = "https://pic.example/missing-cover.jpg"
        article = Article(
            id="mixed-failures",
            title="动图和封面失败",
            source_url="https://zhuanlan.zhihu.com/p/mixed-failures",
            author=AUTHOR,
            published_at=NOW,
            blocks=(
                MediaBlock(
                    image(
                        "missing-animation",
                        animation_url,
                        kind=MediaKind.ANIMATION,
                    )
                ),
                MediaBlock(image("available-image", image_url)),
            ),
            cover_url=cover_url,
        )

        class MixedDownloader(RecordingDownloader):
            def __call__(
                self,
                source_url: str,
                destination: Path,
            ) -> MediaDownloadReceipt:
                if source_url in {animation_url, cover_url}:
                    self.calls.append((source_url, destination))
                    raise MediaDownloadError("temporary media failure")
                return super().__call__(source_url, destination)

        with tempfile.TemporaryDirectory() as temporary_directory:
            result = archive_assets(
                article,
                Path(temporary_directory) / "media",
                downloader=MixedDownloader(),
            )

        self.assertEqual(1, len(result.downloads))
        self.assertIn(image_url, result.source_paths)
        self.assertNotIn(animation_url, result.source_paths)
        self.assertNotIn(cover_url, result.source_paths)
        self.assertEqual(
            [MediaArchiveRole.CONTENT, MediaArchiveRole.COVER],
            [failure.role for failure in result.failures],
        )

    def test_one_failed_article_asset_does_not_block_a_whole_column_archive(self):
        failed_url = "https://pic.example/column-missing.png"
        downloaded_url = "https://pic.example/column-available.png"
        column = ColumnArchive(
            column=Column(
                token="resilient-column",
                title="完整专栏",
                source_url="https://www.zhihu.com/column/resilient-column",
                description="",
                author=AUTHOR,
                item_count=2,
            ),
            articles=(
                Article(
                    id="first",
                    title="坏图文章",
                    source_url="https://zhuanlan.zhihu.com/p/first",
                    author=AUTHOR,
                    published_at=NOW,
                    blocks=(MediaBlock(image("column-missing", failed_url)),),
                ),
                Article(
                    id="second",
                    title="好图文章",
                    source_url="https://zhuanlan.zhihu.com/p/second",
                    author=AUTHOR,
                    published_at=NOW,
                    blocks=(MediaBlock(image("column-available", downloaded_url)),),
                ),
            ),
            archived_at=NOW,
        )

        class ColumnDownloader(RecordingDownloader):
            def __call__(
                self,
                source_url: str,
                destination: Path,
            ) -> MediaDownloadReceipt:
                if source_url == failed_url:
                    self.calls.append((source_url, destination))
                    raise MediaDownloadError("unexpected HTTP status 404")
                return super().__call__(source_url, destination)

        with tempfile.TemporaryDirectory() as temporary_directory:
            receipt = LocalArchive(
                Path(temporary_directory),
                html=True,
                downloader=ColumnDownloader(),
            ).archive(column)

            self.assertTrue(receipt.markdown_path.is_file())
            self.assertTrue(receipt.html_path.is_file())
            self.assertEqual(2, len(receipt.child_markdown_paths))
            self.assertTrue(all(path.is_file() for path in receipt.child_markdown_paths))
            self.assertEqual(1, len(receipt.media_downloads))
            self.assertEqual(1, len(receipt.media_failures))
            failed_article = receipt.child_markdown_paths[0].read_text(encoding="utf-8")
            downloaded_article = receipt.child_markdown_paths[1].read_text(encoding="utf-8")
            self.assertIn(failed_url, failed_article)
            self.assertNotIn(downloaded_url, downloaded_article)

    def test_independent_video_main_file_failure_has_an_explicit_fatal_error(self):
        main_url = "https://video.example/unavailable.mp4"
        video = Video(
            id="required-video",
            title="主文件失败",
            source_url="https://www.zhihu.com/zvideo/required-video",
            author=AUTHOR,
            published_at=NOW,
            description=(),
            asset=MediaAsset(
                id="zvideo-required-video",
                kind=MediaKind.VIDEO,
                renditions=(MediaRendition(main_url, width=1920, height=1080),),
            ),
        )

        def unavailable(_source_url: str, _destination: Path) -> MediaDownloadReceipt:
            raise MediaDownloadError("temporary video failure")

        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            self.assertRaises(PrimaryVideoDownloadError) as raised,
        ):
            archive_assets(
                video,
                Path(temporary_directory) / "media",
                downloader=unavailable,
            )

        self.assertEqual(MediaArchiveRole.PRIMARY_VIDEO, raised.exception.failure.role)
        self.assertEqual(main_url, raised.exception.failure.source_url)
        self.assertIn("独立视频主文件", str(raised.exception))

    def test_recursively_archives_article_assets_and_deduplicates_asset_ids(self):
        original = "https://pic.example/original.png?source=zhihu"
        alternate = "https://pic.example/large.jpg"
        animation_url = "https://pic.example/demo?format=gif"
        duplicate = image("hero", "https://pic.example/duplicate.jpg")
        article = Article(
            id="1",
            title="文章",
            source_url="https://zhuanlan.zhihu.com/p/1",
            author=AUTHOR,
            published_at=NOW,
            blocks=(
                MediaBlock(image("hero", original, alternate_url=alternate)),
                Quote(
                    (
                        ListBlock(
                            ordered=False,
                            items=(
                                (
                                    MediaBlock(
                                        image(
                                            "animation",
                                            animation_url,
                                            kind=MediaKind.ANIMATION,
                                        )
                                    ),
                                ),
                            ),
                        ),
                    )
                ),
                MediaBlock(duplicate),
            ),
            comments=CommentThread(
                comments=(
                    Comment(
                        id="c1",
                        author=None,
                        blocks=(MediaBlock(image("comment-image", "https://pic.example/c.webp")),),
                        created_at=None,
                        like_count=0,
                    ),
                ),
                order="api",
            ),
        )
        downloader = RecordingDownloader()

        with tempfile.TemporaryDirectory() as temporary_directory:
            media_directory = Path(temporary_directory) / "entry" / "media"
            result = archive_assets(
                article,
                media_directory,
                downloader=downloader,
            )

            self.assertEqual(
                [original, animation_url, "https://pic.example/c.webp"],
                [source for source, _ in downloader.calls],
            )
            self.assertEqual(3, len(result.downloads))
            self.assertTrue(all(path.is_file() for _, path in downloader.calls))
            self.assertTrue(downloader.calls[0][1].name.endswith(".png"))
            self.assertTrue(downloader.calls[1][1].name.endswith(".gif"))
            self.assertTrue(downloader.calls[2][1].name.endswith(".webp"))
            self.assertEqual(result.source_paths[original], result.source_paths[alternate])
            self.assertNotIn("https://pic.example/duplicate.jpg", result.source_paths)
            self.assertTrue(
                all(
                    relative.startswith("media/") and "\\" not in relative and ".." not in relative
                    for relative in result.source_paths.values()
                )
            )

    def test_video_uses_largest_known_resolution_and_archives_cover_and_description(self):
        low = MediaRendition("https://video.example/low.mp4", width=640, height=360)
        unknown = MediaRendition(
            "https://video.example/unknown.mp4",
            bitrate=99_000_000,
        )
        high = MediaRendition(
            "https://video.example/high",
            mime_type="video/mp4",
            width=1920,
            height=1080,
        )
        video = Video(
            id="1666569497233207296",
            title="训练方案",
            source_url="https://www.zhihu.com/zvideo/1666569497233207296",
            author=AUTHOR,
            published_at=NOW,
            description=(MediaBlock(image("description", "https://pic.example/description.jpg")),),
            asset=MediaAsset(
                id="zvideo-1666569497233207296",
                kind=MediaKind.VIDEO,
                renditions=(low, unknown, high),
            ),
            cover_url="https://pic.example/cover.avif",
        )
        downloader = RecordingDownloader()

        with tempfile.TemporaryDirectory() as temporary_directory:
            result = archive_assets(
                video,
                Path(temporary_directory) / "media",
                downloader=downloader,
            )

        self.assertEqual(
            [
                "https://video.example/high",
                "https://pic.example/description.jpg",
                "https://pic.example/cover.avif",
            ],
            [source for source, _ in downloader.calls],
        )
        self.assertTrue(downloader.calls[0][1].name.endswith(".mp4"))
        self.assertEqual(
            result.source_paths["https://video.example/low.mp4"],
            result.source_paths["https://video.example/high"],
        )

    def test_video_tie_prefers_bitrate_and_refreshing_signed_url_keeps_resume_filename(self):
        lower_bitrate = MediaRendition(
            "https://video.example/FHD/movie.mp4?pkey=old-low",
            width=1920,
            height=1080,
            bitrate=300,
            size_bytes=30_000,
        )
        old_signed = MediaRendition(
            "https://video.example/FHD/movie.mp4?pkey=old-high&expiration=1",
            width=1920,
            height=1080,
            bitrate=500,
            size_bytes=50_000,
        )
        refreshed_signed = MediaRendition(
            "https://video.example/FHD/movie.mp4?pkey=new-high&expiration=2",
            width=1920,
            height=1080,
            bitrate=500,
            size_bytes=50_000,
        )

        def video_with(renditions):
            return Video(
                id="1666569497233207296",
                title="训练方案",
                source_url="https://www.zhihu.com/zvideo/1666569497233207296",
                author=AUTHOR,
                published_at=NOW,
                description=(),
                asset=MediaAsset(
                    id="zvideo-1666569497233207296",
                    kind=MediaKind.VIDEO,
                    renditions=renditions,
                ),
            )

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first_downloader = RecordingDownloader()
            refreshed_downloader = RecordingDownloader()
            archive_assets(
                video_with((lower_bitrate, old_signed)),
                root / "media",
                downloader=first_downloader,
            )
            archive_assets(
                video_with((lower_bitrate, refreshed_signed)),
                root / "media",
                downloader=refreshed_downloader,
            )

        self.assertEqual(old_signed.source_url, first_downloader.calls[0][0])
        self.assertEqual(refreshed_signed.source_url, refreshed_downloader.calls[0][0])
        self.assertEqual(
            first_downloader.calls[0][1].name,
            refreshed_downloader.calls[0][1].name,
        )

    def test_question_and_column_archives_recurse_into_children(self):
        answer = Answer(
            id="answer",
            question=QuestionRef("q", "问题", "https://www.zhihu.com/question/q"),
            source_url="https://www.zhihu.com/question/q/answer/answer",
            author=AUTHOR,
            published_at=NOW,
            blocks=(MediaBlock(image("answer-image", "https://pic.example/a.jpg")),),
        )
        question = QuestionArchive(
            question=Question(
                id="q",
                title="问题",
                source_url="https://www.zhihu.com/question/q",
                detail=(MediaBlock(image("detail-image", "https://pic.example/q.png")),),
            ),
            answers=(answer,),
            archived_at=NOW,
        )
        article = Article(
            id="article",
            title="文章",
            source_url="https://zhuanlan.zhihu.com/p/article",
            author=AUTHOR,
            published_at=NOW,
            blocks=(MediaBlock(image("article-image", "https://pic.example/article.webp")),),
        )
        column = ColumnArchive(
            column=Column(
                token="column",
                title="专栏",
                source_url="https://www.zhihu.com/column/column",
                description="",
                author=AUTHOR,
                item_count=1,
            ),
            articles=(article,),
            archived_at=NOW,
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            question_downloader = RecordingDownloader()
            column_downloader = RecordingDownloader()
            archive_assets(
                question,
                root / "question" / "media",
                downloader=question_downloader,
            )
            archive_assets(
                column,
                root / "column" / "media",
                downloader=column_downloader,
            )

        self.assertEqual(
            ["https://pic.example/q.png", "https://pic.example/a.jpg"],
            [source for source, _ in question_downloader.calls],
        )
        self.assertEqual(
            ["https://pic.example/article.webp"],
            [source for source, _ in column_downloader.calls],
        )

    def test_empty_target_does_not_create_media_directory(self):
        article = Article(
            id="empty",
            title="空文章",
            source_url="https://zhuanlan.zhihu.com/p/empty",
            author=AUTHOR,
            published_at=None,
            blocks=(Paragraph((Text("只有正文"),)),),
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            media_directory = Path(temporary_directory) / "media"
            result = archive_assets(article, media_directory, downloader=RecordingDownloader())

            self.assertFalse(media_directory.exists())
            self.assertEqual({}, dict(result.source_paths))
            self.assertEqual((), result.downloads)


if __name__ == "__main__":
    unittest.main()
