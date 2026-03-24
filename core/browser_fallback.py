"""
browser_fallback.py - Intelligent Fallback Mechanism for Heavily Protected Routes

When pure API requests (curl_cffi) encounter Zhihu Columns' extremely strict WAF,
quickly activate the Playwright instance in the background and use the browser's
native execution environment to read the final rendered HTML DOM, then pass it
to upstream converter for Markdown reconstruction.

================================================================================
browser_fallback.py — 针对强风控路由的智能降维回退机制

当纯 API 请求 (curl_cffi) 遭遇知乎专栏等极度严苛的 WAF 时，
迅速唤醒后台的 Playwright 实例，并直接利用浏览器的原生执行环境，
读取页面最终渲染好的 HTML DOM，交还给上游转换器进行 Markdown 重构。
================================================================================
"""

from typing import Optional, Dict, Any
from .config import get_config, get_logger


async def _launch_browser_with_fallback(playwright: Any, browser_cfg: Any, *, headless: bool):
    """
    Try configured browser channel first, then fall back to bundled Chromium.
    先按配置的浏览器通道启动，失败后再回退到 Playwright 自带 Chromium。
    """
    log = get_logger()
    launch_args = browser_cfg.args or [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
    ]
    launch_kwargs = {
        "headless": headless,
        "args": launch_args,
    }

    channel = (browser_cfg.channel or "").strip()
    if channel:
        try:
            return await playwright.chromium.launch(**{**launch_kwargs, "channel": channel})
        except Exception as e:
            log.warning("browser_channel_launch_failed", channel=channel, error=str(e))

    return await playwright.chromium.launch(**launch_kwargs)


async def extract_zhuanlan_html(
    article_id: str,
    session_cookies: Optional[Dict[str, str]] = None,
    *,
    headless: bool = True,
) -> Optional[dict]:
    """
    Fetch column article data through Playwright silent rendering.

    Returns a dictionary format that should match api_client.get_article() as much as possible
    for seamless integration with upstream converters.

    通过 Playwright 静默渲染专栏文章获取数据。
    返回的字典格式要和 api_client.get_article() 尽量保持一致，以便无缝对接。

    Args:
        article_id: Zhihu column article ID (e.g., 123456 from zhuanlan.zhihu.com/p/123456)
        session_cookies: Optional session cookies to inject

    Returns:
        Dict with keys: title, content, author, voteup_count, created, image_url
        or None if extraction failed
    """
    from playwright.async_api import async_playwright
    import re

    log = get_logger()
    browser_cfg = get_config().zhihu.browser
    url = f"https://zhuanlan.zhihu.com/p/{article_id}"
    log.info("trigger_browser_fallback", url=url)

    async with async_playwright() as p:
        browser = await _launch_browser_with_fallback(p, browser_cfg, headless=headless)

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            viewport=browser_cfg.viewport,
        )

        # Inject cookie tickets to avoid redirection to homepage login wall
        # 注入 Cookie 票据 (避免被弹到首页重定向登录)
        if session_cookies:
            # Zhihu strictly validates domain, must be precise
            # 知乎强校验 domain, 必须精确
            mapped_cookies = []
            for k, v in session_cookies.items():
                mapped_cookies.append({
                    "name": k,
                    "value": v,
                    "domain": ".zhihu.com",
                    "path": "/",
                    "secure": True,
                    "httpOnly": False,
                    "sameSite": "Lax"
                })
            await context.add_cookies(mapped_cookies)
            log.info("fallback_cookies_injected", count=len(mapped_cookies))

        page = await context.new_page()

        try:
            # JS engine is responsible for cracking zse-ck shield, then render column
            # JS 引擎负责解开 zse-ck 的盾，随后才能渲染专栏
            await page.goto(url, wait_until="domcontentloaded", timeout=browser_cfg.timeout)

            # Check if redirected to homepage login wall
            # 检测是否被重定向到首页登录墙
            if page.url == "https://www.zhihu.com/" or "signin" in page.url:
                raise Exception("Cookie 已失效，专栏强制重定向到了登录页。")

            # Wait for main content (Post-RichTextContainer is the unique content container for columns)
            # 等待正文内容出现 (Post-RichTextContainer 就是专栏特有的正文容器)
            await page.wait_for_selector(".Post-RichTextContainer", timeout=browser_cfg.timeout)

            # Get page information / 获取页面信息
            title = await page.title()
            title = re.sub(r' - 知乎$', '', title).strip()

            author_name = "Unknown Author"  # 未知作者
            try:
                author_elem = await page.wait_for_selector(".AuthorInfo-name", timeout=3000)
                if author_elem:
                    author_name = await author_elem.inner_text()
            except Exception:
                pass

            # Extract upvotes / 提取点赞数
            voteup_count = 0
            try:
                vote_btn = await page.wait_for_selector("button.VoteButton--up", timeout=3000)
                if vote_btn:
                    vote_text = await vote_btn.get_attribute("aria-label") or ""
                    match = re.search(r"赞同 (\d+)", vote_text)
                    if match:
                        voteup_count = int(match.group(1))
            except Exception:
                pass

            # Scrape complete rich text content HTML
            # 抓取完整的富文本内容 HTML
            content_html = ""
            content_elem = await page.query_selector(".Post-RichTextContainer")
            if content_elem:
                content_html = await content_elem.inner_html()

            # Extract header image / 提炼头图
            image_url = ""
            try:
                header_img = await page.query_selector("img.TitleImage")
                if header_img:
                    image_url = await header_img.get_attribute("src") or ""
            except Exception:
                pass

            log.info("browser_fallback_success", title=title, length=len(content_html))

            return {
                "title": title,
                "content": content_html,
                "author": {"name": author_name},
                "voteup_count": voteup_count,
                "created": 0,  # Skip extracting time, fallback scenario focuses on content
                "image_url": image_url
            }

        except Exception as e:
            html_dump = await page.content()
            log.error("browser_fallback_failed", error=str(e), html_snippet=html_dump[:500])
            print("==== 页面内容 DEBUG ====")
            print(html_dump[:1000])
            return None
        finally:
            await browser.close()
