import json
from pathlib import Path
from typing import List, Optional

from .config import get_logger
from .api_client import ZhihuAPIClient

class CollectionMonitor:
    """监控知乎收藏夹，实现增量抓取。"""

    def __init__(self, data_dir: str = "./data"):
        self.log = get_logger()
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_dir / ".monitor_state.json"
        
        self.state = self._load_state()
        self.api_client = ZhihuAPIClient()

    def _load_state(self) -> dict:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                self.log.warning("load_monitor_state_failed", error=str(e))
        return {}

    def _save_state(self):
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self.log.error("save_monitor_state_failed", error=str(e))

    def get_new_items(self, collection_id: str) -> List[dict]:
        """
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
            print(f"📡 正在拉取收藏夹第 {offset // limit + 1} 页数据...")
            
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
                
                # 记录这轮抓取遇到的第一个ID，由于知乎收藏夹通常按时间倒序（最新的在最前）
                # 这个ID就是下一次增量抓取时我们要对比的 stop sign
                if first_item_id_in_this_run is None:
                    first_item_id_in_this_run = item_id

                # 如果遇到已知的 last_id，说明后面的内容全部已经处理过了，提前结束！
                if known_last_id and item_id == known_last_id:
                    self.log.info("hit_known_item_stopping", id=item_id)
                    print("🛑 遇到已知记录，增量检测结束。")
                    is_end = True
                    break
                    
                # 过滤出支持抓取的内容类型 (主要是回答和专栏文章，如果以后支持文章的话)
                # 目前阶段一已确认回答接口 /v4/answers 正常，文章需要通过 URL fallback
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
        print(f"✨ 发现 {len(new_items)} 个新增内容！")
        
        # 暂时不保存状态，待外部完全抓取成功后再调用 mark_updated 保存状态
        return new_items, first_item_id_in_this_run
        
    def mark_updated(self, collection_id: str, new_last_id: Optional[str]):
        """在抓取成功完成后，更新状态文件。"""
        if new_last_id:
            self.state[str(collection_id)] = str(new_last_id)
            self._save_state()
            self.log.info("state_updated", collection_id=collection_id, new_last_id=new_last_id)
