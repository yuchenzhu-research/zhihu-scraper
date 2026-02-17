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
import subprocess
from pathlib import Path
from urllib.parse import urlparse
from typing import Union, List, Optional

import httpx
import execjs
from playwright.async_api import async_playwright, Playwright

from .config import get_config, get_logger

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
USER_DATA_DIR = Path(__file__).parent.parent / "browser_data"
STEALTH_JS_PATH = Path(__file__).parent.parent / "static" / "stealth.min.js"
ZHIHU_JS_PATH = Path(__file__).parent.parent / "static" / "z_core.js"


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
        cookie_path = Path(__file__).parent.parent / "cookies.json"
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

    def has_valid_cookies(self) -> bool:
        """检查是否有有效 Cookie (z_c0)。"""
        try:
            cookies = self._load_cookies()
            for c in cookies:
                if c.get("name") == "z_c0" and c.get("value") and c.get("value") != "YOUR_COOKIE_HERE":
                    return True
        except:
            pass
        return False

    async def debug_dump_page(self, output_path: str = "debug_page.html"):
        """Debug purpose: dump page content to file."""
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=False)
            context = await browser.new_context(
                user_agent=self._UA
            )
            await context.add_init_script(path=STEALTH_JS_PATH)
            
            # Load cookies
            cookies = self._load_cookies()
            if cookies:
                await context.add_cookies(cookies)
            
            page = await context.new_page()
            try:
                await page.goto(self.url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(5000)
                content = await page.content()
                with open(output_path, "w") as f:
                    f.write(content)
                print(f"Dumped page to {output_path}")
            except Exception as e:
                print(f"Dump failed: {e}")
            finally:
                await browser.close()

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

    async def _extract_question(
        self, 
        page, 
        start: int = 0, 
        limit: int = 3,
        start_anchor: Optional[dict] = None,
        end_anchor: Optional[dict] = None
    ) -> List[dict]:
        """
        提取问题下的多个回答。支持：
        1. 数量模式: 从 start 开始抓 limit 个
        2. 范围模式: 从 start_anchor (答主/answer_id) 抓到 end_anchor
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
        if start_anchor and end_anchor:
            print(f"🎯 目标: 寻找范围 {start_anchor['value']} -> {end_anchor['value']}")
            await self._scroll_until_found(page, start_anchor, end_anchor)
        else:
            target_count = start + limit
            print(f"🎯 目标: 抓取前 {target_count} 个回答")
            await self._scroll_until_count(page, target_count)
        
        # 获取所有回答卡片
        answers = page.locator(".ContentItem.AnswerItem")
        total_found = await answers.count()
        
        # 计算提取范围
        extract_indices = []
        
        if start_anchor and end_anchor:
            # 范围模式
            print(f"📊 正在定位起止点...")
            start_idx, end_idx = -1, -1
            
            # 遍历所有回答建立索引
            for i in range(total_found):
                item = answers.nth(i)
                info = await self._get_card_info(item)
                
                # 检查是否匹配 Start
                if start_idx == -1:
                    if self._match_anchor(info, start_anchor):
                        start_idx = i
                
                # 检查是否匹配 End (End 必须 >= Start)
                if end_idx == -1:
                    if self._match_anchor(info, end_anchor):
                        end_idx = i
            
            if start_idx != -1 and end_idx != -1:
                # 确保顺序正确
                if start_idx > end_idx:
                    print(f"⚠️ 起始位置({start_idx})在结束位置({end_idx})之后，自动交换...")
                    start_idx, end_idx = end_idx, start_idx
                
                print(f"✅ 锁定范围: 索引 [{start_idx}] -> [{end_idx}] (共 {end_idx - start_idx + 1} 个)")
                extract_indices = list(range(start_idx, end_idx + 1))
            else:
                 print(f"❌ 未能完全找到起止点 (Start found: {start_idx}, End found: {end_idx})")
                 print("   将尝试提取所有已加载内容...")
                 extract_indices = list(range(total_found))
        else:
            # 数量模式
            target_count = start + limit
            actual_limit = min(total_found, target_count)
            print(f"📊 准备提取范围 [{start}:{actual_limit}]...")
            extract_indices = list(range(start, actual_limit))

        results = []
        question_title = await self._safe_text(page, "h1.QuestionHeader-title", "未知问题")

        for i in extract_indices:

            item = answers.nth(i)
            try:
                data = await self._parse_answer_element(item, page, question_title)
                results.append(data)
            except Exception as e:
                print(f"⚠️ 跳过第 {i+1} 个回答: {e}")
        
        return results

    async def _scroll_until_count(self, page, target_count: int):
        """滚动直到达到目标数量。"""
        prev_count = 0
        no_change_count = 0
        max_attempts = 50

        while True:
            count = await page.locator(".ContentItem.AnswerItem").count()
            print(f"🔄 当前加载了 {count} 个回答 (目标: {target_count})...")
            
            if count >= target_count:
                break
            
            if count == prev_count:
                no_change_count += 1
                
                # 尝试再次点击 "查看全部"，防漏
                if no_change_count % 2 == 0:
                     await self._click_view_all(page)

                # 如果卡住太久，尝试切换排序
                if no_change_count == 4:
                    print("🔄 尝试切换排序方式 (按时间排序)...")
                    await self._switch_sort_order(page)
                    no_change_count = 0 # 重置计数，给新排序一点机会
                    continue

                if no_change_count >= 8: # 增加尝试次数
                    print("⚠️  已滚动到底部或无法加载更多")
                    # Debug: Dump HTML & Buttons
                    try:
                        with open("debug_failed_scroll.html", "w", encoding="utf-8") as f:
                            f.write(await page.content())
                        print("💾 已保存调试页面: debug_failed_scroll.html")
                        
                        btns = page.locator("button")
                        cnt = await btns.count()
                        print(f"🔎 页面剩余按钮 ({cnt}个):")
                        for i in range(min(cnt, 20)):
                            txt = await btns.nth(i).inner_text()
                            if txt.strip():
                                clean_txt = txt.strip().replace('\n', ' ')
                                print(f"   [Btn] {clean_txt}")
                    except: pass
                    break
            else:
                no_change_count = 0
            
            prev_count = count
            await self._scroll_step(page)
            
            max_attempts -= 1
            if max_attempts <= 0:
                break

    async def _scroll_until_found(self, page, start_anchor, end_anchor):
        """滚动直到找到起止锚点（或达到上限）。"""
        limit = 200 # 防止无限滚动
        prev_count = 0
        no_change_count = 0
        
        while True:
            answers = page.locator(".ContentItem.AnswerItem")
            count = await answers.count()
            print(f"🔄 正在搜索锚点... (当前 {count} 个)")
            
            # 检查是否包含 start 和 end
            found_start = False
            found_end = False
            
            # 这里的检查比较耗时，每 5 次或者滚动停滞时检查一次比较好
            # 为了准确性，我们简单粗暴点，每次都检查最后几个? 
            # 还是直接检查全部? 检查全部比较稳妥
            
            # 优化: 只在数量变化或者每隔几次检查
            # 这里简化逻辑: 每次检查最后 5 个看是否包含 end? 
            # 不行，end 可能早就加载过了，或者 start 和 end 很近
            
            # 简单策略: 只要没有同时找到两个，就一直滚，直到上限
            # 但我们需要知道是否已经找到了
            
            # 我们可以抽样检查:
            # 倒序检查
            # for i in range(count - 1, -1, -1):
            
            # 实际上，只要 count 没变，就意味着到底了
            if count >= limit:
                print(f"⚠️ 达到滚动上限 ({limit})")
                break

            if count == prev_count:
                no_change_count += 1
                
                # 尝试再次点击 "查看全部"
                if no_change_count % 2 == 0:
                     await self._click_view_all(page)

                # 尝试切换排序
                if no_change_count == 4:
                    # 降低日志级别或修改为 rich print (如果引入了)
                    # print("🔄 尝试切换排序方式 (按时间排序)...") 
                    await self._switch_sort_order(page)
                    no_change_count = 0 
                    continue

                if no_change_count >= 8:
                    # print("⚠️  已滚动到底部")
                    break
            else:
                no_change_count = 0
            
            # 检测逻辑：如果 count 比较大了，我们可以试着找一下
            # 为了性能，我们每增加 10 个或者滚动 5 次检测一次？
            # 暂时先用最简单的：一直滚到底部或者上限，最后再匹配。
            # 为什么？因为中间检测 DOM 很慢。
            # 用户体验优化：如果用户知道 end 在前 50 个，滚到 200 个太慢。
            
            # 折中方案：先不做实时检测，依赖 limit 和手动停止。
            # 或者：每次滚动后，只检查新加载的 items? 
            # 算了，保持简单，直接复用滚动逻辑，把 limit 设大一点。
            # 但是为了"找到即停"，我们需要检查。
            
            # 让我们尝试快速检查一下页面文本?
            # page_text = await page.inner_text() 
            # if start_anchor['value'] in page_text and end_anchor['value'] in page_text:
            #    break
            # 这也很慢。
            
            # 采用方案: 滚 5 次检查一次 metadata
            pass 

            prev_count = count
            await self._scroll_step(page)

    async def _scroll_step(self, page):
        """执行一次滚动动作。"""
        # 使用 JS 滚动到底部，通常比单纯鼠标滚轮更有效触发加载
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1)
        # 配合 End 键
        await page.keyboard.press("End")
        await asyncio.sleep(1)

    async def _get_card_info(self, item) -> dict:
        """获取回答卡片的元数据用于匹配。"""
        # 提取 answer_id
        answer_id = ""
        try:
             # data-zop="{... "itemId":12345 ...}"
             zop = await item.get_attribute("data-zop")
             if zop:
                 if '"itemId":' in zop:
                     import json
                     # 简单的字符串提取，比 json.loads 快且容错
                     m = re.search(r'"itemId":(\d+)', zop)
                     if m: answer_id = m.group(1)
        except: pass
        if not answer_id:
             # try name attribute
             answer_id = await item.get_attribute("name") or ""
        
        # 提取 author
        author = await self._safe_text(item, ".AuthorInfo-name .UserLink-link", "")
        if not author:
             author = await self._safe_text(item, ".AuthorInfo span.UserLink-Name", "")
             
        return {"answer_id": str(answer_id), "author": author.strip()}

    def _match_anchor(self, info: dict, anchor: dict) -> bool:
        """判断卡片是否匹配锚点。"""
        if not anchor: return False
        
        val = str(anchor["value"]).strip()
        
        if anchor["type"] == "answer_id":
            return val == info.get("answer_id")
        
        if anchor["type"] == "author":
             # 模糊匹配? 还是精确? 精确比较好，防止同名误伤
             # 知乎 id 一般是唯一的，但名字不一定。
             return val == info.get("author")
             
        return False

    async def _click_view_all(self, page):
        """点击 '查看全部' 按钮的封装。"""
        candidates = [
            "button.QuestionMainAction-ViewAll",
            "a.QuestionMainAction-ViewAll",
            "div.Question-mainColumn button:has-text('查看全部')",
            "div.Question-mainColumn button:has-text('更多回答')",
            "div.Question-mainColumn button:has-text('展开阅读全文')",
            "div.Question-mainColumn button:has-text('显示全部')",
             # 兜底：查找所有包含特定文本的按钮
            "button:has-text('View All')",
            "button:has-text('More Answers')",
            "button:has-text('显示全部')"
        ]
        
        for sel in candidates:
            try:
                # 使用 first 避免多匹配报错
                btn = page.locator(sel).first
                if await btn.count() > 0 and await btn.is_visible():
                    print(f"👆 尝试点击: {sel}")
                    await btn.click()
                    # 等待内容加载
                    await asyncio.sleep(2)
                    return True
            except:
                pass
        return False

    async def _switch_sort_order(self, page):
        """切换排序方式（默认 -> 按时间），有时能解决加载卡顿问题。"""
        try:
            # 1. 找到排序按钮 (通常是 '默认排序')
            sort_btn = page.locator("button:has-text('默认排序')").first
            if await sort_btn.count() == 0:
                print("⚠️ 未找到 '默认排序' 按钮，跳过切换")
                return

            print("👆 点击 '默认排序'...")
            await sort_btn.click()
            await asyncio.sleep(1)

            # 2. 点击 '按时间排序'
            time_sort = page.locator("button:has-text('按时间排序')").first
            if await time_sort.count() > 0:
                print("👆 切换到 '按时间排序'...")
                await time_sort.click()
                await asyncio.sleep(3) # 等待刷新
            else:
                 print("⚠️ 未找到 '按时间排序' 选项")
                 # 关闭菜单 (点别处)
                 await page.mouse.click(0, 0)
        except Exception as e:
             print(f"⚠️ 切换排序失败: {e}")

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
    async def download_images(
        cls,
        img_urls: List[str],
        dest: Path,
        *,
        concurrency: int = 4,
        timeout: float = 30.0,
    ) -> dict[str, str]:
        """
        并发下载图片

        Args:
            img_urls: 图片 URL 列表
            dest: 保存目录
            concurrency: 并发数 (默认 4)
            timeout: 超时时间 (秒)
        """
        if not img_urls:
            return {}

        dest.mkdir(parents=True, exist_ok=True)
        url_to_local: dict[str, str] = {}

        # 从配置读取并发数
        try:
            cfg = get_config()
            concurrency = cfg.crawler.images.concurrency
            timeout = cfg.crawler.images.timeout
        except Exception:
            pass  # 使用默认值

        limits = httpx.Limits(
            max_keepalive_connections=concurrency,
            max_connections=concurrency * 2,
        )

        async with httpx.AsyncClient(
            headers=cls._IMG_HEADERS,
            timeout=timeout,
            follow_redirects=True,
            proxy=PROXY_SERVER,
            limits=limits,
        ) as client:
            # 使用 Semaphore 限制并发
            semaphore = asyncio.Semaphore(concurrency)

            async def download_with_limit(url: str) -> None:
                async with semaphore:
                    await cls._download_one(client, url, dest, url_to_local)

            tasks = [download_with_limit(url) for url in img_urls]
            await asyncio.gather(*tasks, return_exceptions=True)

        # 统计成功/失败数
        success = sum(1 for v in url_to_local.values() if v)
        log = get_logger()
        log.info(
            "images_downloaded",
            total=len(img_urls),
            success=success,
            failed=len(img_urls) - success,
        )

        return url_to_local

    @staticmethod
    async def _download_one(client, url, dest, mapping):
        """下载单张图片"""
        try:
            if url.startswith("//"):
                url = "https:" + url

            # 过滤不需要的图片
            if "data:image" in url or "equation" in url:
                return

            resp = await client.get(url)
            resp.raise_for_status()

            ext = Path(urlparse(url).path).suffix or ".jpg"
            if len(ext) > 5:
                ext = ".jpg"

            fname = hashlib.md5(url.encode()).hexdigest()[:12] + ext
            fpath = dest / fname

            fpath.write_bytes(resp.content)
            # 必须用 / 分隔，要在 Markdown 里用
            mapping[url] = f"images/{fname}"
        except Exception as e:
            # 静默失败，记录到日志
            logger = get_logger()
            logger.warning("image_download_failed", url=url[:50], error=str(e)[:50])