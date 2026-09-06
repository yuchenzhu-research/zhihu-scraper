from unittest.mock import Mock

import pytest

from zhihu_scraper.application import ArchiveWorkflow, BatchArchiveInterruptedError
from zhihu_scraper.archive import LocalArchive
from zhihu_scraper.http import RateLimitError, RetryWaitError, ZhihuHttpError
from zhihu_scraper.settings import ArchiveSettings


@pytest.mark.parametrize("stage", ["article", "collection", "comments"])
@pytest.mark.parametrize(
    "error",
    [
        RateLimitError(429, "rate limit exhausted"),
        ZhihuHttpError(429, "too many requests"),
        RetryWaitError("server wait exceeds budget"),
    ],
)
def test_rate_limit_stops_acquisition_without_starting_browser(tmp_path, stage, error):
    source = Mock()
    source.fetch_article_payload.return_value = {
        "id": "1",
        "title": "文章",
        "content": "<p>正文</p>",
    }
    source.fetch_column_payload.return_value = {"id": "example", "title": "专栏"}
    comments = Mock()
    if stage == "article":
        source.fetch_article_payload.side_effect = error
    elif stage == "collection":
        source.iter_column_article_payloads.side_effect = error
    else:
        comments.get_json.side_effect = error
    browser = Mock(side_effect=AssertionError("rate limit must not start browser"))
    workflow = ArchiveWorkflow(
        source=source,
        sink=LocalArchive(tmp_path, media_download=False),
        settings=ArchiveSettings(comments=stage == "comments"),
        comment_client=comments,
        browser_factory=browser,
    )

    with pytest.raises(
        BatchArchiveInterruptedError if stage == "collection" else type(error)
    ) as raised:
        workflow.run(
            "https://www.zhihu.com/column/example"
            if stage == "collection"
            else "https://zhuanlan.zhihu.com/p/1"
        )

    actual = raised.value.__cause__ if stage == "collection" else raised.value
    assert actual is error
    browser.assert_not_called()


@pytest.mark.parametrize("fails_again", [False, True])
def test_browser_recovery_restarts_a_stream_once_without_saving_duplicates(tmp_path, fails_again):
    import json
    from unittest.mock import MagicMock

    from zhihu_scraper.http import InvalidResponseError

    first = {"id": "1", "title": "第一篇", "content": "<p>正文一</p>"}
    second = {"id": "2", "title": "第二篇", "content": "<p>正文二</p>"}
    exhausted = InvalidResponseError("recovered stream is unavailable")

    def initial():
        yield first
        raise InvalidResponseError("refresh needed")

    def recovered():
        yield first
        if fails_again:
            raise exhausted
        yield second

    source = Mock()
    source.fetch_column_payload.return_value = {"id": "example", "title": "专栏", "items_count": 2}
    source.iter_column_article_payloads.side_effect = [initial(), recovered()]
    browser = MagicMock()
    browser.__enter__.return_value = browser
    browser.cookie_dict.return_value = {}
    state = {
        "initialState": {
            "entities": {"columns": {"example": source.fetch_column_payload.return_value}}
        }
    }
    browser.fetch_html.return_value = (
        '<script id="js-initialData">' + json.dumps(state) + "</script>"
    )
    factory = Mock(return_value=browser)
    events = []
    workflow = ArchiveWorkflow(
        source=source,
        sink=LocalArchive(tmp_path, media_download=False),
        settings=ArchiveSettings(media_download=False),
        browser_factory=factory,
        progress=events.append,
    )

    if fails_again:
        with pytest.raises(BatchArchiveInterruptedError) as raised:
            workflow.run("https://www.zhihu.com/column/example")
        assert raised.value.__cause__ is exhausted
    else:
        report = workflow.run("https://www.zhihu.com/column/example")
        assert [article.id for article in report.target.articles] == ["1", "2"]
        assert report.used_browser

    factory.assert_called_once_with()
    browser.__exit__.assert_called_once()
    assert source.iter_column_article_payloads.call_count == 2
    assert [event.current_title for event in events if event.stage == "saved"] == (
        ["第一篇"] if fails_again else ["第一篇", "第二篇"]
    )
