from dataclasses import replace
from datetime import UTC, datetime

import pytest

from zhihu_scraper.content import parse_rich_text
from zhihu_scraper.domain import (
    Answer,
    Article,
    Author,
    Column,
    ColumnArchive,
    EmbeddedVideo,
    MediaBlock,
    MediaKind,
    Paragraph,
    Question,
    QuestionArchive,
    QuestionRef,
    Quote,
    Text,
)
from zhihu_scraper.embedded_video import resolve_embedded_videos
from zhihu_scraper.http import AccessDeniedError, RetryWaitError, TransportError, ZhihuHttpError
from zhihu_scraper.normalize import normalize_answer, normalize_article
from zhihu_scraper.render import HtmlRenderer, MarkdownRenderer

VIDEO_PAGE = "https://www.zhihu.com/video/123456789"
CARD = f'<a class="video-box" href="{VIDEO_PAGE}">实验演示</a>'
PLAYLIST = {
    "playlist_v2": {
        "HD": {
            "play_url": "https://vdn1.vzuu.com/hd.mp4",
            "format": "mp4",
            "width": 1280,
            "height": 720,
            "size": 100,
        },
        "FHD": {
            "play_url": "https://vdn1.vzuu.com/fhd.mp4",
            "format": "mp4",
            "width": 1920,
            "height": 1080,
            "size": 200,
        },
    }
}


def article_with(blocks):
    return Article(
        id="101",
        title="内嵌视频文章",
        source_url="https://zhuanlan.zhihu.com/p/101",
        author=Author(id="author", name="作者"),
        published_at=None,
        blocks=blocks,
    )


def test_video_card_keeps_its_page_identity_between_surrounding_text():
    blocks = parse_rich_text(f"<p>前文{CARD}后文</p>")

    assert blocks == (
        Paragraph((Text("前文"),)),
        EmbeddedVideo(video_id="123456789", source_url=VIDEO_PAGE, title="实验演示"),
        Paragraph((Text("后文"),)),
    )


def test_explicit_lens_id_is_distinct_from_a_zvideo_page_id():
    blocks = parse_rich_text(
        '<a class="video-box" data-lens-id="123456789" '
        'href="https://www.zhihu.com/zvideo/987654321" title="视频卡片">播放</a>'
    )

    assert blocks == (
        EmbeddedVideo(
            video_id="123456789",
            source_url="https://www.zhihu.com/zvideo/987654321",
            title="视频卡片",
        ),
    )


def test_direct_mp4_is_media_but_a_video_page_is_an_ordinary_link():
    blocks = parse_rich_text(
        '<video title="直接播放"><source src="https://vdn1.vzuu.com/demo.mp4" '
        'type="video/mp4"></video>'
        f'<video src="{VIDEO_PAGE}" title="视频页面"></video>'
    )

    assert isinstance(blocks[0], MediaBlock)
    assert blocks[0].asset.kind is MediaKind.VIDEO
    assert blocks[0].asset.renditions[0].source_url == "https://vdn1.vzuu.com/demo.mp4"
    assert isinstance(blocks[1], Paragraph)
    assert VIDEO_PAGE in MarkdownRenderer().render(article_with(blocks))


def test_a_direct_video_source_takes_precedence_over_its_optional_lens_id():
    blocks = parse_rich_text(
        '<video data-lens-id="123456789" src="https://vdn1.vzuu.com/demo.mp4"></video>'
    )

    assert isinstance(blocks[0], MediaBlock)
    result = resolve_embedded_videos(
        article_with(blocks),
        get_json=lambda _url: pytest.fail("direct source needs no lens request"),
    )
    assert not result.warnings


@pytest.mark.parametrize(
    "fragment",
    [
        '<a class="video-box" href="https://attacker.example/video/123">外部网页</a>',
        '<a class="video-box" data-lens-id="../private" href="/video/no-id">失效视频</a>',
        '<a class="video-box" href="https://www.zhihu.com/zvideo/987654321">独立视频页</a>',
    ],
)
def test_unknown_video_cards_are_not_guessed_into_lens_requests(fragment):
    target = article_with(parse_rich_text(fragment))
    result = resolve_embedded_videos(
        target, get_json=lambda _url: pytest.fail("unknown card must not issue a request")
    )

    assert result.target == target
    assert not result.warnings
    assert not any(isinstance(block, MediaBlock) for block in target.blocks)


