import json
import unittest

from zhihu_scraper.source import (
    InvalidZhihuPayloadError,
    PaginationLoopError,
    ZhihuSource,
    extract_article_payload,
    extract_entity_payload,
)
from zhihu_scraper.urls import route_zhihu_url


class FakeClient:
    def __init__(
        self,
        *,
        json_responses: list[object] | None = None,
        html_responses: list[str] | None = None,
    ) -> None:
        self._json_responses = list(json_responses or [])
        self._html_responses = list(html_responses or [])
        self.json_calls: list[str] = []
        self.html_calls: list[str] = []

    def get_json(self, url_or_path: str) -> object:
        self.json_calls.append(url_or_path)
        return self._json_responses.pop(0)

    def get_html(self, url_or_path: str) -> str:
        self.html_calls.append(url_or_path)
        return self._html_responses.pop(0)


class ArticleSourceTests(unittest.TestCase):
    def test_returns_a_valid_direct_article_api_payload_without_loading_html(self):
        payload = {
            "id": 357892158,
            "title": "一文归纳 AI 数据增强之法",
            "content": "<p>正文</p>",
        }
        client = FakeClient(json_responses=[payload])
        source = ZhihuSource(client)

        result = source.fetch_article_payload("357892158")

        self.assertEqual(payload, result)
        self.assertEqual(
            ["/api/v4/articles/357892158"],
            client.json_calls,
        )
        self.assertEqual([], client.html_calls)

    def test_request_parameter_api_error_falls_back_to_article_initial_state(self):
        article_payload = {
            "id": 11617075708,
            "title": "含数学公式的文章",
            "content": '<p><img eeimg="1"/></p>',
        }
        initial_state = {
            "initialState": {
                "entities": {
                    "articles": {
                        "11617075708": article_payload,
                    }
                }
            }
        }
        page = (
            '<html><script type="text/json" id="js-initialData">'
            f"{json.dumps(initial_state, ensure_ascii=False)}"
            "</script></html>"
        )
        client = FakeClient(
            json_responses=[
                {
                    "error": {
                        "code": 10003,
                        "message": "请求参数异常，请升级客户端后重试。",
                    }
                }
            ],
            html_responses=[page],
        )
        source = ZhihuSource(client)

        result = source.fetch_article_payload("https://zhuanlan.zhihu.com/p/11617075708")

        self.assertEqual(article_payload, result)
        self.assertEqual(
            ["https://zhuanlan.zhihu.com/p/11617075708"],
            client.html_calls,
        )

    def test_extracts_window_initial_state_with_braces_inside_json_strings(self):
        article_payload = {
            "id": 42,
            "title": "花括号 } 与分号 ; 不截断 JSON",
            "content": "<p>正文</p>",
        }
        state = {
            "initialState": {
                "entities": {
                    "articles": {
                        "42": article_payload,
                    }
                }
            }
        }
        page = (
            "<script>window.__INITIAL_STATE__ = "
            f"{json.dumps(state, ensure_ascii=False)};"
            "window.after = true;</script>"
        )

        self.assertEqual(article_payload, extract_article_payload(page, "42"))

    def test_missing_or_malformed_initial_state_is_reported_as_invalid_payload(self):
        cases = (
            "<html><article>没有初始状态</article></html>",
            '<script id="js-initialData" type="text/json">{broken}</script>',
            (
                '<script id="js-initialData" type="text/json">'
                '{"initialState":{"entities":{"articles":{"99":{"id":99}}}}}'
                "</script>"
            ),
        )

        for page in cases:
            with self.subTest(page=page):
                with self.assertRaises(InvalidZhihuPayloadError):
                    extract_article_payload(page, "42")

    def test_unrelated_api_error_is_not_silently_treated_as_an_html_failure(self):
        client = FakeClient(
            json_responses=[{"error": {"code": 40362, "message": "内容不存在或无权访问"}}]
        )

        with self.assertRaisesRegex(
            InvalidZhihuPayloadError,
            "文章 API",
        ):
            ZhihuSource(client).fetch_article_payload("42")

        self.assertEqual([], client.html_calls)

    def test_generic_initial_state_extractor_supports_answers_questions_and_video(self):
        state = {
            "initialState": {
                "entities": {
                    "answers": {"200": {"id": 200, "content": "<p>回答</p>"}},
                    "questions": {"100": {"id": 100, "title": "问题"}},
                    "zvideos": {"300": {"id": 300, "title": "视频"}},
                }
            }
        }
        page = (
            '<script id="js-initialData" type="text/json">'
            f"{json.dumps(state, ensure_ascii=False)}"
            "</script>"
        )

        self.assertEqual(
            200,
            extract_entity_payload(page, collection="answers", entity_id="200")["id"],
        )
        self.assertEqual(
            "问题",
            extract_entity_payload(
                page,
                collection="questions",
                entity_id="100",
            )["title"],
        )
        self.assertEqual(
            "视频",
            extract_entity_payload(page, collection="zvideos", entity_id="300")["title"],
        )

        with self.assertRaises(InvalidZhihuPayloadError):
            extract_entity_payload(page, collection="answers", entity_id="missing")
        with self.assertRaises(ValueError):
            extract_entity_payload(page, collection="pins", entity_id="missing")


