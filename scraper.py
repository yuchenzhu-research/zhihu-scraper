"""
scraper.py — 知乎页面抓取 & 图片下载模块

免责声明：
本项目仅供学术研究和学习交流使用，请勿用于任何商业用途。
使用者应遵守知乎的相关服务协议和 robots.txt 协议。
因使用本项目代码而产生的任何法律纠纷或后果，由使用者自行承担。

集成 MediaCrawler 的反爬策略：Persistent Context, Stealth JS, WebGL Mock, Proxy.
"""

import asyncio
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse
from typing import Union, List, Optional

import httpx
# 需 pip install PyExecJS
import execjs
from playwright.async_api import async_playwright, Playwright
import subprocess

def get_auto_proxy() -> Optional[str]:
    """
    自动获取 macOS 系统代理设置 (Shadowrocket/ClashX)。
    解析 `scutil --proxy` 的输出。
    """
    try:
        output = subprocess.check_output("scutil --proxy", shell=True).decode("utf-8")
        if "HTTPEnable : 1" in output:
            # 提取端口
            match = re.search(r"HTTPPort : (\d+)", output)
            if match:
                port = match.group(1)
                print(f"✅ 已自动检测到系统代理: http://127.0.0.1:{port}")
                return f"http://127.0.0.1:{port}"
    except Exception:
        pass
    
    print("⚠️  未检测到系统代理，尝试直连...")
    return None
