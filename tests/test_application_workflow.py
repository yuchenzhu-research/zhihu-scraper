import json
import unittest
from datetime import UTC, datetime
from pathlib import Path

from zhihu_scraper.application import ArchiveWorkflow
from zhihu_scraper.archive import ArchiveReceipt
from zhihu_scraper.assets import MediaArchiveFailure, MediaArchiveRole
from zhihu_scraper.domain import (
    Answer,
    Article,
    ColumnArchive,
    MediaKind,
    QuestionArchive,
    Video,
)
from zhihu_scraper.http import InvalidResponseError
from zhihu_scraper.settings import ArchiveSettings, BrowserFallback
from zhihu_scraper.source import InvalidZhihuPayloadError

NOW = datetime(2026, 7, 26, tzinfo=UTC)


class FakeSource:
    def __init__(self):
        self.article = _article_payload("1", "文章")
        self.answer = _answer_payload("2", "10")
        self.question = {"id": 10, "title": "问题", "answer_count": 1}
        self.answers = [self.answer]
        self.column = {
            "id": "machinelearningpku",
            "title": "机器学习",
            "items_count": 1,
        }
        self.column_articles = [self.article]
        self.video = {
            "id": "3",
            "title": "视频",
            "author": {"id": "v", "name": "视频作者"},
            "video": {
                "playlist": {
                    "fhd": {
                        "play_url": "https://video.example/3.mp4",
                        "width": 1920,
                        "height": 1080,
                    }
                }
            },
        }

    def fetch_article_payload(self, target):
        return self.article

    def fetch_answer_payload(self, target):
        return self.answer

    def fetch_question_payload(self, target):
        return self.question

    def iter_question_answer_payloads(self, target, *, page_size):
        yield from self.answers

    def fetch_column_payload(self, target):
        return self.column

    def iter_column_article_payloads(self, target, *, page_size):
        yield from self.column_articles

    def fetch_video_payload(self, target):
        return self.video


class FakeSink:
    def __init__(self):
        self.targets = []

    def archive(self, target):
        self.targets.append(target)
        return ArchiveReceipt(Path(f"receipt-{target.id}"), None, None)


class FakeCommentClient:
    def __init__(self):
        self.calls = []

    def get_json(self, url):
        self.calls.append(url)
        if "root_comment" in url:
            return {
                "data": [],
                "paging": {"is_end": True, "next": ""},
            }
        raise AssertionError(url)


class FakeBrowser:
    def __init__(self, html, exported_cookies=None):
        self.html = html
        self.urls = []
        self.cookies = None
        self.exported_cookies = dict(exported_cookies or {})
        self.closed = False

    def set_cookie_dict(self, cookies):
        self.cookies = dict(cookies)

    def fetch_html(self, url):
        self.urls.append(url)
        return self.html

    def cookie_dict(self):
        return dict(self.exported_cookies)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True


