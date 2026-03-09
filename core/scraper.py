"""
scraper.py - Zhihu Page Scraping & Image Download Module (v3.0 Pure Protocol Engine API Version)

Disclaimer:
This project is for academic research and learning purposes only.
Please comply with Zhihu's terms of service and robots.txt.

zhihu-scraper integrates a pure protocol-layer network client that directly fetches from the v4 API.
Anti-blocking core relies on:
1. curl_cffi simulates real browser TLS fingerprints (chrome110/edge)
2. Load multi-account Cookie pools from cookies.json or cookie_pool/
3. Intelligent fallback to Playwright headless browser (only for heavily protected routes like Columns)

Core scraping strategy:
- Default to curl_cffi pure protocol API mode (lightweight, fast, no browser required)
- When API encounters 403/blocking, automatically fall back to Playwright browser rendering

================================================================================
scraper.py — 知乎页面抓取 & 图片下载模块 (v3.0 纯协议引擎 API 版)

免责声明：
本项目仅供学术研究和学习交流使用，请勿用于任何商业用途。
使用者应遵守知乎的相关服务协议和 robots.txt 协议。

集成纯协议层网络客户端，直接基于 v4 API 抓取。
防封核心依赖于：
1. curl_cffi 模拟真实浏览器 TLS 指纹 (chrome110/edge)
2. 从 cookies.json 或 cookie_pool/ 加载多账号 Cookie 池
3. 智能降级回退到 Playwright 无头浏览器 (仅专栏等强风控路由)

核心抓取策略：
- 默认使用 curl_cffi 纯协议 API 模式 (轻量、快速、无需浏览器)
- 当 API 遭遇 403/风控拦截时，自动降级启动 Playwright 浏览器渲染
================================================================================
"""

import asyncio
from typing import Union, List, Optional
import httpx
from pathlib import Path
import re
from datetime import datetime
from random import uniform

from .config import get_logger, get_humanizer
from .api_client import ZhihuAPIClient

