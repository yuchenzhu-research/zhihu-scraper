from urllib.parse import parse_qs, urlsplit

import pytest

from zhihu_scraper.cli import run_cli
from zhihu_scraper.http import RateLimitError

QUESTION_URL = "https://www.zhihu.com/question/200"
QUESTION = {"id": 200, "title": "大问题", "answer_count": 10040}


def answer(answer_id, body):
    return {
        "id": answer_id,
        "question": QUESTION,
        "content": f"<p>{body}</p>",
        "author": {"name": f"作者{answer_id}"},
    }


def page(*items, next_offset=None):
    return {
        "data": list(items),
        "paging": {
            "is_end": next_offset is None,
            "next": (
                "" if next_offset is None else f"/api/v4/questions/200/answers?offset={next_offset}"
            ),
        },
    }


class Client:
    def __init__(self, pages):
        self.pages = pages
        self.offsets = []
        self.requests = []

    def get_json(self, url):
        self.requests.append(url)
        parsed = urlsplit(url)
        if parsed.path == "/api/v4/questions/200":
            return QUESTION
        assert parsed.path == "/api/v4/questions/200/answers"
        offset = int(parse_qs(parsed.query)["offset"][0])
        self.offsets.append(offset)
        response = self.pages[offset]
        if isinstance(response, Exception):
            raise response
        return response

    def close(self):
        pass


def fetch(monkeypatch, root, client, *args, url=QUESTION_URL):
    monkeypatch.setattr("zhihu_scraper.facade.ZhihuHttpClient", lambda **kwargs: client)
    return run_cli(["fetch", url, "-o", str(root), "--no-media", "--browser", "never", *args])


def test_offset_resumes_legacy_fragments_without_refetching_or_overwriting(
    monkeypatch, tmp_path, capsys
):
    original = Client(
        {0: page(answer(301, "原有回答"), next_offset=1), 1: RateLimitError(429, "limited")}
    )
    assert fetch(monkeypatch, tmp_path, original) == 1
    entry = next(tmp_path.iterdir())
    legacy = next(entry.glob("回答片段/*.md"))
    previous_body = legacy.read_bytes()
    previous_progress = entry / "归档进度.md"
    # A fragment may have landed before the old process could append its index row.
    previous_progress.write_text(
        "# 归档进度\n\n> 知乎原问题：[原问题](https://www.zhihu.com/question/200)\n",
        encoding="utf-8",
    )
    previous_index = previous_progress.read_bytes()
    capsys.readouterr()

    resumed = Client(
        {9980: page({"id": 301}, next_offset=10000), 10000: page(answer(302, "新回答"))}
    )
    assert fetch(monkeypatch, tmp_path, resumed, "--offset", "9980") == 0

    assert resumed.offsets == [9980, 10000]
    assert legacy.read_bytes() == previous_body
    assert previous_progress.read_bytes() == previous_index
    fragments = sorted(entry.glob("回答片段/*.md"))
    assert len(fragments) == 2
    assert any("新回答" in path.read_text(encoding="utf-8") for path in fragments)
    index = (entry / "续抓进度.md").read_text(encoding="utf-8")
    assert "offset=9980" in index
    assert "不代表完整归档" in index
    assert "/answer/301" in index and "/answer/302" in index
    assert not (entry / "大问题.md").exists()
    stdout = capsys.readouterr().out
    assert "续抓结束" in stdout
    assert "归档完成" not in stdout


def test_offset_keeps_a_previous_complete_document_untouched(monkeypatch, tmp_path, capsys):
    assert fetch(monkeypatch, tmp_path, Client({0: page(answer(301, "完整版本"))})) == 0
    entry = next(tmp_path.iterdir())
    full = entry / "大问题.md"
    original_body = full.read_bytes()
    capsys.readouterr()

    assert (
        fetch(
            monkeypatch, tmp_path, Client({10000: page(answer(302, "后半段"))}), "--offset", "10000"
        )
        == 0
    )

    assert full.read_bytes() == original_body
    assert len(list(entry.glob("回答片段/*.md"))) == 1
    assert (entry / "续抓进度.md").is_file()


def test_new_offset_archive_and_interrupted_resume_are_marked_as_partial(
    monkeypatch, tmp_path, capsys
):
    interrupted = Client(
        {
            10000: page(answer(302, "后半段"), next_offset=10020),
            10020: RateLimitError(429, "limited"),
        }
    )
    assert fetch(monkeypatch, tmp_path, interrupted, "--offset", "10000") == 1
    entry = next(tmp_path.iterdir())
    progress = entry / "续抓进度.md"
    text = progress.read_text(encoding="utf-8")
    assert "offset=10000" in text and "中断" in text
    assert "/answer/302" in text

    exhausted = Client({10020: page()})
    assert fetch(monkeypatch, tmp_path, exhausted, "--offset", "10020") == 0
    text = progress.read_text(encoding="utf-8")
    assert "offset=10020" in text and "不代表完整归档" in text
    assert "/answer/302" in text
    assert list(tmp_path.iterdir()) == [entry]
    assert "续抓结束" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("url", "flags", "message"),
    [
        (QUESTION_URL, ["--offset", "-1"], "非负整数"),
        ("https://www.zhihu.com/column/demo", ["--offset", "20"], "仅支持问题链接"),
        (QUESTION_URL, ["--offset", "20", "--html"], "只支持 Markdown"),
        (QUESTION_URL, ["--offset", "20", "--pdf"], "只支持 Markdown"),
    ],
)
def test_invalid_offset_combinations_fail_without_requests(
    monkeypatch, tmp_path, capsys, url, flags, message
):
    client = Client({})
    assert fetch(monkeypatch, tmp_path, client, *flags, url=url) == 1
    assert not client.requests
    assert not list(tmp_path.iterdir())
    assert message in capsys.readouterr().err
