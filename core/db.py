"""
db.py - SQLite Database Access Layer

Provides persistent storage for scraped Zhihu content.
Supports UPSERT operations, full-text search, and collection management.

================================================================================
db.py — SQLite 数据库访问层 (DAL)

提供知乎抓取内容的持久化存储。
支持 UPSERT 操作、全文搜索和收藏夹管理。
================================================================================
"""

import sqlite3
import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from .config import get_logger


class ZhihuDatabase:
    """
    Chinese: 知乎 SQLite 数据库访问层 (DAL)
    English: Zhihu SQLite Database Access Layer (DAL)
    """

    def __init__(self, db_path: str = "./data/zhihu.db"):
        self.log = get_logger()
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = self._init_db()

    def _init_db(self) -> sqlite3.Connection:
        """
        Initialize database and create tables if needed
        初始化数据库并在必要时建表
        """
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row

        # Enable WAL mode for better concurrent read/write performance
        # 开启 WAL 模式提升并发读写性能
        conn.execute("PRAGMA journal_mode=WAL")

        cursor = conn.cursor()

        self._ensure_articles_schema(cursor)

        conn.commit()
        return conn

    def _ensure_articles_schema(self, cursor: sqlite3.Cursor) -> None:
        """
        Create or migrate the articles table to the current content-key schema.
        创建或迁移 articles 表到当前的 content_key 模型。
        """
        row = cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='articles'"
        ).fetchone()
        if row is None:
            self._create_articles_table(cursor)
            self._create_indexes(cursor)
            return

        table_sql = row["sql"] or ""
        if "content_key" not in table_sql or "answer_id TEXT UNIQUE" in table_sql:
            self._migrate_articles_table(cursor)

        self._create_indexes(cursor)

    @staticmethod
    def _create_articles_table(cursor: sqlite3.Cursor) -> None:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                answer_id TEXT NOT NULL,
                content_key TEXT UNIQUE NOT NULL,
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

    @staticmethod
    def _create_indexes(cursor: sqlite3.Cursor) -> None:
        # Create indexes for query acceleration
        # 创建全文索引或普通索引加速查询
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_answer_id ON articles(answer_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_author ON articles(author)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_collection ON articles(collection_id)")

    def _migrate_articles_table(self, cursor: sqlite3.Cursor) -> None:
        """
        Migrate legacy `answer_id UNIQUE` schema to `content_key = type:id`.
        将旧的 `answer_id UNIQUE` 结构迁移到 `content_key = type:id`。
        """
        cursor.execute("ALTER TABLE articles RENAME TO articles_legacy")
        legacy_columns = {
            row["name"] for row in cursor.execute("PRAGMA table_info(articles_legacy)").fetchall()
        }

        content_key_expr = (
            "COALESCE(NULLIF(content_key, ''), CASE "
            "WHEN COALESCE(type, '') <> '' AND COALESCE(answer_id, '') <> '' "
            "THEN type || ':' || answer_id ELSE answer_id END)"
            if "content_key" in legacy_columns
            else "CASE WHEN COALESCE(type, '') <> '' AND COALESCE(answer_id, '') <> '' THEN type || ':' || answer_id ELSE answer_id END"
        )

        self._create_articles_table(cursor)
        cursor.execute(f"""
            INSERT INTO articles (
                answer_id,
                content_key,
                type,
                title,
                author,
                url,
                content_md,
                collection_id,
                created_at,
                updated_at
            )
            SELECT
                answer_id,
                {content_key_expr},
                COALESCE(type, 'unknown'),
                title,
                author,
                url,
                content_md,
                collection_id,
                COALESCE(created_at, CURRENT_TIMESTAMP),
                COALESCE(updated_at, CURRENT_TIMESTAMP)
            FROM articles_legacy
        """)
        cursor.execute("DROP TABLE articles_legacy")

    def save_article(self, item: Dict[str, Any], content_md: str, collection_id: Optional[str] = None) -> bool:
        """
        Save or update scraped article/answer (UPSERT).
        Relies on 'id', 'type', 'title', 'author', 'url' in item.

        保存或更新抓取的文章/回答 (UPSERT)。
        依赖 item 中的 'id' (answer_id/article_id)、'type'、'title'、'author'、'url'。
        """
        answer_id = str(item.get("id", ""))
        if not answer_id:
            return False

        item_type = str(item.get("type", "unknown") or "unknown")
        content_key = f"{item_type}:{answer_id}"
        title = item.get("title", "Untitled")
        author = item.get("author", "Unknown")
        url = item.get("url", "")
        now = datetime.datetime.now().isoformat()

        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO articles (answer_id, content_key, type, title, author, url, content_md, collection_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(content_key) DO UPDATE SET
                    title = excluded.title,
                    author = excluded.author,
                    url = excluded.url,
                    content_md = excluded.content_md,
                    collection_id = COALESCE(excluded.collection_id, articles.collection_id),
                    updated_at = excluded.updated_at
            """, (answer_id, content_key, item_type, title, author, url, content_md, collection_id, now, now))
            self.conn.commit()
            return True
        except Exception as e:
            self.log.error("db_save_failed", answer_id=answer_id, content_key=content_key, error=str(e))
            self.conn.rollback()
            return False

    def exists(self, answer_id: str, item_type: Optional[str] = None) -> bool:
        """
        Check if specific ID already exists in database
        检查特定 ID 是否已存在库中
        """
        cursor = self.conn.cursor()
        if item_type:
            cursor.execute(
                "SELECT 1 FROM articles WHERE content_key = ?",
                (f"{item_type}:{answer_id}",),
            )
        else:
            cursor.execute("SELECT 1 FROM articles WHERE answer_id = ?", (str(answer_id),))
        return cursor.fetchone() is not None

    def search_articles(self, keyword: str, limit: int = 10) -> list:
        """
        Simple fuzzy search by title or content
        根据标题或内容进行简单模糊搜索
        """
        cursor = self.conn.cursor()
        search_term = f"%{keyword}%"
        cursor.execute("""
            SELECT answer_id, type, title, author, url, created_at
            FROM articles
            WHERE title LIKE ? OR content_md LIKE ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (search_term, search_term, limit))
        return [dict(row) for row in cursor.fetchall()]

    def close(self):
        """Close database connection / 关闭数据库连接"""
        if self.conn:
            self.conn.close()
