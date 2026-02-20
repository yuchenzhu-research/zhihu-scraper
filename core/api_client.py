"""
api_client.py — 纯协议层知乎 API 客户端 (v3.0 核弹)

利用 curl_cffi 模拟真实浏览器 TLS 指纹绕过 WAF，
配合 z_core.js 和 execjs 生成 x-zse-96 签名实现免浏览器纯净抓取。
"""

import json
import urllib.parse
from pathlib import Path
from typing import Optional, Dict

import execjs
from curl_cffi import requests

from .config import get_logger
from .cookie_manager import cookie_manager

# 默认全局 JS 签名解释器路径
ZHIHU_JS_PATH = Path(__file__).parent.parent / "static" / "z_core.js"
COOKIES_PATH = Path(__file__).parent.parent / "cookies.json"

class ZhihuAPIClient:
    def __init__(self):
        self.log = get_logger()
        self._js_ctx = self._init_js_context()
        self.session = None
        self._cookies_dict = None
        
        # 初始化 Session
        self._init_session()

    def _init_session(self) -> None:
        """从 CookieManager 获取当前主 Session 构建网络指纹与头"""
        self._cookies_dict = cookie_manager.get_current_session() or {}
        
        # 即使只切代理也重新初始化底层的 curl 握手
        self.session = requests.Session(impersonate="chrome110")
        
        # 基础请求头
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.zhihu.com/",
        })
        # 注入用户 Cookie
        if self._cookies_dict:
            for k, v in self._cookies_dict.items():
                self.session.cookies.set(k, v, domain=".zhihu.com")

    def _init_js_context(self):
        """初始化 PyExecJS 执行环境，用于生成 x-zse-96。"""
        if ZHIHU_JS_PATH.exists():
            try:
                with open(ZHIHU_JS_PATH, "r", encoding="utf-8") as f:
                    js_code = f.read()
                return execjs.compile(js_code)
            except Exception as e:
                self.log.error("init_js_failed", error=str(e))
        return None

    def _get_signature(self, api_path: str) -> Dict[str, str]:
        """为特定的 API Path 生成 x-zse-96 签名请求头。"""
        if not self._js_ctx:
            return {}
        try:
            # 签名的盐值之一是 Cookie 里的 d_c0
            d_c0 = self._cookies_dict.get("d_c0", "SEARCH_ME")
            sig_headers = self._js_ctx.call("get_sign", api_path, f"d_c0={d_c0}")
            return sig_headers
        except Exception as e:
            self.log.warning("get_signature_failed", path=api_path, error=str(e))
            return {}

    def fetch_api(self, path: str) -> Optional[dict]:
        """通用 API 获取方法，封装了签名与异常处理。"""
        url = f"https://www.zhihu.com{path}"
        
        # 获取针对当前路径的动态签名
        sig_headers = self._get_signature(path)
        
        req_headers = {}
        if sig_headers:
            req_headers.update(sig_headers)
            
        try:
            self.log.info("api_request", url=url)
            # 使用 curl_cffi 进行指纹级请求
            response = self.session.get(url, headers=req_headers, timeout=15.0)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 403:
                self.log.error("api_forbidden", status=403, text=response.text[:200])
                # 触发轮换并通知上游进行一次重试 (由业务代码或手动递归控制)
                cookie_manager.rotate_session()
                # 重新载入底层 session
                self._init_session()
                raise Exception("请求遭到知乎安全盾 403 拦截，已尝试轮换 Cookie 池。")
            else:
                self.log.error("api_error", status=response.status_code)
                return None
        except Exception as e:
            self.log.error("api_fetch_failed", error=str(e))
            raise

    def get_answer(self, answer_id: str) -> dict:
        """获取单个回答的详细数据 (包含 HTML 正文)。"""
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
        """获取专栏文章的详细数据 (回退到 SSR json 解析，防 403)。"""
        url = f"https://zhuanlan.zhihu.com/p/{article_id}"
        self.log.info("article_request", url=url)
        try:
            response = self.session.get(url, timeout=15.0)
            if response.status_code == 200:
                import re
                match = re.search(r'id="js-initialData" type="text/json">([^<]+)</script>', response.text)
                if match:
                    data = json.loads(match.group(1))
                    entities = data.get("initialState", {}).get("entities", {})
                    articles = entities.get("articles", {})
                    if str(article_id) in articles:
                        art = articles[str(article_id)]
                        # Normalize format to match API response expectations in scraper.py
                        return {
                            "title": art.get("title", ""),
                            "content": art.get("content", ""),
                            "author": {"name": art.get("author", {}).get("name", "未知作者")},
                            "voteup_count": art.get("voteupCount", 0),
                            "created": art.get("created", 0),
                            "image_url": art.get("imageUrl", "")
                        }
            
            # If failed or blocked
            self.log.error("article_forbidden", status=response.status_code)
            raise Exception("请求专栏遭到知乎安全盾拦截，未找到文章数据。")
        except Exception as e:
            self.log.error("article_fetch_failed", error=str(e))
            raise

    def get_question_answers(self, question_id: str, limit: int = 3, offset: int = 0) -> list:
        """获取问题下的所有回答列表分页 (用于替代以前狂滚鼠标底部的逻辑)。"""
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
        path = f"/api/v4/questions/{question_id}/answers?include={urllib.parse.quote(include)}&limit={limit}&offset={offset}&platform=desktop&sort_by=default"
        data = self.fetch_api(path)
        if not data or "data" not in data:
            return []
        return data["data"]

    def get_collection_page(self, collection_id: str, limit: int = 20, offset: int = 0) -> dict:
        """获取收藏夹某页的详细内容（文章或回答），并包含 paging 信息。"""
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