@pytest.mark.parametrize("normalizer", [normalize_article, normalize_answer])
def test_article_and_answer_payloads_preserve_embedded_cards(normalizer):
    target = normalizer(
        {
            "id": "101",
            "title": "文章",
            "question": {"id": "201", "title": "问题"},
            "content": f"<p>正文</p>{CARD}",
        }
    )

    assert isinstance(target.blocks[-1], EmbeddedVideo)


def test_resolver_fetches_each_lens_once_and_preserves_original_page_links():
    target = article_with((parse_rich_text(CARD)[0], Quote(parse_rich_text(CARD))))
    requests = []

    def get_json(url):
        requests.append(url)
        return PLAYLIST

    result = resolve_embedded_videos(target, get_json=get_json)

    assert requests == ["https://lens.zhihu.com/api/v4/videos/123456789"]
    assert not result.warnings
    block = result.target.blocks[0]
    assert isinstance(block, MediaBlock)
    assert [variant.height for variant in block.asset.renditions] == [720, 1080]
    assert [variant.size_bytes for variant in block.asset.renditions] == [100, 200]
    markdown = MarkdownRenderer().render(result.target)
    assert VIDEO_PAGE in markdown
    assert "原始视频页面" in markdown
    assert isinstance(target.blocks[0], EmbeddedVideo)
    local_paths = {rendition.source_url: "media/video.mp4" for rendition in block.asset.renditions}
    local_html = HtmlRenderer().render(result.target, media_paths=local_paths)
    assert '<video controls preload="metadata" src="media/video.mp4"></video>' in local_html
    assert VIDEO_PAGE in local_html


def test_unavailable_video_keeps_body_and_readable_links_without_exposing_error_details():
    target = article_with(parse_rich_text(f"<p>正文保留</p>{CARD}"))

    def get_json(_url):
        raise TransportError("request failed with pkey=secret")

    result = resolve_embedded_videos(target, get_json=get_json)
    markdown = MarkdownRenderer().render(result.target)
    rendered_html = HtmlRenderer().render(result.target)

    assert result.target == target
    assert len(result.warnings) == 1
    assert result.warnings[0].video_id == "123456789"
    assert "secret" not in result.warnings[0].display_message
    assert "正文保留" in markdown
    assert VIDEO_PAGE in markdown and VIDEO_PAGE in rendered_html
    assert "<video " not in rendered_html
    assert "<iframe" not in rendered_html


def test_access_denial_stops_further_lens_requests_without_discarding_other_content():
    target = article_with(parse_rich_text(CARD + CARD.replace("123456789", "987654321")))
    requests = []

    def get_json(url):
        requests.append(url)
        raise AccessDeniedError(403, "denied, cookie=secret")

    result = resolve_embedded_videos(target, get_json=get_json)

    assert len(requests) == 1
    assert result.target == target
    assert len(result.warnings) == 2
    assert all(warning.reason == "access_denied" for warning in result.warnings)
    assert all("secret" not in warning.display_message for warning in result.warnings)


def test_missing_video_does_not_prevent_resolving_another_video():
    target = article_with(parse_rich_text(CARD + CARD.replace("123456789", "987654321")))
    requests = []

    def get_json(url):
        requests.append(url)
        if url.endswith("123456789"):
            raise ZhihuHttpError(404, "not found")
        return PLAYLIST

    result = resolve_embedded_videos(target, get_json=get_json)

    assert len(requests) == 2
    assert len(result.warnings) == 1
    assert isinstance(result.target.blocks[0], EmbeddedVideo)
    assert isinstance(result.target.blocks[1], MediaBlock)


