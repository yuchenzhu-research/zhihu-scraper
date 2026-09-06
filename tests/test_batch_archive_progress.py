import pytest

from zhihu_scraper.application import ArchiveWorkflow, BatchArchiveInterruptedError
from zhihu_scraper.archive import LocalArchive
from zhihu_scraper.domain import Article
from zhihu_scraper.http import TransportError
from zhihu_scraper.media import MediaDownloadReceipt
from zhihu_scraper.render import MarkdownRenderer
from zhihu_scraper.settings import ArchiveSettings, BrowserFallback

COLUMN_URL = "https://www.zhihu.com/column/batch-column"
QUESTION_URL = "https://www.zhihu.com/question/200"


class BatchSource:
    def __init__(self, *, fail_after=None):
        self.fail_after = fail_after
        self.title = "批量专栏"
        self.contents = ["<p>第一篇正文</p>", "<p>第二篇正文</p>"]

    def fetch_column_payload(self, _target):
        return {"id": "batch-column", "title": self.title, "items_count": len(self.contents)}

    def fetch_question_payload(self, _target):
        return {"id": "200", "title": "批量问题", "answer_count": len(self.contents)}

    def iter_column_article_payloads(self, _target, *, page_size):
        for index, content in enumerate(self.contents):
            if self.fail_after == index:
                raise TransportError("request failed, secret must stay private")
            yield {"id": str(index + 1), "title": f"文章{index + 1}", "content": content}

    def iter_question_answer_payloads(self, _target, *, page_size):
        for index, content in enumerate(self.contents):
            if self.fail_after == index:
                raise TransportError("request failed, secret must stay private")
            yield {
                "id": str(index + 1),
                "question": {"id": "200", "title": "批量问题"},
                "author": {"name": f"作者{index + 1}"},
                "content": content,
            }


def workflow(root, source, **options):
    return ArchiveWorkflow(
        source=source,
        sink=LocalArchive(root, media_download=False),
        settings=ArchiveSettings(
            output_dir=root, media_download=False, browser_fallback=BrowserFallback.NEVER
        ),
        **options,
    )


def test_column_failure_keeps_written_articles_and_an_explicit_incomplete_progress_document(
    tmp_path,
):
    with pytest.raises(RuntimeError):
        workflow(tmp_path, BatchSource(fail_after=1)).run(COLUMN_URL)

    progress_files = list(tmp_path.glob("*/归档进度.md"))
    assert len(progress_files) == 1
    progress = progress_files[0].read_text(encoding="utf-8")
    assert "未完成" in progress
    assert "secret" not in progress
    assert COLUMN_URL in progress
    assert "文章1" in progress and "文章2" not in progress
    saved = list(progress_files[0].parent.glob("内容/*.md"))
    assert len(saved) == 1
    assert "第一篇正文" in saved[0].read_text(encoding="utf-8")


def test_rerun_recovers_the_first_interrupted_directory_by_source_id_after_title_change(tmp_path):
    source = BatchSource(fail_after=1)
    with pytest.raises(RuntimeError):
        workflow(tmp_path, source).run(COLUMN_URL)
    original_entry = next(tmp_path.iterdir())
    first_document = next((original_entry / "内容").glob("*.md"))
    source.fail_after = None
    source.title = "专栏更新标题"

    report = workflow(tmp_path, source).run(COLUMN_URL)

    assert report.receipt.entry_directory == original_entry
    assert list(tmp_path.iterdir()) == [original_entry]
    assert first_document in report.receipt.child_markdown_paths
    assert len(report.receipt.child_markdown_paths) == 2
    assert report.receipt.markdown_path.name != "归档进度.md"
    assert "已完成" in report.receipt.progress_path.read_text(encoding="utf-8")


def test_failed_refresh_preserves_the_previous_complete_catalog_and_older_saved_items(tmp_path):
    source = BatchSource()
    complete = workflow(tmp_path, source).run(COLUMN_URL)
    original_catalog = complete.receipt.markdown_path.read_bytes()
    original_second = complete.receipt.child_markdown_paths[1].read_bytes()
    source.fail_after = 1
    source.contents[0] = "<p>第一篇更新后正文</p>"

    with pytest.raises(RuntimeError):
        workflow(tmp_path, source).run(COLUMN_URL)

    assert complete.receipt.markdown_path.read_bytes() == original_catalog
    assert complete.receipt.child_markdown_paths[1].read_bytes() == original_second
    progress = complete.receipt.progress_path.read_text(encoding="utf-8")
    assert "未完成" in progress
    assert "文章2" in progress


