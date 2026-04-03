import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.db import ZhihuDatabase


class DatabaseContractTests(unittest.TestCase):
    def test_content_key_allows_same_numeric_id_for_different_item_types(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db = ZhihuDatabase(str(Path(tmpdir) / "zhihu.db"))

            self.assertTrue(
                db.save_article(
                    {
                        "id": "42",
                        "type": "answer",
                        "title": "Answer",
                        "author": "Demo",
                        "url": "https://www.zhihu.com/question/1/answer/42",
                    },
                    "answer body",
                )
            )
            self.assertTrue(
                db.save_article(
                    {
                        "id": "42",
                        "type": "article",
                        "title": "Article",
                        "author": "Demo",
                        "url": "https://zhuanlan.zhihu.com/p/42",
                    },
                    "article body",
                )
            )

            rows = db.conn.execute(
                "SELECT answer_id, type, content_key FROM articles ORDER BY type ASC"
            ).fetchall()
            db.close()

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["content_key"], "answer:42")
        self.assertEqual(rows[1]["content_key"], "article:42")

    def test_existing_schema_is_migrated_to_content_key_layout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "zhihu.db"
            conn = sqlite3.connect(str(db_path))
            conn.execute("""
                CREATE TABLE articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    answer_id TEXT UNIQUE NOT NULL,
                    type TEXT NOT NULL,
                    title TEXT,
                    author TEXT,
                    url TEXT,
                    content_md TEXT,
                    collection_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute(
                """
                INSERT INTO articles (
                    answer_id, type, title, author, url, content_md, collection_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "7",
                    "answer",
                    "Legacy row",
                    "Demo",
                    "https://www.zhihu.com/question/1/answer/7",
                    "legacy body",
                    None,
                    "2026-04-03T00:00:00",
                    "2026-04-03T00:00:00",
                ),
            )
            conn.commit()
            conn.close()

            db = ZhihuDatabase(str(db_path))
            columns = [
                row["name"] for row in db.conn.execute("PRAGMA table_info(articles)").fetchall()
            ]
            row = db.conn.execute(
                "SELECT answer_id, type, content_key, title FROM articles"
            ).fetchone()

            self.assertIn("content_key", columns)
            self.assertEqual(row["content_key"], "answer:7")
            self.assertEqual(row["title"], "Legacy row")
            self.assertTrue(
                db.save_article(
                    {
                        "id": "7",
                        "type": "article",
                        "title": "New article row",
                        "author": "Demo",
                        "url": "https://zhuanlan.zhihu.com/p/7",
                    },
                    "article body",
                )
            )

            count = db.conn.execute("SELECT COUNT(*) AS c FROM articles").fetchone()["c"]
            db.close()

        self.assertEqual(count, 2)


if __name__ == "__main__":
    unittest.main()
