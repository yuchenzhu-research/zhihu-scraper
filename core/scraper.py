"""
scraper.py — 知乎页面抓取 & 图片下载模块 (v3.0 纯协议引擎 API 版)

免责声明：
本项目仅供学术研究和学习交流使用，请勿用于任何商业用途。
使用者应遵守知乎的相关服务协议和 robots.txt 协议。

集成纯协议层网络客户端，直接基于 v4 API 抓取。
大幅度降低对 CPU 和内存的消耗，防封核心依赖于 TLS 指纹模拟 (curl_cffi)。
"""

import asyncio
from typing import Union, List, Optional
import httpx
from pathlib import Path
import re
from datetime import datetime

from .config import get_logger, get_humanizer
from .api_client import ZhihuAPIClient

class ZhihuDownloader:
    """从知乎文章/回答页面直接抓取 API 数据并下载图片到本地。"""

    def __init__(self, url: str) -> None:
        self.url = url.split("?")[0]
        self.page_type = self._detect_type()
        self.api_client = ZhihuAPIClient()
        self.log = get_logger()

    def _detect_type(self) -> str:
        if "zhuanlan.zhihu.com" in self.url:
            return "article"
        if "/answer/" in self.url:
            return "answer"
        if "/question/" in self.url:
            return "question"
        return "article"

    def has_valid_cookies(self) -> bool:
        """检查是否有有效 Cookie (兼容 CLI 调用)。"""
        return bool(self.api_client._cookies_dict)

    async def fetch_page(self, **kwargs) -> Union[dict, List[dict]]:
        """
        使用纯协议层抓取页面数据。
        支持传入 kwargs (如 start, limit) 传递给 _extract_question。
        注意：目前已经是轻量级代码，但为了兼容 v2.0 的协程外壳，方法签名保留 async。
        """
        humanizer = get_humanizer()
        
        self.log.info("start_fetching", url=self.url, page_type=self.page_type)
        print(f"🌍 访问 [API 模式]: {self.url}")
        
        # 模拟部分延时，以避免瞬时高频请求
        await humanizer.page_load()

        if self.page_type == "article":
            return self._extract_article()
        elif self.page_type == "question":
            return self._extract_question(**kwargs)
        else:
            return self._extract_answer()

    def _extract_article(self) -> dict:
        """提取专栏文章数据。"""
        # 从 URL 提取 Article ID
        # e.g., https://zhuanlan.zhihu.com/p/123456
        match = re.search(r"p/(\d+)", self.url)
        if not match:
             raise Exception(f"无法从专栏 URL 提取 ID: {self.url}")
        
        article_id = match.group(1)
        data = self.api_client.get_article(article_id)
        
        author = data.get("author", {}).get("name", "未知作者")
        title = data.get("title", "未知专栏标题")
        html = data.get("content", "")
        upvotes = data.get("voteup_count", 0)
        
        # 将 timestamp 转为日历格式
        created_sec = data.get("created", 0)
        date_str = datetime.fromtimestamp(created_sec).strftime("%Y-%m-%d") if created_sec else datetime.today().strftime("%Y-%m-%d")

        # 挂载头图
        title_img = data.get("image_url")
        if title_img:
            html = f'<img src="{title_img}" alt="TitleImage"><br>{html}'

        return {
            "id": article_id,
            "type": "article",
            "url": self.url,
            "title": title.strip(), 
            "author": author.strip(), 
            "html": html, 
            "date": date_str,
            "upvotes": upvotes
        }

    def _extract_answer(self) -> dict:
        """提取单个回答数据。"""
        # https://www.zhihu.com/question/298203515/answer/2008258573281562692
        match = re.search(r"answer/(\d+)", self.url)
        if not match:
             raise Exception(f"无法从回答 URL 提取 ID: {self.url}")
             
        answer_id = match.group(1)
        data = self.api_client.get_answer(answer_id)
        
        author = data.get("author", {}).get("name", "未知作者")
        title = data.get("question", {}).get("title", "未知问题")
        html = data.get("content", "")
        upvotes = data.get("voteup_count", 0)
        
        created_sec = data.get("created_time", 0)
        date_str = datetime.fromtimestamp(created_sec).strftime("%Y-%m-%d") if created_sec else datetime.today().strftime("%Y-%m-%d")

        return {
            "id": answer_id,
            "type": "answer",
            "url": self.url,
            "title": title.strip(), 
            "author": author.strip(), 
            "html": html, 
            "date": date_str,
            "upvotes": upvotes
        }

    def _extract_question(self, start: int = 0, limit: int = 3, **kwargs) -> List[dict]:
        """提取问题下的多个回答。利用 API 分页直接获取，无视 DOM 滚动。"""
        match = re.search(r"question/(\d+)", self.url)
        if not match:
             raise Exception(f"无法从问题 URL 提取 ID: {self.url}")
             
        question_id = match.group(1)
        
        # 为了防封，可以一次拿一页（如 limit=20 内），如果你需要很多，需要在这里循环
        # 如果 limit 很大，建议使用 for 循环带 delay 分页拿
        print(f"🎯 目标: API 抓取问题 {question_id} 的前 {limit} 个回答 (从第 {start} 只开始)")
        
        answers_data = self.api_client.get_question_answers(question_id, limit=limit, offset=start)
        
        results = []
        for data in answers_data:
            author = data.get("author", {}).get("name", "未知作者")
            title = data.get("question", {}).get("title", "未知问题")
            html = data.get("content", "")
            upvotes = data.get("voteup_count", 0)
            
            created_sec = data.get("created_time", 0)
            date_str = datetime.fromtimestamp(created_sec).strftime("%Y-%m-%d") if created_sec else datetime.today().strftime("%Y-%m-%d")

            results.append({
                "id": str(data.get("id", "")),
                "type": "answer",
                "url": f"https://www.zhihu.com/question/{question_id}/answer/{data.get('id', '')}",
                "title": title.strip(), 
                "author": author.strip(), 
                "html": html, 
                "date": date_str,
                "upvotes": upvotes
            })
            
        print(f"✅ 成功命中 {len(results)} 个回答。")
        return results

    # ── 图片下载 ──────────────────────────────────────────────
    @classmethod
    async def download_images(
        cls,
        img_urls: List[str],
        dest: Path,
        *,
        concurrency: int = 4,
        timeout: float = 30.0,
    ) -> dict[str, str]:
        """
        并发下载图片 (保持使用轻量的 httpx 客户端进行基础资源下载)
        """
        if not img_urls:
            return {}

        dest.mkdir(parents=True, exist_ok=True)
        url_to_local: dict[str, str] = {}
        sem = asyncio.Semaphore(concurrency)
        client = httpx.AsyncClient(headers={
            "Referer": "https://www.zhihu.com/",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        })

        async def worker(url: str):
            async with sem:
                try:
                    # 获取文件名
                    file_name = url.split("/")[-1]
                    if "?" in file_name:
                        file_name = file_name.split("?")[0]
                    # 补全扩展名
                    if not "." in file_name:
                         file_name += ".jpg"
                    
                    local_path = dest / file_name
                    
                    if local_path.exists():
                        url_to_local[url] = file_name
                        return
                        
                    resp = await client.get(url, timeout=timeout)
                    resp.raise_for_status()
                    with open(local_path, "wb") as f:
                        f.write(resp.content)
                        
                    url_to_local[url] = file_name
                    
                except Exception as e:
                    # 使用 print 代替 log 避免阻塞过深
                    print(f"⚠️ 图片下载失败 [{url}]: {e}")

        # 并发执行
        tasks = [worker(url) for url in img_urls]
        await asyncio.gather(*tasks)
        await client.aclose()

        return url_to_local