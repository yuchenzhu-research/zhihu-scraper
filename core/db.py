import sqlite3
import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from .config import get_logger

class ZhihuDatabase:
    """知乎 SQLite 数据库访问层 (DAL)"""

    def __init__(self, db_path: str = "./data/zhihu.db"):
        self.log = get_logger()
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = self._init_db()

    def _init_db(self) -> sqlite3.Connection:
        """初始化数据库并在必要时建表。"""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        
        # 开启 WAL 模式提升并发读写性能
        conn.execute("PRAGMA journal_mode=WAL")
        
        cursor = conn.cursor()
        # 创建文章表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
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
        # 创建全文索引或普通索引加速查询
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_author ON articles(author)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_collection ON articles(collection_id)")
        
        conn.commit()
        return conn

    def save_article(self, item: Dict[str, Any], content_md: str, collection_id: Optional[str] = None) -> bool:
        """
        保存或更新抓取的文章/回答 (UPSERT)。
        依赖 item 中的 'id' (answer_id/article_id)、'type'、'title'、'author'、'url'。
        """
        answer_id = str(item.get("id", ""))
        if not answer_id:
            return False

        item_type = item.get("type", "unknown")
        title = item.get("title", "Untitled")
        author = item.get("author", "Unknown")
        url = item.get("url", "")
        now = datetime.datetime.now().isoformat()

        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO articles (answer_id, type, title, author, url, content_md, collection_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(answer_id) DO UPDATE SET
                    title = excluded.title,
                    author = excluded.author,
                    url = excluded.url,
                    content_md = excluded.content_md,
                    collection_id = COALESCE(excluded.collection_id, articles.collection_id),
                    updated_at = excluded.updated_at
            """, (answer_id, item_type, title, author, url, content_md, collection_id, now, now))
            self.conn.commit()
            return True
        except Exception as e:
            self.log.error("db_save_failed", answer_id=answer_id, error=str(e))
            self.conn.rollback()
            return False

    def exists(self, answer_id: str) -> bool:
        """检查特定 ID 是否已存在库中。"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM articles WHERE answer_id = ?", (str(answer_id),))
        return cursor.fetchone() is not None

    def search_articles(self, keyword: str, limit: int = 10) -> list:
        """根据标题或内容进行简单模糊搜索"""
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
        if self.conn:
            self.conn.close()