def test_question_answers_survive_failure_as_readable_fragments_then_merge_on_success(tmp_path):
    source = BatchSource(fail_after=1)
    with pytest.raises(RuntimeError):
        workflow(tmp_path, source).run(QUESTION_URL)
    entry = next(tmp_path.iterdir())
    fragments = list((entry / "回答片段").glob("*.md"))
    assert len(fragments) == 1
    assert "第一篇正文" in fragments[0].read_text(encoding="utf-8")
    source.fail_after = None

    report = workflow(tmp_path, source).run(QUESTION_URL)

    assert report.receipt.entry_directory == entry
    merged = report.receipt.markdown_path.read_text(encoding="utf-8")
    assert "第一篇正文" in merged and "第二篇正文" in merged
    assert not (entry / "回答片段").exists()
    assert not (entry / "内容").exists()


def test_batch_progress_is_emitted_only_after_items_are_saved(tmp_path):
    progress = []
    source = BatchSource(fail_after=1)
    with pytest.raises(RuntimeError):
        workflow(tmp_path, source, progress=progress.append).run(COLUMN_URL)

    assert [event.stage for event in progress] == ["started", "saved", "interrupted"]
    assert [event.completed for event in progress] == [0, 1, 1]
    assert all(event.total == 2 for event in progress)
    assert progress[1].current_title == "文章1"
    assert progress[-1].progress_path.is_file()


def test_successful_batch_does_not_rerender_all_previous_articles_at_each_checkpoint(
    tmp_path, monkeypatch
):
    source = BatchSource()
    source.contents = [f"<p>正文{index}</p>" for index in range(8)]
    article_renders = []
    original_render = MarkdownRenderer.render

    def render(renderer, target, **options):
        if isinstance(target, Article):
            article_renders.append(target.id)
        return original_render(renderer, target, **options)

    monkeypatch.setattr(MarkdownRenderer, "render", render)
    workflow(tmp_path, source).run(COLUMN_URL)

    assert len(article_renders) <= 2 * len(source.contents)
    assert set(article_renders) == {str(index + 1) for index in range(8)}


def test_final_catalog_reuses_checkpoint_media_without_repeating_downloads(tmp_path):
    source = BatchSource()
    source.contents = [
        f'<p>正文</p><img src="https://pic.example/{index}.jpg">' for index in range(2)
    ]
    downloads = []

    def downloader(source_url, destination, *, expected_size=None):
        downloads.append(source_url)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"image")
        return MediaDownloadReceipt(source_url, destination, 0, 5)

    report = ArchiveWorkflow(
        source=source,
        sink=LocalArchive(tmp_path, downloader=downloader),
        settings=ArchiveSettings(output_dir=tmp_path, browser_fallback=BrowserFallback.NEVER),
    ).run(COLUMN_URL)

    assert downloads == ["https://pic.example/0.jpg", "https://pic.example/1.jpg"]
    assert len(report.media_failures) == 0
    assert len(report.receipt.media_downloads) == 2


def test_question_progress_does_not_claim_removed_answers_still_exist_in_the_replaced_document(
    tmp_path,
):
    source = BatchSource()
    workflow(tmp_path, source).run(QUESTION_URL)
    source.contents = source.contents[:1]

    report = workflow(tmp_path, source).run(QUESTION_URL)

    progress = report.receipt.progress_path.read_text(encoding="utf-8")
    assert "/answer/1" in progress
    assert "/answer/2" not in progress
    assert "第二篇正文" not in report.receipt.markdown_path.read_text(encoding="utf-8")


@pytest.mark.parametrize("failure", [OSError("original disk failure"), KeyboardInterrupt()])
def test_progress_update_failure_cannot_mask_the_original_interruption(
    tmp_path, monkeypatch, failure
):
    from zhihu_scraper.archive import LocalArchiveBatch

    source = BatchSource()

    def fail_items(_target, *, page_size):
        yield {"id": "1", "title": "已保存", "content": "<p>正文</p>"}
        raise failure

    def fail_progress(_batch):
        raise PermissionError("secondary progress failure")

    source.iter_column_article_payloads = fail_items
    monkeypatch.setattr(LocalArchiveBatch, "interrupt", fail_progress)
    if isinstance(failure, KeyboardInterrupt):
        with pytest.raises(KeyboardInterrupt) as caught:
            workflow(tmp_path, source).run(COLUMN_URL)
        assert caught.value is failure
    else:
        with pytest.raises(BatchArchiveInterruptedError) as caught:
            workflow(tmp_path, source).run(COLUMN_URL)
        assert caught.value.__cause__ is failure
        assert not caught.value.progress_saved
    assert len(list(tmp_path.glob("*/内容/*.md"))) == 1


def test_interruption_observer_failure_preserves_the_original_error_and_saved_progress(tmp_path):
    def notify(event):
        if event.stage == "interrupted":
            raise RuntimeError("progress observer failed")

    with pytest.raises(BatchArchiveInterruptedError) as caught:
        workflow(tmp_path, BatchSource(fail_after=1), progress=notify).run(COLUMN_URL)

    assert isinstance(caught.value.__cause__, TransportError)
    assert caught.value.progress_saved
    assert caught.value.receipt.progress_path.is_file()