# 全局配置
# 自动检测本地代理 (127.0.0.1:xxxx)
PROXY_SERVER = get_auto_proxy()
USER_DATA_DIR = Path(__file__).parent / "browser_data"
STEALTH_JS_PATH = Path(__file__).parent / "stealth.min.js"
ZHIHU_JS_PATH = Path(__file__).parent / "libs" / "z_core.js"


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
        if "/question/" in self.url:
            return "question"
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

    def _load_cookies(self) -> List[dict]:
        """从 cookies.json 加载 Cookie。过滤掉占位符。"""
        cookie_path = Path(__file__).parent / "cookies.json"
        if cookie_path.exists():
            try:
                with open(cookie_path, "r", encoding="utf-8") as f:
                    cookies = json.load(f)
                    # 过滤掉带有占位符的 Cookie
                    valid_cookies = [
                        c for c in cookies 
                        if c.get("value") and c.get("value") != "YOUR_COOKIE_HERE"
                    ]
                    return valid_cookies
            except Exception as e:
                print(f"⚠️  加载 cookies.json 失败: {e}")
        return []

    async def fetch_page(self, **kwargs) -> Union[dict, List[dict]]:
        """
        使用 Persistent Context + Stealth + Proxy 抓取页面。
        支持传入 kwargs (如 start, limit) 传递给 _extract_question。
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

                # 1.5 注入 Cookies
                cookies = self._load_cookies()
                if cookies:
                    await context.add_cookies(cookies)
                    print(f"🍪 已加载 {len(cookies)} 个 Cookie")

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
                # 6. 提取内容
                if self.page_type == "article":
                    result = await self._extract_article(page)
                elif self.page_type == "question":
                    result = await self._extract_question(page, **kwargs)
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

    async def _extract_question(self, page, start: int = 0, limit: int = 3) -> List[dict]:
        """
        提取问题下的多个回答。
        :param start: 从第几个回答开始抓 (0-indexed)
        :param limit: 抓取多少个 (默认 3 个)
        """
        text = await page.locator("body").inner_text()
        if "40362" in text or "请求存在异常" in text:
            raise Exception("触发知乎反爬 (40362)")

        # 等待问题标题加载
        try:
            await page.wait_for_selector(".QuestionHeader-title", timeout=5000)
        except:
            pass
        
        # 尝试点击 "查看全部" 按钮 (如果是 auto 模式且 limit 较小，其实可以不点，为了保险还是点一下)
        await self._click_view_all(page)

        # 等待至少一个回答项加载
        try:
            await page.wait_for_selector(".ContentItem.AnswerItem", timeout=5000)
        except:
            print("⚠️ 未检测到回答列表，可能需要登录或无回答")

        # 智能滚动逻辑
        target_count = start + limit
        print(f"🎯 目标: 抓取前 {target_count} 个回答")

        prev_count = 0
        max_scroll_attempts = 30  # 稍微减少尝试次数，避免死循环
        no_change_count = 0

        while True:
            answers = page.locator(".ContentItem.AnswerItem")
            count = await answers.count()
            print(f"🔄 当前加载了 {count} 个回答...")

            if count >= target_count:
                break
            
            if count == prev_count:
                no_change_count += 1
                if no_change_count >= 3: # 3次没动静就停，更灵敏
                    print("⚠️  已滚动到底部或无法加载更多")
                    break
            else:
                no_change_count = 0
            
            prev_count = count
            
            # 滚动
            await page.mouse.wheel(0, 10000)
            await asyncio.sleep(0.5)
            await page.keyboard.press("End")
            await asyncio.sleep(1.0)
            
            max_scroll_attempts -= 1
            if max_scroll_attempts <= 0:
                print("⚠️  达到最大滚动次数")
                break
        
        # 获取所有回答卡片
        answers = page.locator(".ContentItem.AnswerItem")
        total_found = await answers.count()
        print(f"📊 共发现 {total_found} 个回答，准备提取范围 [{start}:{target_count}]...")
        
        results = []
        actual_limit = min(total_found, target_count)
        
        # 获取问题标题 (通用)
        question_title = await self._safe_text(page, "h1.QuestionHeader-title", "未知问题")

        for i in range(start, actual_limit):
            item = answers.nth(i)
            try:
                data = await self._parse_answer_element(item, page, question_title)
                results.append(data)
            except Exception as e:
                print(f"⚠️ 跳过第 {i+1} 个回答: {e}")
        
        return results

    async def _click_view_all(self, page):
        """点击‘查看全部’按钮的封装。"""
        try:
            view_all_btn = page.get_by_text("查看全部")
            if await view_all_btn.count() > 0:
                print("👆 发现 '查看全部' 按钮，尝试点击...")
                await view_all_btn.first.click()
                await asyncio.sleep(2)
            else:
                 view_all_btn_alt = page.locator(".QuestionMainAction")
                 if await view_all_btn_alt.count() > 0:
                     print("👆 发现 '.QuestionMainAction' 按钮，尝试点击...")
                     await view_all_btn_alt.first.click()
                     await asyncio.sleep(2)
                 else:
                    btns = page.locator("button")
                    count = await btns.count()
                    for i in range(count):
                        txt = await btns.nth(i).inner_text()
                        if "查看全部" in txt or "View All" in txt:
                            print(f"👆 发现按钮 '{txt}'，尝试点击...")
                            await btns.nth(i).click()
                            await asyncio.sleep(2)
                            break
        except Exception as e:
            print(f"⚠️  点击 '查看全部' 按钮失败或无需点击: {e}")

    async def _extract_answer(self, page) -> dict:
        """提取单个回答。"""
        text = await page.locator("body").inner_text()
        if "40362" in text:
            raise Exception("触发知乎反爬 (40362)")

        # 增加等待时间，改用更宽泛的选择器，避免 strictly waiting for .QuestionAnswer-content
        try:
            # 优先等待回答主体，给 15s 超时
            await page.wait_for_selector(".ContentItem.AnswerItem", timeout=15000)
        except:
            print("⚠️  等待回答内容超时，尝试直接解析...")
        
        # 尝试从 URL 提取 answer_id
        answer_id = None
        match = re.search(r"answer/(\d+)", self.url)
        if match:
            answer_id = match.group(1)
            
        # 确定内容容器
        container = page.locator(".ContentItem.AnswerItem").first
        
        if answer_id:
            # 尝试精确定位
            specific_item = page.locator(f".ContentItem.AnswerItem[name='{answer_id}']")
            if await specific_item.count() > 0:
                print(f"🎯 定位到指定回答: {answer_id}")
                container = specific_item.first
            else:
                zop_item = page.locator(f".ContentItem.AnswerItem[data-zop*='{answer_id}']")
                if await zop_item.count() > 0:
                    print(f"🎯 通过 data-zop 定位到指定回答: {answer_id}")
                    container = zop_item.first
        
        # 获取问题标题
        question_title = await self._safe_text(page, "h1.QuestionHeader-title", "未知问题")
        
        return await self._parse_answer_element(container, page, question_title)

    async def _parse_answer_element(self, element, page, question_title) -> dict:
        """解析单个回答元素"""
        # 作者
        author = await self._safe_text(element, ".AuthorInfo-name .UserLink-link", "未知作者")
        if author == "未知作者":
            author = await self._safe_text(element, ".AuthorInfo span.UserLink-Name", "未知作者")
        
        # 赞同数
        upvotes_text = await self._safe_text(element, "button.VoteButton--up", "0")
        # 提取数字, e.g. "赞同 1.2 万" -> 12000
        upvotes = self._parse_upvotes(upvotes_text)

        # 发布时间
        date = await self._extract_date(element)
        
        # 内容 HTML
        rich = element.locator(".RichText").first
        if await rich.count() > 0:
            html = await rich.inner_html()
        else:
             html = "<p>无法获取内容</p>"

        return {
            "title": question_title.strip(), 
            "author": author.strip(), 
            "html": html, 
            "date": date,
            "upvotes": upvotes
        }

    def _parse_upvotes(self, text: str) -> int:
        """解析赞同数文本。"""
        # e.g. "赞同 1,234", "1.2 万", "750"
        m = re.search(r"([\d\.,]+)\s*([万kK]?)", text)
        if not m: return 0
        num_str = m.group(1).replace(",", "")
        unit = m.group(2).lower()
        try:
            val = float(num_str)
            if unit == "万": val *= 10000
            elif unit in ("k", "K"): val *= 1000
            return int(val)
        except:
            return 0

    async def _extract_date(self, element) -> str:
        from datetime import date as dt_date
        try:
            # 1. 尝试找 meta (适用于 Page 或包含 meta 的容器)
            meta = await element.locator('meta[itemprop="datePublished"]').get_attribute("content", timeout=500)
            if meta: return meta[:10]
        except: pass
        
        try:
            # 2. 尝试找 "发布于 ..." 文本 (适用于 AnswerItem)
            text = await element.locator(".ContentItem-time").first.inner_text(timeout=500)
            m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
            if m: return m.group(1)
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
    async def download_images(cls, img_urls: List[str], dest: Path) -> dict[str, str]:
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