class SinglePayloadSourceTests(unittest.TestCase):
    def test_fetches_answer_question_column_and_video_from_real_api_routes(self):
        cases = (
            (
                "fetch_answer_payload",
                "https://www.zhihu.com/question/100/answer/200",
                "/api/v4/answers/200?include=content,voteup_count,question,author",
                {"id": 200, "content": "<p>回答</p>"},
            ),
            (
                "fetch_question_payload",
                "https://www.zhihu.com/question/100",
                "/api/v4/questions/100",
                {"id": 100, "title": "问题"},
            ),
            (
                "fetch_column_payload",
                "https://www.zhihu.com/column/machinelearningpku",
                "/api/v4/columns/machinelearningpku",
                {"id": "machinelearningpku", "title": "机器学习"},
            ),
            (
                "fetch_video_payload",
                "https://www.zhihu.com/zvideo/1666569497233207296",
                "/api/v4/zvideos/1666569497233207296",
                {"id": "1666569497233207296", "title": "哑铃全身训练方案"},
            ),
        )

        for method_name, target_url, expected_path, payload in cases:
            with self.subTest(method=method_name):
                client = FakeClient(json_responses=[payload])
                source = ZhihuSource(client)

                result = getattr(source, method_name)(target_url)

                self.assertEqual(payload, result)
                self.assertEqual([expected_path], client.json_calls)

    def test_accepts_a_preparsed_target_and_rejects_the_wrong_target_kind(self):
        article_target = route_zhihu_url("https://zhuanlan.zhihu.com/p/42")
        client = FakeClient(json_responses=[{"id": 42}])
        source = ZhihuSource(client)

        self.assertEqual({"id": 42}, source.fetch_article_payload(article_target))

        with self.assertRaisesRegex(ValueError, "回答"):
            source.fetch_answer_payload(article_target)

    def test_single_payload_endpoints_reject_non_mapping_json(self):
        methods = (
            "fetch_answer_payload",
            "fetch_question_payload",
            "fetch_column_payload",
            "fetch_video_payload",
        )

        for method_name in methods:
            with self.subTest(method=method_name):
                source = ZhihuSource(FakeClient(json_responses=[["not", "mapping"]]))
                with self.assertRaises(InvalidZhihuPayloadError):
                    getattr(source, method_name)("42")


