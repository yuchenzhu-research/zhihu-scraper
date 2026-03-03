"""
scraper.py — 知乎页面抓取 & 图片下载模块

免责声明：
本项目仅供学术研究和学习交流使用，请勿用于任何商业用途。
使用者应遵守知乎的相关服务协议和 robots.txt 协议。

使用 Playwright 浏览器模式抓取，配合 stealth.min.js 反检测。
"""

import asyncio
import hashlib
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import httpx
from playwright.async_api import async_playwright, Playwright

# 从配置文件读取
from .config import get_logger

# 全局配置
STEALTH_JS_PATH = Path(__file__).parent.parent / "static" / "stealth.min.js"
USER_DATA_DIR = Path(__file__).parent.parent / "browser_data"


def get_auto_proxy() -> str | None:
    """
    自动获取 macOS 系统代理设置。
    """
    try:
        output = subprocess.check_output("scutil --proxy", shell=True).decode("utf-8")
        if "HTTPEnable : 1" in output:
            match = re.search(r"HTTPPort : (\d+)", output)
            if match:
                return f"http://127.0.0.1:{match.group(1)}"
    except Exception:
        pass
    return None


PROXY_SERVER = get_auto_proxy()


class ZhihuDownloader:
    """从知乎文章/回答页面抓取 HTML 内容并下载图片到本地。"""

    _UA = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    )

    _IMG_HEADERS = {
        "Referer": "https://www.zhihu.com/",
        "User-Agent": _UA,
    }

    def __init__(self, url: str) -> None:
        self.url = url.split("?")[0]
        self.page_type = self._detect_type()
        self.log = get_logger()

    def _detect_type(self) -> str:
        if "zhuanlan.zhihu.com" in self.url:
            return "article"
        if "/answer/" in self.url:
            return "answer"
        return "article"

    # ── 页面抓取 Core ──────────────────────────────────────────

    async def fetch_page(self) -> dict:
        """
        使用 Playwright 浏览器抓取页面。
        """
        async with async_playwright() as pw:
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars",
                "--disable-gpu",
            ]

            context = await pw.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR,
                headless=True,
                args=launch_args,
                user_agent=self._UA,
                viewport={"width": 1920, "height": 1080},
                proxy={"server": PROXY_SERVER} if PROXY_SERVER else None,
                java_script_enabled=True,
                locale="zh-CN",
                channel="chrome",
            )

            try:
                page = context.pages[0] if context.pages else await context.new_page()

                # 注入 stealth.min.js
                if STEALTH_JS_PATH.exists():
                    await context.add_init_script(path=STEALTH_JS_PATH)

                # 注入额外的 WebGL / Navigator 伪造
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    const getParameter = WebGLRenderingContext.prototype.getParameter;
                    WebGLRenderingContext.prototype.getParameter = function(parameter) {
                        if (parameter === 37445) return 'Intel Inc.';
                        if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                        return getParameter(parameter);
                    };
                """)

                page.set_default_timeout(30000)

                print(f"🌍 访问: {self.url}")
                await asyncio.sleep(1)
                await page.goto(self.url, wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)

                # 关闭弹窗
                await self._dismiss_popup(page)

                # 提取内容
                if self.page_type == "article":
                    result = await self._extract_article(page)
                else:
                    result = await self._extract_answer(page)

                return result

            finally:
                await context.close()

    async def _dismiss_popup(self, page) -> None:
        """关闭登录弹窗。"""
        try:
            btn = page.locator("button.Modal-closeButton")
            if await btn.count() > 0:
                await btn.click(timeout=2000)
                await page.wait_for_timeout(500)
        except Exception:
            pass

    async def _extract_article(self, page) -> dict:
        """提取文章。"""
        text = await page.locator("body").inner_text()
        if "40362" in text or "请求存在异常" in text:
            raise Exception("触发知乎反爬 (40362)")

        await page.wait_for_selector("h1.Post-Title", timeout=10000)

        title = await page.locator("h1.Post-Title").inner_text()
        author = await self._safe_text(page, ".AuthorInfo span.UserLink-Name", "未知作者")
        if author == "未知作者":
            author = await self._safe_text(page, ".AuthorInfo-name .UserLink-link", "未知作者")

        date = await self._extract_date(page)

        rich = page.locator(".Post-RichTextContainer .RichText").first
        if await rich.count() > 0:
            html = await rich.inner_html()
        else:
            html = await page.locator(".RichText").first.inner_html()

        # 尝试获取头图
        try:
            title_img = page.locator("img.TitleImage").first
            if await title_img.count() > 0:
                src = await title_img.get_attribute("src")
                if src:
                    html = f'<img src="{src}" alt="TitleImage"><br>{html}'
        except Exception:
            pass

        return {"title": title.strip(), "author": author.strip(), "html": html, "date": date}

    async def _extract_answer(self, page) -> dict:
        """提取回答。"""
        text = await page.locator("body").inner_text()
        if "40362" in text:
            raise Exception("触发知乎反爬 (40362)")

        await page.wait_for_selector(".QuestionAnswer-content", timeout=10000)

        title = await self._safe_text(page, "h1.QuestionHeader-title", "未知问题")
        author = await self._safe_text(page, ".AuthorInfo-name .UserLink-link", "未知作者")
        if author == "未知作者":
            author = await self._safe_text(page, ".AuthorInfo span.UserLink-Name", "未知作者")

        date = await self._extract_date(page)
        html = await page.locator(".QuestionAnswer-content .RichText").first.inner_html()

        return {"title": title.strip(), "author": author.strip(), "html": html, "date": date}

    async def _extract_date(self, page) -> str:
        from datetime import date as dt_date
        try:
            meta = await page.locator('meta[itemprop="datePublished"]').get_attribute("content", timeout=2000)
            if meta:
                return meta[:10]
        except:
            pass
        return dt_date.today().isoformat()

    async def _safe_text(self, page, selector: str, default: str) -> str:
        try:
            el = page.locator(selector).first
            return await el.inner_text(timeout=2000)
        except:
            return default

    # ── 图片下载 ──────────────────────────────────────────────

    @classmethod
    async def download_images(cls, img_urls: list[str], dest: Path) -> dict[str, str]:
        """
        并发下载图片，返回 URL → 相对路径 的映射。
        返回的路径格式为 "images/xxx.jpg"，用于 Markdown 引用。
        """
        dest.mkdir(parents=True, exist_ok=True)
        url_to_local: dict[str, str] = {}

        if not img_urls:
            return url_to_local

        limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
        async with httpx.AsyncClient(
            headers=cls._IMG_HEADERS,
            timeout=30.0,
            follow_redirects=True,
            proxy=PROXY_SERVER,
            limits=limits,
        ) as client:
            tasks = [cls._download_one(client, url, dest, url_to_local) for url in img_urls]
            await asyncio.gather(*tasks, return_exceptions=True)

        return url_to_local

    @staticmethod
    async def _download_one(client, url, dest, mapping):
        """
        下载单张图片。
        知乎图片命名规则：v2-xxx_720w.jpg, v2-xxx_r.jpg
        我们去重后缀，只保留基础文件名。
        """
        try:
            if url.startswith("//"):
                url = "https:" + url

            # 过滤不需要的图片
            if "data:image" in url or "equation" in url:
                return

            resp = await client.get(url)
            resp.raise_for_status()

            # 提取文件名并去除尺寸后缀
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

            fpath = dest / fname
            fpath.write_bytes(resp.content)

            # 返回带 images/ 前缀的路径（用于 Markdown）
            mapping[url] = f"images/{fname}"
        except Exception:
            pass