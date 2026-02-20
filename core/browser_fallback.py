"""
core/browser_fallback.py — 针对强风控路由的智能降维回退机制

当纯 API 请求 (curl_cffi) 遭遇知乎专栏等极度严苛的 WAF 时，
迅速唤醒后台的 Playwright 实例，并直接利用浏览器的原生执行环境，
读取页面最终渲染好的 HTML DOM，交还给上游转换器进行 Markdown 重构。
"""

from typing import Optional, Dict
from .config import get_logger

async def extract_zhuanlan_html(article_id: str, session_cookies: Optional[Dict[str, str]] = None) -> Optional[dict]:
    """
    通过 Playwright 静默渲染专栏文章获取数据。
    返回的字典格式要和 api_client.get_article() 尽量保持一致，以便无缝对接。
    """
    from playwright.async_api import async_playwright
    import re

    log = get_logger()
    url = f"https://zhuanlan.zhihu.com/p/{article_id}"
    log.info("trigger_browser_fallback", url=url)

    async with async_playwright() as p:
        # 使用真实的 Chrome 浏览器类型降低风险
        browser = await p.chromium.launch(headless=True, args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox"
        ])
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )

        # 注入 Cookie 票据 (避免被弹到首页重定向登录)
        if session_cookies:
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
            # JS 引擎负责解开 zse-ck 的盾，随后才能渲染专栏
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            
            # 检测是否被重定向到首页登录墙
            if page.url == "https://www.zhihu.com/" or "signin" in page.url:
                raise Exception("Cookie 已失效，专栏强制重定向到了登录页。")
            
            # 等待正文内容出现 (Post-RichTextContainer 就是专栏特有的正文容器)
            await page.wait_for_selector(".Post-RichTextContainer", timeout=10000)

            # 获取页面信息
            title = await page.title()
            title = re.sub(r' - 知乎$', '', title).strip()

            author_name = "未知作者"
            try:
                author_elem = await page.wait_for_selector(".AuthorInfo-name", timeout=3000)
                if author_elem:
                    author_name = await author_elem.inner_text()
            except Exception:
                pass

            # 提取点赞数
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

            # 抓取完整的富文本内容 HTML
            content_html = ""
            content_elem = await page.query_selector(".Post-RichTextContainer")
            if content_elem:
                content_html = await content_elem.inner_html()

            # 提炼头图
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
                "created": 0, # 这里不费劲提时间了，Fallback 场景能保住图文是最重要的
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