def test_server_wait_requirement_is_preserved_for_optional_video_resolution():
    target = article_with(parse_rich_text(CARD + CARD.replace("123456789", "987654321")))
    requests = []

    def get_json(url):
        requests.append(url)
        raise RetryWaitError("server requested a long wait")

    result = resolve_embedded_videos(target, get_json=get_json)

    assert len(requests) == 1
    assert result.target == target
    assert all(warning.reason == "rate_limited" for warning in result.warnings)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"playlist": {"HD": {"play_url": VIDEO_PAGE, "format": "mp4"}}},
        {"playlist": {"HD": {"play_url": "javascript:alert(1)", "format": "mp4"}}},
        {"playlist": {"HD": {"play_url": "https://vdn1.vzuu.com/video.m3u8"}}},
        {"error": {"code": 403, "message": "secret"}},
        {"error": {"code": [403], "message": "invalid error payload"}},
    ],
)
def test_invalid_lens_payloads_never_turn_pages_or_stream_playlists_into_media(payload):
    target = article_with(parse_rich_text(CARD))

    result = resolve_embedded_videos(target, get_json=lambda _url: payload)

    assert result.target == target
    assert len(result.warnings) == 1


def test_question_and_column_children_are_enriched_without_losing_their_identity():
    article = article_with(parse_rich_text(CARD))
    answer = Answer(
        id="301",
        question=QuestionRef(id="201", title="问题", url="https://www.zhihu.com/question/201"),
        source_url="https://www.zhihu.com/question/201/answer/301",
        author=article.author,
        published_at=None,
        blocks=article.blocks,
    )
    now = datetime(2026, 9, 5, tzinfo=UTC)
    question = QuestionArchive(
        question=Question(id="201", title="问题", source_url=answer.question.url),
        answers=(answer,),
        archived_at=now,
    )
    column = ColumnArchive(
        column=Column(
            "column", "专栏", "https://www.zhihu.com/column/column", "", article.author, 1
        ),
        articles=(article,),
        archived_at=now,
    )

    resolved_question = resolve_embedded_videos(question, get_json=lambda _url: PLAYLIST).target
    resolved_column = resolve_embedded_videos(column, get_json=lambda _url: PLAYLIST).target

    assert isinstance(resolved_question.answers[0].blocks[0], MediaBlock)
    assert isinstance(resolved_column.articles[0].blocks[0], MediaBlock)
    assert replace(resolved_question, answers=question.answers) == question
    assert replace(resolved_column, articles=column.articles) == column


@pytest.mark.parametrize("download", [True, False])
def test_public_workflow_resolves_optional_video_before_writing(tmp_path, download):
    from zhihu_scraper.application import ArchiveWorkflow
    from zhihu_scraper.archive import LocalArchive
    from zhihu_scraper.settings import ArchiveSettings

    class Source:
        def fetch_article_payload(self, _target):
            return {"id": "101", "title": "文章", "content": CARD}

    requests = []

    def get_json(url):
        requests.append(url)
        return PLAYLIST

    report = ArchiveWorkflow(
        source=Source(),
        sink=LocalArchive(tmp_path, media_download=False),
        settings=ArchiveSettings(media_download=download),
        embedded_video_fetcher=get_json,
    ).run("https://zhuanlan.zhihu.com/p/101")

    assert requests == (["https://lens.zhihu.com/api/v4/videos/123456789"] if download else [])
    assert isinstance(report.target.blocks[0], MediaBlock if download else EmbeddedVideo)
    assert VIDEO_PAGE in report.receipt.markdown_path.read_text(encoding="utf-8")
    assert not report.embedded_video_warnings


def test_public_workflow_reports_unavailable_video_and_still_saves_text(tmp_path):
    from zhihu_scraper.application import ArchiveWorkflow
    from zhihu_scraper.archive import LocalArchive
    from zhihu_scraper.settings import ArchiveSettings

    class Source:
        def fetch_article_payload(self, _target):
            return {"id": "101", "title": "文章", "content": f"<p>正文</p>{CARD}"}

    report = ArchiveWorkflow(
        source=Source(),
        sink=LocalArchive(tmp_path, media_download=False),
        settings=ArchiveSettings(),
        embedded_video_fetcher=lambda _url: {},
    ).run("https://zhuanlan.zhihu.com/p/101")

    assert len(report.embedded_video_warnings) == 1
    markdown = report.receipt.markdown_path.read_text(encoding="utf-8")
    assert "正文" in markdown and VIDEO_PAGE in markdown
