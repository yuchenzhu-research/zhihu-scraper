import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cli.creator_metadata import _normalize_creator_text
from cli.save_contracts import SavePipelineError
from cli.save_pipeline import (
    SavePipelineSettings,
    build_output_folder_name,
    resolve_creator_output_dir,
    resolve_entries_output_dir,
    save_items_result,
    write_creator_metadata,
)


class OutputPathTests(unittest.TestCase):
    def test_build_output_folder_name_keeps_suffix_and_shell_safe(self):
        folder = build_output_folder_name(
            "2026-03-31",
            "如何看待伊朗驻华大使馆认为日本是二战受害者？",
            "玄睛",
            "answer-2022365612303741181",
            folder_template="[{date}] {title}",
        )
        self.assertIn("2026-03-31", folder)
        self.assertIn("answer-2022365612303741181", folder)
        self.assertNotIn("[", folder)
        self.assertNotIn("]", folder)
        self.assertNotIn("(", folder)
        self.assertNotIn(")", folder)
        self.assertNotIn(" ", folder)

    def test_entries_output_dir_only_appends_entries_once(self):
        self.assertEqual(resolve_entries_output_dir(Path("data")), Path("data/entries"))
        self.assertEqual(resolve_entries_output_dir(Path("entries")), Path("entries"))

    def test_creator_output_dir_places_content_under_creators(self):
        self.assertEqual(
            resolve_creator_output_dir(Path("data"), "hu-xi-jin"),
            Path("data/creators/hu-xi-jin"),
        )


class CreatorMetadataTests(unittest.TestCase):
    def test_write_creator_metadata_emits_json_and_readme(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            creator_root = Path(tmpdir) / "creators" / "demo-user"
            creator_root.mkdir(parents=True, exist_ok=True)
            article_folder = creator_root / "2026-04-03_demo--article-1"
            article_folder.mkdir(parents=True, exist_ok=True)
            markdown_path = article_folder / "index.md"
            markdown_path.write_text("# demo\n", encoding="utf-8")

            write_creator_metadata(
                creator_root,
                {
                    "user_id": "u-1",
                    "name": "Demo User",
                    "url_token": "demo-user",
                    "profile_url": "https://www.zhihu.com/people/demo-user",
                    "headline": "https://example.com/",
                    "description": '<a href="https://link.zhihu.com/?target=https%3A//example.com/" class="external"><span>example</span></a>',
                },
                [
                    {
                        "item": {
                            "id": "1",
                            "type": "article",
                            "title": "示例标题",
                            "date": "2026-04-03",
                            "url": "https://zhuanlan.zhihu.com/p/1",
                        },
                        "folder": article_folder,
                        "markdown_path": markdown_path,
                    }
                ],
                sync_info={"articles": {"requested_limit": 5, "saved_count": 1}},
            )

            creator_json = json.loads((creator_root / "creator.json").read_text(encoding="utf-8"))
            creator_readme = (creator_root / "README.md").read_text(encoding="utf-8")

            self.assertEqual(creator_json["url_token"], "demo-user")
            self.assertEqual(creator_json["saved_articles"], 1)
            self.assertEqual(creator_json["description"], "https://example.com/")
            self.assertIn("## Summary / 概览", creator_readme)
            self.assertIn("> **Headline / 简介**: https://example.com/", creator_readme)
            self.assertNotIn("> **Description / 描述**:", creator_readme)
            self.assertNotIn("<a href=", creator_readme)
            self.assertIn("[index.md](2026-04-03_demo--article-1/index.md)", creator_readme)

    def test_normalize_creator_text_collapses_html_and_whitespace(self):
        self.assertEqual(
            _normalize_creator_text(
                '<div>  graphics   researcher <a href="https://link.zhihu.com/?target=https%3A//example.com/">link</a></div>'
            ),
            "graphics researcher https://example.com/",
        )


class SavePipelineFailureTests(unittest.TestCase):
    def test_save_items_result_raises_typed_error_with_partial_context(self):
        class FailingDb:
            def __init__(self, *_args, **_kwargs):
                self.closed = False
                self.calls = 0

            def save_article(self, *_args, **_kwargs):
                self.calls += 1
                return self.calls == 1

            def close(self):
                self.closed = True

        items = [
            {
                "id": "42",
                "type": "answer",
                "url": "https://www.zhihu.com/question/1/answer/42",
                "title": "Demo",
                "author": "Tester",
                "html": "<p>hello</p>",
                "date": "2026-04-03",
            },
            {
                "id": "43",
                "type": "article",
                "url": "https://zhuanlan.zhihu.com/p/43",
                "title": "Second",
                "author": "Tester",
                "html": "<p>world</p>",
                "date": "2026-04-03",
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            settings = SavePipelineSettings(
                folder_template="[{date}] {title}",
                images_subdir="images",
                image_concurrency=4,
                image_timeout=30,
            )
            with patch("cli.save_pipeline.ZhihuDatabase", FailingDb):
                with self.assertRaises(SavePipelineError) as captured:
                    asyncio.run(
                        save_items_result(
                            items=items,
                            content_root=Path(tmpdir) / "entries",
                            db_root=Path(tmpdir),
                            settings=settings,
                            download_images=False,
                            source_url_fallback=items[0]["url"],
                            printer=lambda *_args, **_kwargs: None,
                        )
                    )
                error = captured.exception
                self.assertEqual(error.saved_count, 1)
                self.assertEqual(error.partial_result.saved_count, 1)
                self.assertEqual(error.failed_item.id, "43")
                self.assertTrue(error.failed_markdown_path.exists())
                self.assertIn("SQLite save failed", str(error))
                self.assertIn("1 item(s) were already archived to disk", str(error))


if __name__ == "__main__":
    unittest.main()
