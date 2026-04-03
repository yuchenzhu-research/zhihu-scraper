"""
scraper.py - Zhihu Page Scraping & Image Download Module (v3.0 Pure Protocol Engine API Version)

Disclaimer:
This project is for academic research and learning purposes only.
Please comply with Zhihu's terms of service and robots.txt.

zhihu-scraper integrates a pure protocol-layer network client that directly fetches from the v4 API.
Anti-blocking core relies on:
1. curl_cffi simulates real browser TLS fingerprints (chrome110/edge)
2. Load multi-account Cookie pools from .local/cookies.json or .local/cookie_pool/
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
2. 从 .local/cookies.json 或 .local/cookie_pool/ 加载多账号 Cookie 池
3. 智能降级回退到 Playwright 无头浏览器 (仅专栏等强风控路由)

核心抓取策略：
- 默认使用 curl_cffi 纯协议 API 模式 (轻量、快速、无需浏览器)
- 当 API 遭遇 403/风控拦截时，自动降级启动 Playwright 浏览器渲染
================================================================================
"""

import asyncio
from typing import Union, List, Optional, Dict, Any, Callable
import httpx
from pathlib import Path
import re
import hashlib
from random import uniform

from .config import get_logger, get_humanizer
from .api_client import ZhihuAPIClient
from .scraper_contracts import (
    CreatorFetchResult,
    CreatorProfileSummary,
    PageFetchResult,
    PaginationStats,
    to_scraped_items,
)
from .utils import extract_creator_token
from .scraper_payloads import (
    build_answer_item,
    build_article_item,
    build_creator_answer_item,
    build_creator_article_item,
    build_creator_profile_payload,
    build_empty_sync_stats,
    build_question_answer_item,
)

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
        """Backward-compatible fetch entrypoint returning legacy dict/list payloads."""
        return (await self.fetch_result(**kwargs)).to_legacy_payload()

    async def fetch_result(self, **kwargs) -> PageFetchResult:
        """
        Typed fetch entrypoint returning a stable result contract.
        返回稳定结果契约的抓取入口。
        """
        humanizer = get_humanizer()

        self.log.info("start_fetching", url=self.url, page_type=self.page_type)
        access_mode = "协议模式" if self.page_type == "article" else "API 模式"
        print(f"🌍 访问 [{access_mode}]: {self.url}")

        # 模拟部分延时，以避免瞬时高频请求
        await humanizer.page_load()

        headless = kwargs.pop("headless", True)

        if self.page_type == "article":
            raw_items = [await self._extract_article(headless=headless)]
        elif self.page_type == "question":
            raw_items = await self._extract_question(**kwargs)
        else:
            raw_items = [await self._extract_answer()]

        return PageFetchResult(
            source_url=self.url,
            page_type=self.page_type,
            items=to_scraped_items(raw_items),
        )

    async def _extract_article(self, *, headless: bool = True) -> dict:
        """提取专栏文章数据。

        流程说明：
        1. 尝试协议层 HTML 直取，并解析 `js-initialData`
        2. 首轮失败时自动轮换 Cookie 重试一次
        3. 若仍失败，再自动降级到 Playwright 浏览器渲染
        """
        # 从 URL 提取 Article ID
        # e.g., https://zhuanlan.zhihu.com/p/123456
        match = re.search(r"p/(\d+)", self.url)
        if not match:
             raise Exception(f"无法从专栏 URL 提取 ID: {self.url}")

        article_id = match.group(1)
        try:
            print("📰 专栏阶段 1/3: 协议层 HTML 直取")
            data = self.api_client.get_article(article_id)
        except Exception as e:
            self.log.warning("article_protocol_failed", article_id=article_id, error=str(e))
            print(f"⚠️ 协议路径未能提取专栏 ({e})")
            print("🔁 已尝试 HTML 直取，并在失败后轮换 Cookie 重试一次")
            print("🔄 专栏阶段 3/3: 正在启动 Playwright 无头浏览器智能降级回退机制...")

            # Fallback 策略：使用 Playwright 渲染页面
            from .browser_fallback import extract_zhuanlan_html
            from .cookie_manager import cookie_manager

            # 使用现有 session 的 cookies
            session_cookies = cookie_manager.get_current_session()
            data = await extract_zhuanlan_html(article_id, session_cookies, headless=headless)

            if not data:
                raise Exception(f"专栏文章 {article_id} API 及降级抓取均失败，请手工检查 URL 或重新分配 Cookie。")

        return build_article_item(url=self.url, article_id=article_id, data=data)

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

        return build_answer_item(url=self.url, answer_id=answer_id, data=data)

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
                results.append(build_question_answer_item(question_id=question_id, data=data))

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

        def infer_extension(url: str, content_type: str) -> str:
            """
            Infer a file extension from URL or HTTP content type.
            根据 URL 或 HTTP content-type 推断文件扩展名。
            """
            lowered_url = url.lower()
            if lowered_url.endswith(".jpg") or lowered_url.endswith(".jpeg"):
                return ".jpg"
            if lowered_url.endswith(".png"):
                return ".png"
            if lowered_url.endswith(".webp"):
                return ".webp"
            if lowered_url.endswith(".gif"):
                return ".gif"
            if lowered_url.endswith(".svg"):
                return ".svg"

            content_type = (content_type or "").split(";")[0].strip().lower()
            mapping = {
                "image/jpeg": ".jpg",
                "image/jpg": ".jpg",
                "image/png": ".png",
                "image/webp": ".webp",
                "image/gif": ".gif",
                "image/svg+xml": ".svg",
            }
            return mapping.get(content_type, ".jpg")

        async def worker(url: str):
            async with sem:
                try:
                    # 获取基础文件名，去除 URL 参数和尺寸后缀
                    raw_name = url.split("/")[-1].split("?")[0]
                    fname = raw_name
                    for suffix in ["_720w", "_r", "_l"]:
                        if fname.endswith(suffix + ".jpg"):
                            fname = fname.replace(suffix + ".jpg", ".jpg")
                            break
                        if fname.endswith(suffix + ".png"):
                            fname = fname.replace(suffix + ".png", ".png")
                            break

                    stem = Path(fname).stem if "." in fname else (fname or hashlib.sha1(url.encode("utf-8")).hexdigest()[:16])
                    suffix = Path(fname).suffix if "." in fname else ""

                    if suffix:
                        existing_path = dest / f"{stem}{suffix}"
                        if existing_path.exists():
                            url_to_local[url] = f"{relative_prefix}/{existing_path.name}"
                            return
                    else:
                        for existing_path in sorted(dest.glob(f"{stem}.*")):
                            if existing_path.is_file():
                                url_to_local[url] = f"{relative_prefix}/{existing_path.name}"
                                return

                    last_error: Optional[Exception] = None
                    resp: Optional[httpx.Response] = None
                    for attempt in range(1, 4):
                        try:
                            resp = await client.get(url, timeout=timeout)
                            resp.raise_for_status()
                            break
                        except Exception as e:
                            last_error = e
                            if attempt < 3:
                                await asyncio.sleep(0.8 * attempt)
                            else:
                                raise

                    assert resp is not None

                    if not suffix:
                        suffix = infer_extension(url, resp.headers.get("Content-Type", ""))

                    final_name = f"{stem}{suffix}"
                    local_path = dest / final_name

                    if local_path.exists():
                        url_to_local[url] = f"{relative_prefix}/{final_name}"
                        return

                    # 写入二进制文件
                    with open(local_path, "wb") as f:
                        f.write(resp.content)

                    # 返回带 images/ 前缀的路径（用于 Markdown）
                    url_to_local[url] = f"{relative_prefix}/{final_name}"

                except Exception as e:
                    print(f"⚠️ 图片下载失败 [{url}]: {e}")

        # 并发执行
        tasks = [worker(url) for url in urls_to_download]
        await asyncio.gather(*tasks)
        await client.aclose()

        return url_to_local