class ZhihuDownloader:
    """
    Chinese: 从知乎文章/回答页面直接抓取 API 数据并下载图片到本地。
    English: Downloads API data from Zhihu articles/answers and saves images locally.
    """

    def __init__(self, url: str) -> None:
        # Initialize URL and detect page type
        # 初始化 URL 并检测页面类型
        self.url = url.split("?")[0]
        self.page_type = self._detect_type()
        self.api_client = ZhihuAPIClient()
        self.log = get_logger()

    def _detect_type(self) -> str:
        """
        Detect page type from URL
        Detect: article (zhuanlan), answer, or question page
        从 URL 检测页面类型：专栏、回答或问题页面
        """
        if "zhuanlan.zhihu.com" in self.url:
            return "article"
        if "/answer/" in self.url:
            return "answer"
        if "/question/" in self.url:
            return "question"
        return "article"

    def has_valid_cookies(self) -> bool:
        """
        Check if valid cookies exist (for CLI compatibility)
        检查是否有有效 Cookie (兼容 CLI 调用)
        """
        return bool(self.api_client._cookies_dict)

    async def fetch_page(self, **kwargs) -> Union[dict, List[dict]]:
        """
        Fetch page data using pure protocol layer.
        Supports kwargs (like start, limit) passed to _extract_question.

        Scraping workflow:
        1. First try curl_cffi API mode (lightweight and fast)
        2. If encountering 403/blocking, automatically fall back to Playwright browser rendering

        使用纯协议层抓取页面数据。
        支持传入 kwargs (如 start, limit) 传递给 _extract_question。

        抓取流程：
        1. 首先尝试 curl_cffi API 模式 (轻量快速)
        2. 如果遭遇 403/风控，自动降级到 Playwright 浏览器渲染
        """
        humanizer = get_humanizer()

        self.log.info("start_fetching", url=self.url, page_type=self.page_type)
        print(f"🌍 访问 [API 模式]: {self.url}")

        # 模拟部分延时，以避免瞬时高频请求
        await humanizer.page_load()

        headless = kwargs.pop("headless", True)

        if self.page_type == "article":
            return await self._extract_article(headless=headless)
        elif self.page_type == "question":
            return await self._extract_question(**kwargs)
        else:
            return await self._extract_answer()

    async def _extract_article(self, *, headless: bool = True) -> dict:
        """提取专栏文章数据。

        流程说明：
        1. 尝试 API 直接获取文章 JSON 数据
        2. 如果 API 返回 403 或解析失败，自动降级到 Playwright 浏览器渲染
        """
        # 从 URL 提取 Article ID
        # e.g., https://zhuanlan.zhihu.com/p/123456
        match = re.search(r"p/(\d+)", self.url)
        if not match:
             raise Exception(f"无法从专栏 URL 提取 ID: {self.url}")

        article_id = match.group(1)
        try:
            data = self.api_client.get_article(article_id)
        except Exception as e:
            print(f"⚠️ API 请求专栏失败 ({e})")
            print(f"🔄 正在启动 Playwright 无头浏览器智能降级回退机制...")

            # Fallback 策略���使用 Playwright 渲染页面
            from .browser_fallback import extract_zhuanlan_html
            from .cookie_manager import cookie_manager

            # 使用现有 session 的 cookies
            session_cookies = cookie_manager.get_current_session()
            data = await extract_zhuanlan_html(article_id, session_cookies, headless=headless)

            if not data:
                raise Exception(f"专栏文章 {article_id} API 及降级抓取均失败，请手工检查 URL 或重新分配 Cookie。")

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

    async def _extract_answer(self) -> dict:
        """提取单个回答数据。"""
        # https://www.zhihu.com/question/298203515/answer/2008258573281562692
        match = re.search(r"answer/(\d+)", self.url)
        if not match:
             raise Exception(f"无法从回答 URL 提取 ID: {self.url}")

        answer_id = match.group(1)
        try:
            data = self.api_client.get_answer(answer_id)
        except Exception as e:
            raise Exception(f"回答 {answer_id} API 抓取失败: {e}")

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

    async def _extract_question(self, start: int = 0, limit: int = 3, **kwargs) -> List[dict]:
        """提取问题下的多个回答。

        利用 API 分页直接获取，支持一次获取多页回答。

        Args:
            start: 起始偏移量 (默认 0)
            limit: 获取回答数量 (默认 3)
        """
        match = re.search(r"question/(\d+)", self.url)
        if not match:
             raise Exception(f"无法从问题 URL 提取 ID: {self.url}")

        question_id = match.group(1)
        target_limit = max(1, limit)
        current_offset = max(0, start)
        page_size = 20
        humanizer = get_humanizer()

        print(f"🎯 目标: API 分页抓取问题 {question_id} 的前 {target_limit} 个回答 (从第 {current_offset} 条开始)")

        results: List[dict] = []
        page_index = 0

        while len(results) < target_limit:
            current_page_size = min(page_size, target_limit - len(results))

            try:
                page = self.api_client.get_question_answers_page(
                    question_id,
                    limit=current_page_size,
                    offset=current_offset,
                )
            except Exception as e:
                message = f"问题 {question_id} 第 {page_index + 1} 页回答列表 API 抓取失败: {e}"
                if results:
                    print(f"⚠️ {message}")
                    print(f"🛑 为降低风险，本次提前停止，保留已抓到的 {len(results)} 个回答。")
                    break
                raise Exception(message)

            answers_data = page.get("data", [])
            if not answers_data:
                break

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
                    "upvotes": upvotes,
                })

            page_index += 1
            current_offset += len(answers_data)
            print(f"📄 第 {page_index} 页完成，本页 {len(answers_data)} 条，累计 {len(results)}/{target_limit} 条。")

            if len(results) >= target_limit:
                break

            if page.get("paging", {}).get("is_end", len(answers_data) < current_page_size):
                break

            if humanizer.config.enabled:
                if page_index % 3 == 0:
                    delay = uniform(15.0, 30.0)
                    print(f"⏸️ 已连续抓取 {page_index} 页，额外休息 {delay:.1f} 秒后继续...")
                else:
                    min_delay = max(3.0, humanizer.config.min_delay)
                    max_delay = max(min_delay, humanizer.config.max_delay, 8.0)
                    delay = uniform(min_delay, max_delay)
                    print(f"⏳ 等待 {delay:.1f} 秒后抓取下一页...")
                await asyncio.sleep(delay)

        print(f"✅ 成功命中 {len(results)} 个回答。")
        return results

    # ── 图片下载 (Image Download) ──────────────────────────────────────────────

    @classmethod
    async def download_images(
        cls,
        img_urls: List[str],
        dest: Path,
        *,
        concurrency: int = 4,
        timeout: float = 30.0,
        relative_prefix: str = "images",
    ) -> dict[str, str]:
        """
        Download images concurrently with deduplication.

        Image deduplication strategy:
        - Zhihu image naming: v2-xxx_720w.jpg, v2-xxx_r.jpg
        - For same base_name images, download only once, keeping highest quality
        - Returns format "images/xxx.jpg" for Markdown references

        Args:
            img_urls: List of image URLs
            dest: Image save directory
            concurrency: Concurrency count (default 4)
            timeout: Request timeout (default 30s)

        Returns:
            URL -> relative path mapping dict, format "images/xxx.jpg"

        并发下载图片。
        图片去重策略：
        - 知乎图片命名规则：v2-xxx_720w.jpg, v2-xxx_r.jpg
        - 对于相同 base_name 的图片，只下载一次，保留最高质量版本
        - 返回格式为 "images/xxx.jpg" 用于 Markdown 引用

        Args:
            img_urls: 图片 URL 列表
            dest: 图片保存目录
            concurrency: 并发数 (默认 4)
            timeout: 请求超时时间 (默认 30秒)

        Returns:
            URL → 相对路径 映射字典，格式 "images/xxx.jpg"
        """
        if not img_urls:
            return {}

        dest.mkdir(parents=True, exist_ok=True)
        url_to_local: dict[str, str] = {}

        # 用作去重的 base name 集合
        seen_base: set[str] = set()
        # 真正需要下载的 URL 列表
        urls_to_download: list[str] = []

        for url in img_urls:
            # 补全协议头
            if url.startswith("//"):
                url = "https:" + url

            # 过滤特殊情况
            if not url or url.startswith("data:") or "noavatar" in url:
                continue

            # 提取基础名用于去重：v2-xxx_720w.jpg → v2-xxx
            base_name = url.split("/")[-1].split("?")[0]
            for suffix in ["_720w", "_r", "_l"]:
                if base_name.endswith(suffix + ".jpg"):
                    base_name = base_name.replace(suffix + ".jpg", ".jpg")
                    break
                if base_name.endswith(suffix + ".png"):
                    base_name = base_name.replace(suffix + ".png", ".png")
                    break

            # 如果已经见过同主题图片，跳过
            if base_name in seen_base:
                continue
            seen_base.add(base_name)
            urls_to_download.append(url)

        if not urls_to_download:
            return url_to_local

        sem = asyncio.Semaphore(concurrency)
        client = httpx.AsyncClient(headers={
            "Referer": "https://www.zhihu.com/",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        })

        async def worker(url: str):
            async with sem:
                try:
                    # 获取文件名，去除 URL 参数和尺寸后缀
                    fname = url.split("/")[-1].split("?")[0]
                    for suffix in ["_720w", "_r", "_l"]:
                        if fname.endswith(suffix + ".jpg"):
                            fname = fname.replace(suffix + ".jpg", ".jpg")
                            break
                        if fname.endswith(suffix + ".png"):
                            fname = fname.replace(suffix + ".png", ".png")
                            break

                    # 确保有扩展名
                    if "." not in fname:
                        fname += ".jpg"

                    # 保存路径带上 images/ 前缀（用于 Markdown 引用）
                    local_path = dest / fname

                    if local_path.exists():
                        url_to_local[url] = f"{relative_prefix}/{fname}"
                        return

                    resp = await client.get(url, timeout=timeout)
                    resp.raise_for_status()

                    # 写入二进制文件
                    with open(local_path, "wb") as f:
                        f.write(resp.content)

                    # 返回带 images/ 前缀的路径（用于 Markdown）
                    url_to_local[url] = f"{relative_prefix}/{fname}"

                except Exception as e:
                    print(f"⚠️ 图片下载失败 [{url}]: {e}")

        # 并发执行
        tasks = [worker(url) for url in urls_to_download]
        await asyncio.gather(*tasks)
        await client.aclose()

        return url_to_local