class ArchiveWorkflowTests(unittest.TestCase):
    def test_rejects_an_archive_sink_without_a_structured_receipt(self):
        class InvalidSink:
            def archive(self, target):
                return "saved"

        workflow = ArchiveWorkflow(
            source=FakeSource(), sink=InvalidSink(), settings=ArchiveSettings()
        )
        with self.assertRaisesRegex(TypeError, "ArchiveReceipt"):
            workflow.run("https://zhuanlan.zhihu.com/p/1")

    def test_report_exposes_structured_media_failures_from_the_archive_sink(self):
        failure = MediaArchiveFailure(
            asset_id="missing-image",
            kind=MediaKind.IMAGE,
            role=MediaArchiveRole.CONTENT,
            source_url="https://pic.example/missing.png",
            destination=Path("media/missing.png"),
            error_type="MediaDownloadError",
            reason="unexpected HTTP status 404",
        )

        class FailureReportingSink(FakeSink):
            def archive(self, target):
                self.targets.append(target)
                return ArchiveReceipt(Path("saved"), None, None, media_failures=(failure,))

        report = ArchiveWorkflow(
            source=FakeSource(),
            sink=FailureReportingSink(),
            settings=ArchiveSettings(media_download=False),
            clock=lambda: NOW,
        ).run("https://zhuanlan.zhihu.com/p/1")

        self.assertEqual((failure,), report.media_failures)
        self.assertIn("404", report.media_failures[0].display_message)

    def test_routes_and_archives_every_supported_target_type(self):
        cases = (
            ("https://zhuanlan.zhihu.com/p/1", Article),
            ("https://www.zhihu.com/question/10/answer/2", Answer),
            ("https://www.zhihu.com/question/10", QuestionArchive),
            ("https://www.zhihu.com/column/machinelearningpku", ColumnArchive),
            ("https://www.zhihu.com/zvideo/3", Video),
        )

        for url, expected_type in cases:
            with self.subTest(url=url):
                sink = FakeSink()
                workflow = ArchiveWorkflow(
                    source=FakeSource(),
                    sink=sink,
                    settings=ArchiveSettings(media_download=False),
                    clock=lambda: NOW,
                )

                report = workflow.run(url)

                self.assertIsInstance(report.target, expected_type)
                self.assertIs(report.target, sink.targets[0])
                self.assertEqual(
                    Path(f"receipt-{report.target.id}"), report.receipt.entry_directory
                )
                self.assertFalse(report.used_browser)

    def test_column_articles_record_all_memberships_and_current_archive_origin(self):
        source = FakeSource()
        source.article["column"] = {
            "id": "another-column",
            "title": "另一个专栏",
            "url": "https://www.zhihu.com/column/another-column",
        }

        report = ArchiveWorkflow(
            source=source,
            sink=FakeSink(),
            settings=ArchiveSettings(media_download=False),
            clock=lambda: NOW,
        ).run("https://www.zhihu.com/column/machinelearningpku")

        self.assertIsInstance(report.target, ColumnArchive)
        self.assertEqual(1, report.target.column.item_count)
        self.assertEqual(
            ("another-column", "machinelearningpku"),
            tuple(column.token for column in report.target.articles[0].columns),
        )

    def test_comments_are_absent_by_default_and_fetched_only_when_enabled(self):
        disabled_client = FakeCommentClient()
        disabled = ArchiveWorkflow(
            source=FakeSource(),
            sink=FakeSink(),
            settings=ArchiveSettings(media_download=False),
            comment_client=disabled_client,
            clock=lambda: NOW,
        ).run("https://zhuanlan.zhihu.com/p/1")

        enabled_client = FakeCommentClient()
        enabled = ArchiveWorkflow(
            source=FakeSource(),
            sink=FakeSink(),
            settings=ArchiveSettings(
                comments=True,
                comment_roots=10,
                comment_replies=10,
                media_download=False,
            ),
            comment_client=enabled_client,
            clock=lambda: NOW,
        ).run("https://zhuanlan.zhihu.com/p/1")

        self.assertIsNone(disabled.target.comments)
        self.assertEqual([], disabled_client.calls)
        self.assertIsNotNone(enabled.target.comments)
        self.assertEqual(1, len(enabled_client.calls))

    def test_auto_browser_fallback_extracts_page_state_and_imports_cookies(self):
        source = FakeSource()

        def fail_article(target):
            raise InvalidZhihuPayloadError("blocked")

        source.fetch_article_payload = fail_article
        state = {
            "initialState": {
                "entities": {
                    "articles": {
                        "1": _article_payload("1", "浏览器文章"),
                    }
                }
            }
        }
        browser = FakeBrowser(
            f'<script id="js-initialData">{json.dumps(state, ensure_ascii=False)}</script>',
            exported_cookies={"__zse_ck": "browser-session"},
        )
        browser_cookie_updates = []
        workflow = ArchiveWorkflow(
            source=source,
            sink=FakeSink(),
            settings=ArchiveSettings(
                media_download=False,
                browser_fallback=BrowserFallback.AUTO,
            ),
            browser_factory=lambda: browser,
            browser_cookies={"z_c0": "secret"},
            browser_cookie_sink=browser_cookie_updates.append,
            clock=lambda: NOW,
        )

        report = workflow.run("https://zhuanlan.zhihu.com/p/1")

        self.assertEqual("浏览器文章", report.target.title)
        self.assertTrue(report.used_browser)
        self.assertEqual({"z_c0": "secret"}, browser.cookies)
        self.assertEqual(
            [{"__zse_ck": "browser-session"}],
            browser_cookie_updates,
        )
        self.assertTrue(browser.closed)

    def test_auto_browser_fallback_replaces_a_truncated_success_payload(self):
        source = FakeSource()
        source.article = {
            "id": "1",
            "title": "被裁剪的文章",
            "author": {"id": "a", "name": "文章作者"},
        }
        complete = _article_payload("1", "浏览器完整文章")
        complete["content"] = "<p>不能静默丢失的完整正文</p>"
        state = {
            "initialState": {
                "entities": {
                    "articles": {
                        "1": complete,
                    }
                }
            }
        }
        browser = FakeBrowser(
            f'<script id="js-initialData">{json.dumps(state, ensure_ascii=False)}</script>'
        )

        report = ArchiveWorkflow(
            source=source,
            sink=FakeSink(),
            settings=ArchiveSettings(media_download=False),
            browser_factory=lambda: browser,
            clock=lambda: NOW,
        ).run("https://zhuanlan.zhihu.com/p/1")

        self.assertEqual("浏览器完整文章", report.target.title)
        self.assertEqual("不能静默丢失的完整正文", report.target.blocks[0].inlines[0].text)
        self.assertTrue(report.used_browser)

    def test_question_retries_truncated_answer_collection_after_browser_hydration(self):
        source = FakeSource()
        source.answers = [
            {
                "id": "2",
                "question": {"id": "10", "title": "问题"},
                "author": {"id": "b", "name": "回答作者"},
            }
        ]
        state = {
            "initialState": {
                "entities": {
                    "questions": {
                        "10": source.question,
                    }
                }
            }
        }
        browser = FakeBrowser(
            f'<script id="js-initialData">{json.dumps(state, ensure_ascii=False)}</script>',
            exported_cookies={"__zse_ck": "browser-session"},
        )

        def update_session(_cookies):
            source.answers = [_answer_payload("2", "10")]

        report = ArchiveWorkflow(
            source=source,
            sink=FakeSink(),
            settings=ArchiveSettings(media_download=False),
            browser_factory=lambda: browser,
            browser_cookie_sink=update_session,
            clock=lambda: NOW,
        ).run("https://www.zhihu.com/question/10")

        self.assertIsInstance(report.target, QuestionArchive)
        self.assertEqual("回答", report.target.answers[0].blocks[0].inlines[0].text)
        self.assertTrue(report.used_browser)

    def test_question_pagination_retries_after_browser_cookie_backflow(self):
        source = FakeSource()
        source.session_ready = False

        def fail_question(target):
            raise InvalidZhihuPayloadError("blocked")

        def gated_answers(target, *, page_size):
            if not source.session_ready:
                raise InvalidZhihuPayloadError("missing browser session")
            yield source.answer

        source.fetch_question_payload = fail_question
        source.iter_question_answer_payloads = gated_answers
        state = {
            "initialState": {
                "entities": {
                    "questions": {
                        "10": source.question,
                    }
                }
            }
        }
        browser = FakeBrowser(
            f'<script id="js-initialData">{json.dumps(state, ensure_ascii=False)}</script>',
            exported_cookies={"__zse_ck": "browser-session"},
        )

        def update_session(cookies):
            self.assertEqual({"__zse_ck": "browser-session"}, cookies)
            source.session_ready = True

        report = ArchiveWorkflow(
            source=source,
            sink=FakeSink(),
            settings=ArchiveSettings(media_download=False),
            browser_factory=lambda: browser,
            browser_cookie_sink=update_session,
            clock=lambda: NOW,
        ).run("https://www.zhihu.com/question/10")

        self.assertIsInstance(report.target, QuestionArchive)
        self.assertEqual(1, len(report.target.answers))
        self.assertTrue(report.used_browser)

    def test_comments_retry_once_after_browser_cookie_backflow(self):
        source = FakeSource()
        state = {
            "initialState": {
                "entities": {
                    "articles": {
                        "1": source.article,
                    }
                }
            }
        }
        browser = FakeBrowser(
            f'<script id="js-initialData">{json.dumps(state, ensure_ascii=False)}</script>',
            exported_cookies={"__zse_ck": "browser-session"},
        )

        class GatedCommentClient(FakeCommentClient):
            def __init__(self):
                super().__init__()
                self.session_ready = False

            def get_json(self, url):
                self.calls.append(url)
                if not self.session_ready:
                    raise InvalidResponseError("blocked")
                return {
                    "data": [],
                    "paging": {"is_end": True, "next": ""},
                }

        comments = GatedCommentClient()

        def update_session(cookies):
            self.assertEqual({"__zse_ck": "browser-session"}, cookies)
            comments.session_ready = True

        report = ArchiveWorkflow(
            source=source,
            sink=FakeSink(),
            settings=ArchiveSettings(
                comments=True,
                media_download=False,
            ),
            comment_client=comments,
            browser_factory=lambda: browser,
            browser_cookie_sink=update_session,
            clock=lambda: NOW,
        ).run("https://zhuanlan.zhihu.com/p/1")

        self.assertIsNotNone(report.target.comments)
        self.assertEqual(2, len(comments.calls))
        self.assertTrue(report.used_browser)
        self.assertEqual(
            ["https://zhuanlan.zhihu.com/p/1"],
            browser.urls,
        )

    def test_invalid_comment_payload_uses_the_same_browser_hydration_path(self):
        source = FakeSource()
        state = {
            "initialState": {
                "entities": {
                    "articles": {
                        "1": source.article,
                    }
                }
            }
        }
        browser = FakeBrowser(
            f'<script id="js-initialData">{json.dumps(state, ensure_ascii=False)}</script>',
            exported_cookies={"__zse_ck": "browser-session"},
        )

        class InvalidThenReadyComments(FakeCommentClient):
            def __init__(self):
                super().__init__()
                self.ready = False

            def get_json(self, url):
                self.calls.append(url)
                if not self.ready:
                    return {"error": {"message": "challenge"}}
                return {"data": [], "paging": {"is_end": True, "next": ""}}

        comments = InvalidThenReadyComments()

        report = ArchiveWorkflow(
            source=source,
            sink=FakeSink(),
            settings=ArchiveSettings(comments=True, media_download=False),
            comment_client=comments,
            browser_factory=lambda: browser,
            browser_cookie_sink=lambda _cookies: setattr(comments, "ready", True),
            clock=lambda: NOW,
        ).run("https://zhuanlan.zhihu.com/p/1")

        self.assertIsNotNone(report.target.comments)
        self.assertEqual(2, len(comments.calls))
        self.assertTrue(report.used_browser)

    def test_browser_never_preserves_the_original_fetch_error(self):
        source = FakeSource()

        def fail_article(target):
            raise InvalidZhihuPayloadError("blocked")

        source.fetch_article_payload = fail_article
        workflow = ArchiveWorkflow(
            source=source,
            sink=FakeSink(),
            settings=ArchiveSettings(
                media_download=False,
                browser_fallback=BrowserFallback.NEVER,
            ),
            browser_factory=lambda: FakeBrowser(""),
            clock=lambda: NOW,
        )

        with self.assertRaisesRegex(InvalidZhihuPayloadError, "blocked"):
            workflow.run("https://zhuanlan.zhihu.com/p/1")


def _article_payload(article_id, title):
    return {
        "id": article_id,
        "title": title,
        "content": "<p>正文</p>",
        "author": {"id": "a", "name": "文章作者"},
    }


def _answer_payload(answer_id, question_id):
    return {
        "id": answer_id,
        "content": "<p>回答</p>",
        "author": {"id": "b", "name": "回答作者"},
        "question": {"id": question_id, "title": "问题"},
    }


if __name__ == "__main__":
    unittest.main()