class ZhihuCreatorDownloader:
    """
    Fetch answers and articles from a Zhihu creator profile.
    抓取知乎作者主页下的回答与专栏。
    """

    def __init__(self, creator: str) -> None:
        self.creator = creator.strip()
        self.url_token = extract_creator_token(self.creator)
        self.api_client = ZhihuAPIClient()
        self.log = get_logger()

    async def fetch_items(self, answer_limit: int = 10, article_limit: int = 5) -> Dict[str, Any]:
        """
        Backward-compatible creator fetch returning the legacy dict structure.
        返回旧版 dict 结构的兼容入口。
        """
        return (await self.fetch_items_result(answer_limit=answer_limit, article_limit=article_limit)).to_dict()

    async def fetch_items_result(self, answer_limit: int = 10, article_limit: int = 5) -> CreatorFetchResult:
        """
        Fetch creator profile and selected content types with a stable result contract.
        以稳定结果契约抓取作者资料和指定内容。
        """
        if not self.url_token:
            raise Exception(f"无法从作者输入中提取知乎用户标识: {self.creator}")

        creator_profile = self.api_client.get_creator_profile(self.url_token)
        items: List[dict] = []
        answer_result = {"items": [], "stats": self._make_empty_sync_stats(answer_limit)}
        article_result = {"items": [], "stats": self._make_empty_sync_stats(article_limit)}

        if answer_limit > 0:
            answer_result = await self._paginate_creator_items(
                label="回答",
                target_limit=answer_limit,
                fetch_page=lambda offset, limit: self.api_client.get_creator_answers_page(self.url_token, limit=limit, offset=offset),
                normalize_item=self._normalize_creator_answer,
            )
            items.extend(answer_result["items"])

        if article_limit > 0:
            article_result = await self._paginate_creator_items(
                label="专栏",
                target_limit=article_limit,
                fetch_page=lambda offset, limit: self.api_client.get_creator_articles_page(self.url_token, limit=limit, offset=offset),
                normalize_item=self._normalize_creator_article,
            )
            items.extend(article_result["items"])

        return CreatorFetchResult(
            creator=CreatorProfileSummary.from_dict(build_creator_profile_payload(self.url_token, creator_profile)),
            items=to_scraped_items(items),
            answers=PaginationStats.from_dict(answer_result["stats"]),
            articles=PaginationStats.from_dict(article_result["stats"]),
        )

    async def _paginate_creator_items(
        self,
        *,
        label: str,
        target_limit: int,
        fetch_page: Callable[[int, int], dict],
        normalize_item: Callable[[dict], dict],
    ) -> Dict[str, Any]:
        """
        Generic creator pagination loop with conservative throttling.
        通用作者分页抓取循环，带保守节流。
        """
        humanizer = get_humanizer()
        page_size = 20
        offset = 0
        page_index = 0
        items: List[dict] = []
        reached_end = False
        stopped_early = False

        print(f"👤 开始抓取作者 {self.url_token} 的前 {target_limit} 条{label}...")

        while len(items) < target_limit:
            current_page_size = min(page_size, target_limit - len(items))

            try:
                page = fetch_page(offset, current_page_size)
            except Exception as e:
                message = f"作者 {self.url_token} 第 {page_index + 1} 页{label}抓取失败: {e}"
                if items:
                    print(f"⚠️ {message}")
                    print(f"🛑 为降低风险，本次提前停止，保留已抓到的 {len(items)} 条{label}。")
                    stopped_early = True
                    break
                raise Exception(message)

            page_items = page.get("data", [])
            if not page_items:
                reached_end = True
                break

            for raw_item in page_items:
                items.append(normalize_item(raw_item))

            page_index += 1
            offset += len(page_items)
            print(f"📄 {label}第 {page_index} 页完成，本页 {len(page_items)} 条，累计 {len(items)}/{target_limit} 条。")

            if len(items) >= target_limit:
                break

            if page.get("paging", {}).get("is_end", len(page_items) < current_page_size):
                reached_end = True
                break

            if humanizer.config.enabled:
                if page_index % 3 == 0:
                    delay = uniform(15.0, 30.0)
                    print(f"⏸️ 已连续抓取 {page_index} 页{label}，额外休息 {delay:.1f} 秒后继续...")
                else:
                    min_delay = max(3.0, humanizer.config.min_delay)
                    max_delay = max(min_delay, humanizer.config.max_delay, 8.0)
                    delay = uniform(min_delay, max_delay)
                    print(f"⏳ 等待 {delay:.1f} 秒后抓取下一页{label}...")
                await asyncio.sleep(delay)

        return {
            "items": items,
            "stats": {
                "requested_limit": target_limit,
                "saved_count": len(items),
                "pages_fetched": page_index,
                "last_offset": offset,
                "reached_end": reached_end,
                "stopped_early": stopped_early,
            },
        }

    @staticmethod
    def _make_empty_sync_stats(target_limit: int) -> Dict[str, Any]:
        """
        Build default sync stats for disabled or empty content types.
        为禁用或空内容类型构建默认同步统计。
        """
        return build_empty_sync_stats(target_limit)

    def _normalize_creator_answer(self, data: dict) -> dict:
        """
        Convert creator answer API response into the internal item format.
        将作者回答 API 结果转换为内部统一结构。
        """
        return build_creator_answer_item(url_token=self.url_token, data=data)

    def _normalize_creator_article(self, data: dict) -> dict:
        """
        Convert creator article API response into the internal item format.
        将作者专栏 API 结果转换为内部统一结构。
        """
        return build_creator_article_item(url_token=self.url_token, data=data)
