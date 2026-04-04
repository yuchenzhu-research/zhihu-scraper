import json
import tempfile
import unittest
from pathlib import Path

from cli.save_pipeline import (
    build_output_folder_name,
    resolve_creator_output_dir,
    resolve_entries_output_dir,
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
                    "headline": "writer",
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
            self.assertIn("## Summary / 概览", creator_readme)
            self.assertIn("[index.md](2026-04-03_demo--article-1/index.md)", creator_readme)


if __name__ == "__main__":
    unittest.main()
