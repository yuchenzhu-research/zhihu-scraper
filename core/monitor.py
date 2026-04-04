"""
monitor.py - Collection Monitor for Incremental Scraping

Monitors Zhihu collections and implements incremental fetching.
Uses state file to track last processed item ID, only fetching new content.

================================================================================
monitor.py — 收藏夹增量监控模块

监控知乎收藏夹，实现增量抓取。
使用状态文件跟踪最后处理的项 ID，仅抓取新内容。
================================================================================
"""

import json
from pathlib import Path
from typing import List, Optional, Tuple

from .config import get_logger
from .api_client import ZhihuAPIClient


class CollectionMonitor:
    """
    Chinese: 监控知乎收藏夹，实现增量抓取
    English: Monitor Zhihu collections and implement incremental fetching
    """

    def __init__(self, data_dir: str = "./data"):
        self.log = get_logger()
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_dir / ".monitor_state.json"

        self.state = self._load_state()
        self.api_client = ZhihuAPIClient()

    def _load_state(self) -> dict:
        """
        Load monitoring state from file
        从文件加载监控状态
        """
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                self.log.warning("load_monitor_state_failed", error=str(e))
        return {}

    def _save_state(self):
        """
        Save monitoring state to file
        保存监控状态到文件
        """
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self.log.error("save_monitor_state_failed", error=str(e))

    def get_new_items(self, collection_id: str) -> Tuple[List[dict], Optional[str]]:
        """
        Get new items from collection.
        Returned data structure contains basic info needed for scraping: url, type, title, etc.

        获取收藏夹中的新增内容。
        返回的数据结构包含抓取所需的基本信息，如 url, type, title 等。
        """
        known_last_id = self.state.get(str(collection_id))
        self.log.info("check_collection", collection_id=collection_id, known_last_id=known_last_id)

        offset = 0
        limit = 20
        new_items = []
        is_end = False

        first_item_id_in_this_run = None

        while not is_end:
            self.log.info("fetch_collection_page", offset=offset, limit=limit)
            print(f"📡 Fetching collection page {offset // limit + 1}...")

            data = self.api_client.get_collection_page(collection_id, limit=limit, offset=offset)
            items = data.get("data", [])
            paging = data.get("paging", {})
            is_end = paging.get("is_end", True)

            if not items:
                break

            for item in items:
                content = item.get("content", {})
                item_type = content.get("type")
                item_id = str(content.get("id", ""))

                # Record the first ID encountered in this run.
                # Since Zhihu collections are usually in reverse chronological order (newest first),
                # this ID becomes the stop sign for the next incremental fetch.
                # 记录这轮抓取遇到的第一个ID，由于知乎收藏夹通常按时间倒序（最新的在最前）
                # 这个ID就是下一次增量抓取时我们要对比的 stop sign
                if first_item_id_in_this_run is None:
                    first_item_id_in_this_run = item_id

                # If we encounter the known last_id, all subsequent content has been processed
                # 如果遇到已知的 last_id，说明后面的内容全部已经处理过了，提前结束！
                if known_last_id and item_id == known_last_id:
                    self.log.info("hit_known_item_stopping", id=item_id)
                    print("🛑 Encountered known record, incremental check complete")
                    is_end = True
                    break

                # Filter content types that support scraping (mainly answers and column articles)
                # 过滤出支持抓取的内容类型 (主要是回答和专栏文章)
                url = ""
                if item_type == "answer":
                    question_id = content.get("question", {}).get("id")
                    url = f"https://www.zhihu.com/question/{question_id}/answer/{item_id}"
                elif item_type == "article":
                    url = f"https://zhuanlan.zhihu.com/p/{item_id}"

                if url:
                    new_items.append({
                        "id": item_id,
                        "type": item_type,
                        "url": url,
                        "title": content.get("question", {}).get("title") if item_type == "answer" else content.get("title", "Unknown")
                    })

            offset += limit

        self.log.info("collection_delta_found", count=len(new_items))
        print(f"✨ Found {len(new_items)} new items!")

        # Don't save state yet, wait for external complete fetch then call mark_updated
        # 暂时不保存状态，待外部完全抓取成功后再调用 mark_updated 保存状态
        return new_items, first_item_id_in_this_run

    def mark_updated(self, collection_id: str, new_last_id: Optional[str]):
        """
        Update state file after successful fetch
        在抓取成功完成后，更新状态文件
        """
        if new_last_id:
            self.state[str(collection_id)] = str(new_last_id)
            self._save_state()
            self.log.info("state_updated", collection_id=collection_id, new_last_id=new_last_id)
