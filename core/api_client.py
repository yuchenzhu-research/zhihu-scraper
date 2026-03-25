"""
api_client.py - Pure Protocol Zhihu API Client (v3.0 Core)

Uses curl_cffi to simulate real browser TLS fingerprints for bypassing WAF,
and generates x-zse-96 signatures with z_core.js + execjs for browser-free scraping.

================================================================================
api_client.py — 纯协议层知乎 API 客户端 (v3.0 核弹)

利用 curl_cffi 模拟真实浏览器 TLS 指纹绕过 WAF，
配合 z_core.js 和 execjs 生成 x-zse-96 签名实现免浏览器纯净抓取。
================================================================================
"""

import json
import re
import urllib.parse
from pathlib import Path
from typing import Optional, Dict

import execjs
from curl_cffi import requests

from .config import get_logger, summarize_text_for_logs
from .cookie_manager import cookie_manager

# Default global JS signature interpreter path
# 默认全局 JS 签名解释器路径
ZHIHU_JS_PATH = Path(__file__).parent.parent / "static" / "z_core.js"


class ZhihuAPIClient:
    """
    Chinese: 纯协议层 API 客户端，负责签名生成和 API 请求
    English: Pure protocol API client responsible for signature generation and API requests
    """

    def __init__(self):
        self.log = get_logger()
        self._js_ctx = self._init_js_context()
        self.session = None
        self._cookies_dict = None

        # Initialize Session / 初始化 Session
        self._init_session()

    def _init_session(self) -> None:
        """
        Build network fingerprint and headers from CookieManager's current main session
        从 CookieManager 获取当前主 Session 构建网络指纹与头
        """
        self._cookies_dict = cookie_manager.get_current_session() or {}

        # Re-initialize underlying curl handshake even when switching proxies
        # 即使只切代理也重新初始化底层的 curl 握手
        self.session = requests.Session(impersonate="chrome110")

        # Base request headers / 基础请求头
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.zhihu.com/",
        })
        # Inject user cookies / 注入用户 Cookie
        if self._cookies_dict:
            for k, v in self._cookies_dict.items():
                self.session.cookies.set(k, v, domain=".zhihu.com")

    def _init_js_context(self):
        """
        Initialize PyExecJS execution environment for generating x-zse-96
        初始化 PyExecJS 执行环境，用于生成 x-zse-96
        """
        if ZHIHU_JS_PATH.exists():
            try:
                with open(ZHIHU_JS_PATH, "r", encoding="utf-8") as f:
                    js_code = f.read()
                return execjs.compile(js_code)
            except Exception as e:
                self.log.error("init_js_failed", error=str(e))
        return None

    def _get_signature(self, api_path: str) -> Dict[str, str]:
        """
        Generate x-zse-96 signature request headers for specific API path
        为特定的 API Path 生成 x-zse-96 签名请求头
        """
        if not self._js_ctx:
            return {}
        try:
            # One of the salt values for signature is d_c0 from cookies
            # 签名的盐值之一是 Cookie 里的 d_c0
            d_c0 = self._cookies_dict.get("d_c0", "SEARCH_ME")
            sig_headers = self._js_ctx.call("get_sign", api_path, f"d_c0={d_c0}")
            return sig_headers
        except Exception as e:
            self.log.warning("get_signature_failed", path=api_path, error=str(e))
            return {}

    def _build_article_headers(self, referer: str) -> Dict[str, str]:
        """
        Build document-style headers for Zhihu column HTML requests.
        为知乎专栏 HTML 请求构建更接近真实导航行为的请求头。
        """
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": referer,
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Upgrade-Insecure-Requests": "1",
        }

    def _warmup_article_origin(self) -> None:
        """
        Warm up the zhuanlan origin before fetching a specific article page.
        在抓具体专栏页之前，先对专栏域名做一次轻量预热。
        """
        warmup_url = "https://zhuanlan.zhihu.com/"
        warmup_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Referer": "https://www.zhihu.com/",
            "Upgrade-Insecure-Requests": "1",
        }
        try:
            response = self.session.get(
                warmup_url,
                headers=warmup_headers,
                timeout=10.0,
            )
            self.log.info("article_html_warmup", status=response.status_code, url=warmup_url)
        except Exception as e:
            self.log.warning("article_html_warmup_failed", error=str(e), url=warmup_url)

    def _parse_article_payload(self, article_id: str, html: str) -> Optional[dict]:
        """
        Parse `js-initialData` from a Zhihu column HTML document.
        从知乎专栏 HTML 中解析 `js-initialData`。
        """
        match = re.search(r'id="js-initialData" type="text/json">([^<]+)</script>', html)
        if not match:
            return None

        data = json.loads(match.group(1))
        entities = data.get("initialState", {}).get("entities", {})
        articles = entities.get("articles", {})
        if str(article_id) not in articles:
            return None

        art = articles[str(article_id)]
        return {
            "title": art.get("title", ""),
            "content": art.get("content", ""),
            "author": {"name": art.get("author", {}).get("name", "未知作者")},
            "voteup_count": art.get("voteupCount", 0),
            "created": art.get("created", 0),
            "image_url": art.get("imageUrl", ""),
        }

    def fetch_api(self, path: str) -> Optional[dict]:
        """
        General API fetch method that encapsulates signature and exception handling
        通用 API 获取方法，封装了签名与异常处理
        """
        url = f"https://www.zhihu.com{path}"

        # Get dynamic signature for current path
        # 获取针对当前路径的动态签名
        sig_headers = self._get_signature(path)

        req_headers = {}
        if sig_headers:
            req_headers.update(sig_headers)

        try:
            self.log.info("api_request", url=url)
            # Use curl_cffi for fingerprint-level request
            # 使用 curl_cffi 进行指纹级请求
            response = self.session.get(url, headers=req_headers, timeout=15.0)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 403:
                self.log.error(
                    "api_forbidden",
                    status=403,
                    response_preview=summarize_text_for_logs(response.text, kind="response"),
                )
                # Trigger rotation and notify upstream to retry
                # 触发轮换并通知上游进行一次重试
                cookie_manager.rotate_session()
                # Reload underlying session / 重新载入底层 session
                self._init_session()
                raise Exception("请求遭到知乎安全盾 403 拦截，已尝试轮换 Cookie 池。")
            else:
                self.log.error("api_error", status=response.status_code)
                return None
        except Exception as e:
            self.log.error("api_fetch_failed", error=str(e))
            raise

    def get_answer(self, answer_id: str) -> dict:
        """
        Get detailed data for a single answer (including HTML content)
        获取单个回答的详细数据 (包含 HTML 正文)
        """
        # Include parameters for complete answer data from Zhihu API
        # 知乎回答完整数据的请求 Include 参数
        include = (
            "data[*].is_normal,admin_closed_comment,reward_info,is_collapsed,"
            "annotation_action,annotation_detail,collapse_reason,is_sticky,collapsed_by,"
            "suggest_edit,comment_count,can_comment,content,editable_content,attachment,"
            "voteup_count,reshipment_settings,comment_permission,created_time,updated_time,"
            "review_info,relevant_info,question,excerpt,is_labeled,paid_info,paid_info_content,"
            "reaction_instruction,relationship.is_authorized,is_author,voting,is_thanked,"
            "is_nothelp,is_recognized;data[*].mark_infos[*].url;data[*].author.follower_count,"
            "vip_info,badge[*].topics;data[*].settings.table_of_content.enabled"
        )
        path = f"/api/v4/answers/{answer_id}?include={urllib.parse.quote(include)}"
        data = self.fetch_api(path)
        if not data:
            raise Exception(f"回答 {answer_id} 数据抓取失败。")
        return data

    def get_article(self, article_id: str) -> dict:
        """
        Get detailed data for column articles via protocol HTML fetch.
        The flow is:
        1. warm up the zhuanlan origin
        2. fetch article HTML and parse `js-initialData`
        3. if the first attempt fails, rotate cookies and retry once

        通过协议层 HTML 请求获取专栏文章数据。
        流程为：
        1. 预热专栏域名
        2. 获取文章 HTML 并解析 `js-initialData`
        3. 首轮失败时轮换 Cookie 并重试一次
        """
        url = f"https://zhuanlan.zhihu.com/p/{article_id}"
        referer = "https://zhuanlan.zhihu.com/"
        last_error = "未知错误"

        for attempt in (1, 2):
            self.log.info("article_html_attempt", article_id=article_id, attempt=attempt, url=url)
            if attempt == 2:
                print("🔁 专栏阶段 2/3: 已轮换 Cookie，正在重试协议路径...")
            self._warmup_article_origin()
            try:
                response = self.session.get(
                    url,
                    headers=self._build_article_headers(referer),
                    timeout=15.0,
                )
            except Exception as e:
                last_error = f"HTML 请求异常: {e}"
                self.log.error(
                    "article_html_request_failed",
                    article_id=article_id,
                    attempt=attempt,
                    error=str(e),
                )
            else:
                if response.status_code == 200:
                    parsed = self._parse_article_payload(article_id, response.text)
                    if parsed:
                        self.log.info(
                            "article_html_success",
                            article_id=article_id,
                            attempt=attempt,
                            title=parsed.get("title", "")[:80],
                        )
                        return parsed

                    last_error = "HTML 返回 200，但未解析到 js-initialData 文章实体"
                    self.log.warning(
                        "article_html_missing_payload",
                        article_id=article_id,
                        attempt=attempt,
                        response_preview=summarize_text_for_logs(response.text, kind="html"),
                    )
                else:
                    last_error = f"HTML 请求返回 HTTP {response.status_code}"
                    log_event = "article_forbidden" if response.status_code == 403 else "article_html_unexpected_status"
                    self.log.error(
                        log_event,
                        article_id=article_id,
                        attempt=attempt,
                        status=response.status_code,
                    )

            if attempt == 1:
                rotated = cookie_manager.rotate_session()
                self._init_session()
                self.log.warning(
                    "article_cookie_rotated_retry",
                    article_id=article_id,
                    rotated=bool(rotated),
                )

        self.log.error("article_fetch_failed", article_id=article_id, error=last_error)
        raise Exception(f"专栏协议抓取失败：{last_error}")

    def get_question_answers_page(self, question_id: str, limit: int = 3, offset: int = 0) -> dict:
        """
        Get one paginated page of answers under a question.
        获取问题回答列表的一页数据，并保留分页信息。
        """
        page_limit = max(1, min(limit, 20))
        include = (
            "data[*].is_normal,admin_closed_comment,reward_info,is_collapsed,annotation_action,"
            "annotation_detail,collapse_reason,is_sticky,collapsed_by,suggest_edit,comment_count,"
            "can_comment,content,editable_content,attachment,voteup_count,reshipment_settings,"
            "comment_permission,created_time,updated_time,review_info,relevant_info,question,"
            "excerpt,is_labeled,paid_info,paid_info_content,reaction_instruction,"
            "relationship.is_authorized,is_author,voting,is_thanked,is_nothelp,is_recognized;"
            "data[*].mark_infos[*].url;data[*].author.follower_count,vip_info,badge[*].topics;"
            "data[*].settings.table_of_content.enabled"
        )
        path = f"/api/v4/questions/{question_id}/answers?include={urllib.parse.quote(include)}&limit={page_limit}&offset={offset}&platform=desktop&sort_by=default"
        data = self.fetch_api(path)
        if not data or "data" not in data:
            return {"data": [], "paging": {"is_end": True}}

        paging = data.get("paging") or {}
        return {
            "data": data.get("data", []),
            "paging": {
                "is_end": bool(paging.get("is_end", len(data.get("data", [])) < page_limit)),
                "totals": paging.get("totals"),
                "next": paging.get("next"),
            },
        }

    def get_question_answers(self, question_id: str, limit: int = 3, offset: int = 0) -> list:
        """
        Get paginated list of answers under a question.
        获取问题下的一批回答列表数据。
        """
        page = self.get_question_answers_page(question_id, limit=limit, offset=offset)
        return page.get("data", [])

    def get_creator_profile(self, url_token: str) -> dict:
        """
        Get creator profile information.
        获取创作者资料信息。
        """
        include = (
            "id,name,headline,description,url_token,avatar_url,avatar_url_template,"
            "answer_count,articles_count,question_count,zvideo_count,columns_count,"
            "follower_count,following_count,voteup_count"
        )
        path = f"/api/v4/members/{url_token}?include={urllib.parse.quote(include)}"
        data = self.fetch_api(path)
        if not data:
            raise Exception(f"作者 {url_token} 资料抓取失败。")
        return data

    def get_creator_answers_page(self, url_token: str, limit: int = 20, offset: int = 0) -> dict:
        """
        Get one paginated page of answers from a creator.
        获取某个作者回答列表的一页数据。
        """
        page_limit = max(1, min(limit, 20))
        include = (
            "data[*].is_normal,admin_closed_comment,reward_info,is_collapsed,"
            "annotation_action,annotation_detail,collapse_reason,suggest_edit,"
            "comment_count,can_comment,content,attachment,voteup_count,"
            "comment_permission,created_time,updated_time,question,excerpt,"
            "reaction_instruction,is_author,voting,is_thanked,is_nothelp,"
            "is_recognized;data[*].mark_infos[*].url;data[*].author.follower_count,"
            "vip_info,badge[*].topics"
        )
        path = (
            f"/api/v4/members/{url_token}/answers?"
            f"include={urllib.parse.quote(include)}&offset={offset}&limit={page_limit}&order_by=created"
        )
        data = self.fetch_api(path)
        if not data or "data" not in data:
            return {"data": [], "paging": {"is_end": True}}

        paging = data.get("paging") or {}
        return {
            "data": data.get("data", []),
            "paging": {
                "is_end": bool(paging.get("is_end", len(data.get("data", [])) < page_limit)),
                "totals": paging.get("totals"),
                "next": paging.get("next"),
            },
        }

    def get_creator_articles_page(self, url_token: str, limit: int = 20, offset: int = 0) -> dict:
        """
        Get one paginated page of articles from a creator.
        获取某个作者专栏列表的一页数据。
        """
        page_limit = max(1, min(limit, 20))
        include = (
            "data[*].comment_count,is_normal,thumbnail,can_comment,comment_permission,"
            "admin_closed_comment,content,voteup_count,created,updated,"
            "reaction_instruction;data[*].author.badge[*].topics;data[*].author.vip_info"
        )
        path = (
            f"/api/v4/members/{url_token}/articles?"
            f"include={urllib.parse.quote(include)}&offset={offset}&limit={page_limit}&order_by=created"
        )
        data = self.fetch_api(path)
        if not data or "data" not in data:
            return {"data": [], "paging": {"is_end": True}}

        paging = data.get("paging") or {}
        return {
            "data": data.get("data", []),
            "paging": {
                "is_end": bool(paging.get("is_end", len(data.get("data", [])) < page_limit)),
                "totals": paging.get("totals"),
                "next": paging.get("next"),
            },
        }

    def get_collection_page(self, collection_id: str, limit: int = 20, offset: int = 0) -> dict:
        """
        Get detailed content of a collection page (articles or answers), includes paging info
        获取收藏夹某页的详细内容（文章或回答），并包含 paging 信息
        """
        include = (
            "data[*].content.is_normal,admin_closed_comment,reward_info,is_collapsed,"
            "annotation_action,annotation_detail,collapse_reason,is_sticky,collapsed_by,"
            "suggest_edit,comment_count,can_comment,content,editable_content,attachment,"
            "voteup_count,reshipment_settings,comment_permission,created_time,updated_time,"
            "review_info,relevant_info,question,excerpt,is_labeled,paid_info,paid_info_content,"
            "reaction_instruction,relationship.is_authorized,is_author,voting,is_thanked,"
            "is_nothelp,is_recognized;data[*].content.author.follower_count,vip_info,badge[*].topics"
        )
        path = f"/api/v4/collections/{collection_id}/items?offset={offset}&limit={limit}&include={urllib.parse.quote(include)}"
        data = self.fetch_api(path)
        if not data:
            return {"data": [], "paging": {"is_end": True}}
        return data
