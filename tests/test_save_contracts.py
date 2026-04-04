import tempfile
import unittest
from pathlib import Path

from cli.save_contracts import SavePipelineError, SaveRunResult, SavedContentRecord
from cli.save_pipeline import write_creator_metadata
from core.scraper_contracts import CreatorProfileSummary, PaginationStats, ScrapedItem


class SaveContractTests(unittest.TestCase):
    def test_save_run_result_roundtrips_to_legacy_records(self):
        record = SavedContentRecord(
            item=ScrapedItem(
                id="123",
                type="answer",
                url="https://www.zhihu.com/question/1/answer/123",
                title="问题",
                author="作者",
                html="<p>body</p>",
                date="2026-04-03",
            ),
            folder=Path("data/entries/demo--answer-123"),
            markdown_path=Path("data/entries/demo--answer-123/index.md"),
        )
        result = SaveRunResult(
            source_url="https://www.zhihu.com/question/1/answer/123",
            content_root=Path("data/entries"),
            records=(record,),
            collection_id="42",
        )

        legacy = result.to_legacy_records()

        self.assertEqual(result.saved_count, 1)
        self.assertEqual(result.markdown_paths, ("data/entries/demo--answer-123/index.md",))
        self.assertEqual(legacy[0]["item"]["id"], "123")

    def test_write_creator_metadata_accepts_typed_contracts(self):
        creator = CreatorProfileSummary(
            user_id="u-1",
            name="Demo User",
            url_token="demo-user",
            headline="writer",
            description="demo",
            profile_url="https://www.zhihu.com/people/demo-user",
            avatar_url="",
            follower_count=1,
            following_count=2,
            voteup_count=3,
            answer_count=4,
            articles_count=5,
            question_count=6,
            video_count=7,
            column_count=8,
        )
        record = SavedContentRecord(
            item=ScrapedItem(
                id="article-1",
                type="article",
                url="https://zhuanlan.zhihu.com/p/1",
                title="示例标题",
                author="Demo User",
                html="<p>body</p>",
                date="2026-04-03",
            ),
            folder=Path("2026-04-03_demo--article-1"),
            markdown_path=Path("2026-04-03_demo--article-1/index.md"),
        )
        result = SaveRunResult(
            source_url=creator.profile_url,
            content_root=Path("creators/demo-user"),
            records=(record,),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            creator_root = Path(tmpdir) / "creators" / "demo-user"
            article_folder = creator_root / "2026-04-03_demo--article-1"
            article_folder.mkdir(parents=True, exist_ok=True)
            markdown_path = article_folder / "index.md"
            markdown_path.write_text("# demo\n", encoding="utf-8")

            adjusted_result = SaveRunResult(
                source_url=result.source_url,
                content_root=creator_root,
                records=(
                    SavedContentRecord(
                        item=record.item,
                        folder=article_folder,
                        markdown_path=markdown_path,
                    ),
                ),
            )

            write_creator_metadata(
                creator_root,
                creator,
                adjusted_result,
                {
                    "answers": PaginationStats(5, 0, 0, 0, True, False).to_dict(),
                    "articles": PaginationStats(5, 1, 1, 5, True, False).to_dict(),
                },
            )

            creator_readme = (creator_root / "README.md").read_text(encoding="utf-8")
            creator_json = (creator_root / "creator.json").read_text(encoding="utf-8")

            self.assertIn("Saved articles / 已保存专栏: 1", creator_readme)
            self.assertIn("demo-user", creator_json)

    def test_save_pipeline_error_exposes_partial_result(self):
        record = SavedContentRecord(
            item=ScrapedItem(
                id="123",
                type="answer",
                url="https://www.zhihu.com/question/1/answer/123",
                title="问题",
                author="作者",
                html="<p>body</p>",
                date="2026-04-03",
            ),
            folder=Path("data/entries/demo--answer-123"),
            markdown_path=Path("data/entries/demo--answer-123/index.md"),
        )
        partial_result = SaveRunResult(
            source_url="https://www.zhihu.com/question/1/answer/123",
            content_root=Path("data/entries"),
            records=(record,),
        )
        failed_item = ScrapedItem(
            id="124",
            type="article",
            url="https://zhuanlan.zhihu.com/p/124",
            title="失败条目",
            author="作者",
            html="<p>body</p>",
            date="2026-04-03",
        )

        error = SavePipelineError(
            "SQLite save failed after writing Markdown for article:124; 1 item(s) were already archived to disk",
            partial_result=partial_result,
            failed_item=failed_item,
            failed_markdown_path=Path("data/entries/demo--article-124/index.md"),
        )

        self.assertEqual(error.saved_count, 1)
        self.assertEqual(error.partial_result.saved_count, 1)
        self.assertEqual(error.failed_item.id, "124")
        self.assertIn("SQLite save failed", str(error))


if __name__ == "__main__":
    unittest.main()
