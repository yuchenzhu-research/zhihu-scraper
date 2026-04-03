import unittest
from unittest.mock import patch

from core.scraper import ZhihuDownloader
from core.scraper_contracts import (
    CreatorFetchResult,
    CreatorProfileSummary,
    PageFetchResult,
    PaginationStats,
    ScrapedItem,
)


class ScraperContractTests(unittest.TestCase):
    def test_page_fetch_result_keeps_legacy_answer_shape(self):
        result = PageFetchResult(
            source_url="https://www.zhihu.com/question/1/answer/2",
            page_type="answer",
            items=(
                ScrapedItem(
                    id="2",
                    type="answer",
                    url="https://www.zhihu.com/question/1/answer/2",
                    title="问题",
                    author="作者",
                    html="<p>body</p>",
                    date="2026-04-04",
                ),
            ),
        )
        legacy = result.to_legacy_payload()
        self.assertIsInstance(legacy, dict)
        self.assertEqual(legacy["id"], "2")

    def test_page_fetch_result_keeps_legacy_question_shape(self):
        result = PageFetchResult(
            source_url="https://www.zhihu.com/question/1",
            page_type="question",
            items=(
                ScrapedItem(id="2", type="answer", url="u", title="t", author="a", html="", date="2026-04-04"),
                ScrapedItem(id="3", type="answer", url="u2", title="t2", author="a2", html="", date="2026-04-04"),
            ),
            pagination=PaginationStats(10, 2, 1, 2, True, False),
        )
        legacy = result.to_legacy_payload()
        self.assertIsInstance(legacy, list)
        self.assertEqual(len(legacy), 2)
        self.assertEqual(result.pagination.requested_limit, 10)

    def test_creator_fetch_result_roundtrips_to_legacy_dict(self):
        result = CreatorFetchResult(
            creator=CreatorProfileSummary(
                user_id="u1",
                name="Demo",
                url_token="demo",
                headline="",
                description="",
                profile_url="https://www.zhihu.com/people/demo",
                avatar_url="",
                follower_count=1,
                following_count=2,
                voteup_count=3,
                answer_count=4,
                articles_count=5,
                question_count=6,
                video_count=7,
                column_count=8,
            ),
            items=(
                ScrapedItem(id="1", type="article", url="u", title="t", author="a", html="", date="2026-04-04"),
            ),
            answers=PaginationStats(10, 4, 1, 20, False, False),
            articles=PaginationStats(5, 1, 1, 5, True, False),
        )

        legacy = result.to_dict()
        self.assertEqual(legacy["creator"]["url_token"], "demo")
        self.assertEqual(legacy["sync"]["answers"]["requested_limit"], 10)
        self.assertEqual(len(legacy["items"]), 1)


class QuestionFetchResultTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_result_attaches_question_pagination_stats(self):
        class FakeApiClient:
            def get_question_answers_page(self, question_id, limit, offset):
                self.last_call = (question_id, limit, offset)
                return {
                    "data": [
                        {
                            "id": "a1",
                            "author": {"name": "作者A"},
                            "question": {"title": "测试问题"},
                            "content": "<p>one</p>",
                            "created_time": 1712102400,
                            "voteup_count": 1,
                        },
                        {
                            "id": "a2",
                            "author": {"name": "作者B"},
                            "question": {"title": "测试问题"},
                            "content": "<p>two</p>",
                            "created_time": 1712102401,
                            "voteup_count": 2,
                        },
                    ],
                    "paging": {"is_end": True},
                }

        class FakeHumanizer:
            class Config:
                enabled = False

            config = Config()

            async def page_load(self):
                return None

        with patch("core.scraper.ZhihuAPIClient", return_value=FakeApiClient()):
            downloader = ZhihuDownloader("https://www.zhihu.com/question/123")

        with patch("core.scraper.get_humanizer", return_value=FakeHumanizer()):
            result = await downloader.fetch_result(limit=2)

        self.assertEqual(result.page_type, "question")
        self.assertEqual(len(result.items), 2)
        self.assertIsNotNone(result.pagination)
        self.assertEqual(result.pagination.requested_limit, 2)
        self.assertEqual(result.pagination.saved_count, 2)
        self.assertEqual(result.pagination.pages_fetched, 1)
        self.assertTrue(result.pagination.reached_end)


if __name__ == "__main__":
    unittest.main()
