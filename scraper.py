"""
scraper.py — 知乎页面抓取 & 图片下载模块
集成 MediaCrawler 的反爬策略：Persistent Context, Stealth JS, WebGL Mock, Proxy.
"""

import asyncio
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx
# 需 pip install PyExecJS
import execjs
from playwright.async_api import async_playwright, Playwright

# 全局配置
# 如果本地 Shadowrocket/Clash 开启了 1087 端口，请使用下面的配置；否则设为 None
# 如果本地 Shadowrocket/Clash 开启了 1087 端口，请使用 "http://127.0.0.1:1087"；否则设为 None
PROXY_SERVER = "http://127.0.0.1:1082"
USER_DATA_DIR = Path(__file__).parent / "browser_data"
STEALTH_JS_PATH = Path(__file__).parent / "stealth.min.js"
ZHIHU_JS_PATH = Path(__file__).parent / "zhihu.js"


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
        self._js_ctx = self._init_js_context()

    def _detect_type(self) -> str:
        if "zhuanlan.zhihu.com" in self.url:
            return "article"
        if "/answer/" in self.url:
            return "answer"
        return "article"

    def _init_js_context(self):
        """初始化 JS 执行环境 (备用，用于生成 x-zse-96)。"""
        if ZHIHU_JS_PATH.exists():
            try:
                with open(ZHIHU_JS_PATH, "r", encoding="utf-8") as f:
                    js_code = f.read()
                return execjs.compile(js_code)
            except Exception as e:
                print(f"⚠️  JS 环境加载失败: {e}")
        return None

    def _get_signature(self, url: str) -> dict:
        """生成 x-zse-96 签名。"""
        if not self._js_ctx:
            return {}
        try:
            # 提取 path, e.g. /question/xxx
            path = urlparse(url).path
            # 前面判空了 self._js_ctx，这里显式类型断言或直接调用
            from typing import cast, Any
            ctx = cast(Any, self._js_ctx)
            return ctx.call("get_sign", path, "d_c0=SEARCH_ME") # d_c0 is simplified
        except Exception as e:
            # print(f"⚠️  签名生成失败: {e}")
            return {}

    # ── 页面抓取 Core ──────────────────────────────────────────

    async def fetch_page(self) -> dict:
        """
        使用 Persistent Context + Stealth + Proxy 抓取页面。
        """
        async with async_playwright() as pw:
            # 准备启动参数
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars",
                "--disable-gpu",  # 有时禁用 GPU 更稳定
            ]

            # 启动持久化上下文
            context = await pw.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR,
                headless=True,  # 依然可以用 Headless，配合 Stealth
                args=launch_args,
                user_agent=self._UA,
                viewport={"width": 1920, "height": 1080},
                proxy={"server": PROXY_SERVER} if PROXY_SERVER else None,
                java_script_enabled=True,
                locale="zh-CN",
                channel="chrome",  # 尝试用本机 Chrome
            )

            try:
                page = context.pages[0] if context.pages else await context.new_page()

                # 1. 注入 stealth.min.js
                if STEALTH_JS_PATH.exists():
                    await context.add_init_script(path=STEALTH_JS_PATH)
                else:
                    print("⚠️  未找到 stealth.min.js，反爬能力可能下降")

                # 2. 注入额外的 WebGL / Navigator 伪造 (参考 MediaCrawler CDP)
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    
                    // 伪造 WebGL
                    const getParameter = WebGLRenderingContext.prototype.getParameter;
                    WebGLRenderingContext.prototype.getParameter = function(parameter) {
                        if (parameter === 37445) return 'Intel Inc.';
                        if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                        return getParameter(parameter);
                    };
                """)

                # 注入签名 (如果是 API 请求，这里主要演示思路，实际页面访问不需要手动加 Header，浏览器会自动处理)
                # 但为了保险，我们可以把签名加到 extraHTTPHeaders
                sig = self._get_signature(self.url)
                if sig:
                   await page.set_extra_http_headers(sig)

                # 3. 设置默认 Timeout
                page.set_default_timeout(30000)

                # 4. 访问页面
                print(f"🌍 访问: {self.url}")
                # 随机延迟，模拟真人
                await asyncio.sleep(1)
                
                await page.goto(self.url, wait_until="domcontentloaded")
                
                # 等待 JS 执行和反爬检测通过
                await page.wait_for_timeout(3000)

                # 5. 处理弹窗
                await self._dismiss_popup(page)

                # 6. 提取内容
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
        # 知乎的反爬有时会返回 JSON 错误
        text = await page.locator("body").inner_text()
        if "40362" in text or "请求存在异常" in text:
            raise Exception("触发知乎反爬 (40362)")

        # 等待标题
        await page.wait_for_selector("h1.Post-Title", timeout=10000)

        title = await page.locator("h1.Post-Title").inner_text()
        author = await self._safe_text(
            page, ".AuthorInfo span.UserLink-Name", "未知作者"
        )
        if author == "未知作者":
            author = await self._safe_text(
                page, ".AuthorInfo-name .UserLink-link", "未知作者"
            )
        
        date = await self._extract_date(page)

        # 优先由容器找
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
        
        # 尝试多种作者选择器
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
            if meta: return meta[:10]
        except: pass
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
        dest.mkdir(parents=True, exist_ok=True)
        url_to_local: dict[str, str] = {}

        # 配置代理
        limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
        async with httpx.AsyncClient(
            headers=cls._IMG_HEADERS,
            timeout=30.0,
            follow_redirects=True,
            proxy=PROXY_SERVER,  # 图片下载也走代理
            limits=limits,
        ) as client:
            tasks = [cls._download_one(client, url, dest, url_to_local) for url in img_urls]
            await asyncio.gather(*tasks, return_exceptions=True)

        return url_to_local

    @staticmethod
    async def _download_one(client, url, dest, mapping):
        try:
            if url.startswith("//"): url = "https:" + url
            
            # 过滤不需要的图片
            if "data:image" in url or "equation" in url:
                return

            resp = await client.get(url)
            resp.raise_for_status()

            ext = Path(urlparse(url).path).suffix or ".jpg"
            if len(ext) > 5: ext = ".jpg"
            
            fname = hashlib.md5(url.encode()).hexdigest()[:12] + ext
            fpath = dest / fname

            fpath.write_bytes(resp.content)
            # 必须用 / 分隔，要在 Markdown 里用
            mapping[url] = f"images/{fname}"
        except Exception:
            pass