class PaginationSourceTests(unittest.TestCase):
    def test_iterates_question_answers_by_following_paging_next_until_end(self):
        next_url = (
            "https://www.zhihu.com/api/v4/questions/100/answers"
            "?limit=2&offset=2&platform=desktop&sort_by=default"
            "&include=data%5B%2A%5D.content%2Cvoteup_count%2Ccomment_count"
        )
        client = FakeClient(
            json_responses=[
                {
                    "data": [{"id": 1}, {"id": 2}],
                    "paging": {"is_end": False, "next": next_url},
                },
                {
                    "data": [{"id": 3}],
                    "paging": {"is_end": True, "next": ""},
                },
            ]
        )
        source = ZhihuSource(client)

        answers = list(source.iter_question_answer_payloads("100", page_size=2))

        self.assertEqual([{"id": 1}, {"id": 2}, {"id": 3}], answers)
        self.assertEqual(
            [
                (
                    "/api/v4/questions/100/answers?limit=2&offset=0"
                    "&platform=desktop&sort_by=default"
                    "&include=data%5B%2A%5D.content%2Cvoteup_count%2Ccomment_count"
                ),
                next_url,
            ],
            client.json_calls,
        )

    def test_iterates_column_items_and_advances_offset_when_next_is_omitted(self):
        client = FakeClient(
            json_responses=[
                {
                    "data": [{"id": 11}, {"id": 12}],
                    "paging": {"is_end": False},
                },
                {
                    "data": [{"id": 13}],
                    "paging": {"is_end": True},
                },
            ]
        )
        source = ZhihuSource(client)

        articles = list(
            source.iter_column_article_payloads(
                "https://www.zhihu.com/column/machinelearningpku",
                page_size=2,
            )
        )

        self.assertEqual([{"id": 11}, {"id": 12}, {"id": 13}], articles)
        self.assertEqual(
            [
                "/api/v4/columns/machinelearningpku/items?limit=2&offset=0",
                "/api/v4/columns/machinelearningpku/items?limit=2&offset=2",
            ],
            client.json_calls,
        )

    def test_deduplicates_overlapping_pages_by_stable_id_preserving_first_seen_order(self):
        client = FakeClient(
            json_responses=[
                {
                    "data": [
                        {"id": 11, "title": "first"},
                        {"id": "12", "title": "original"},
                    ],
                    "paging": {"is_end": False},
                },
                {
                    "data": [
                        {"id": 12, "title": "duplicate"},
                        {"id": 13, "title": "last"},
                    ],
                    "paging": {"is_end": True},
                },
            ]
        )

        articles = list(
            ZhihuSource(client).iter_column_article_payloads(
                "machinelearningpku",
                page_size=2,
            )
        )

        self.assertEqual(
            [
                {"id": 11, "title": "first"},
                {"id": "12", "title": "original"},
                {"id": 13, "title": "last"},
            ],
            articles,
        )

    def test_normalizes_legacy_http_next_from_the_same_zhihu_endpoint(self):
        insecure_next = (
            "http://www.zhihu.com/api/v4/columns/machinelearningpku/items?limit=2&offset=2"
        )
        secure_next = insecure_next.replace("http://", "https://", 1)
        client = FakeClient(
            json_responses=[
                {
                    "data": [{"id": 11}, {"id": 12}],
                    "paging": {"is_end": False, "next": insecure_next},
                },
                {
                    "data": [{"id": 13}],
                    "paging": {"is_end": True, "next": ""},
                },
            ]
        )

        articles = list(
            ZhihuSource(client).iter_column_article_payloads(
                "machinelearningpku",
                page_size=2,
            )
        )

        self.assertEqual([{"id": 11}, {"id": 12}, {"id": 13}], articles)
        self.assertEqual(
            [
                "/api/v4/columns/machinelearningpku/items?limit=2&offset=0",
                secure_next,
            ],
            client.json_calls,
        )

    def test_stops_when_changing_offsets_keep_returning_the_same_items(self):
        client = FakeClient(
            json_responses=[{"data": [{"id": 1}], "paging": {"is_end": False}} for _ in range(4)]
        )

        with self.assertRaisesRegex(PaginationLoopError, "没有新增"):
            list(ZhihuSource(client).iter_column_article_payloads("demo", page_size=1))

        self.assertEqual(3, len(client.json_calls))
        self.assertEqual(3, len(set(client.json_calls)))

    def test_stops_repeated_page_sequences_even_when_next_urls_keep_changing(self):
        for pages in (([1], [2], [1], [2]), ([], [])):
            with self.subTest(pages=pages):
                client = FakeClient(
                    json_responses=[
                        {
                            "data": [{"id": item_id} for item_id in page_ids],
                            "paging": {
                                "is_end": False,
                                "next": (
                                    f"/api/v4/questions/100/answers?limit=1&offset={index + 1}"
                                ),
                            },
                        }
                        for index, page_ids in enumerate(pages)
                    ]
                )

                with self.assertRaisesRegex(PaginationLoopError, "没有新增"):
                    list(ZhihuSource(client).iter_question_answer_payloads("100", page_size=1))

                self.assertEqual(len(pages), len(client.json_calls))

    def test_one_overlapping_page_can_recover_and_terminal_duplicates_are_allowed(self):
        ids = [1, 1, 2, 2, 3, 3]
        client = FakeClient(
            json_responses=[
                {"data": [{"id": item_id}], "paging": {"is_end": index == len(ids) - 1}}
                for index, item_id in enumerate(ids)
            ]
        )

        articles = list(ZhihuSource(client).iter_column_article_payloads("demo", page_size=1))

        self.assertEqual([{"id": 1}, {"id": 2}, {"id": 3}], articles)
        self.assertEqual(len(ids), len(client.json_calls))

    def test_pagination_rejects_items_without_stable_ids_before_requesting_more(self):
        for item in ({}, {"id": " "}, {"id": True}, {"id": []}):
            with self.subTest(item=item):
                client = FakeClient(
                    json_responses=[
                        {"data": [item], "paging": {"is_end": False}},
                        {"data": [], "paging": {"is_end": True}},
                    ]
                )

                with self.assertRaisesRegex(InvalidZhihuPayloadError, "ID"):
                    list(ZhihuSource(client).iter_column_article_payloads("demo", page_size=1))

                self.assertEqual(1, len(client.json_calls))

    def test_detects_repeated_next_urls_before_requesting_forever(self):
        repeated_url = (
            "https://www.zhihu.com/api/v4/questions/100/answers"
            "?limit=1&offset=1&platform=desktop&sort_by=default"
        )
        client = FakeClient(
            json_responses=[
                {
                    "data": [{"id": 1}],
                    "paging": {"is_end": False, "next": repeated_url},
                },
                {
                    "data": [{"id": 2}],
                    "paging": {"is_end": False, "next": repeated_url},
                },
            ]
        )

        with self.assertRaises(PaginationLoopError):
            list(
                ZhihuSource(client).iter_question_answer_payloads(
                    "100",
                    page_size=1,
                )
            )

        self.assertEqual(2, len(client.json_calls))

    def test_rejects_non_mapping_pages_data_items_and_paging(self):
        invalid_pages = (
            ["page"],
            {"data": "not-a-list", "paging": {"is_end": True}},
            {"data": [1], "paging": {"is_end": True}},
            {"data": [], "paging": []},
        )

        for invalid_page in invalid_pages:
            with self.subTest(page=invalid_page):
                source = ZhihuSource(FakeClient(json_responses=[invalid_page]))
                with self.assertRaises(InvalidZhihuPayloadError):
                    list(source.iter_column_article_payloads("machinelearningpku"))

    def test_non_terminal_empty_page_without_next_is_rejected(self):
        source = ZhihuSource(
            FakeClient(
                json_responses=[
                    {"data": [], "paging": {"is_end": False}},
                ]
            )
        )

        with self.assertRaises(PaginationLoopError):
            list(source.iter_column_article_payloads("machinelearningpku"))

    def test_page_size_is_bounded(self):
        source = ZhihuSource(FakeClient())

        for page_size in (0, -1, 101):
            with self.subTest(page_size=page_size):
                with self.assertRaisesRegex(ValueError, "1 到 100"):
                    list(
                        source.iter_question_answer_payloads(
                            "100",
                            page_size=page_size,
                        )
                    )


if __name__ == "__main__":
    unittest.main()
