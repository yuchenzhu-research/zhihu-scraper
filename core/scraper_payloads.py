"""
scraper_payloads.py - Pure payload normalization helpers for scraper workflows.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict


def format_zhihu_date(timestamp: int) -> str:
    """Convert a Zhihu timestamp into YYYY-MM-DD with a safe today fallback."""
    if timestamp:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
    return datetime.today().strftime("%Y-%m-%d")


def build_article_item(*, url: str, article_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize article API payload into the internal item shape."""
    author = data.get("author", {}).get("name", "未知作者")
    title = data.get("title", "未知专栏标题")
    html = data.get("content", "")
    title_img = data.get("image_url")
    if title_img:
        html = f'<img src="{title_img}" alt="TitleImage"><br>{html}'

    return {
        "id": article_id,
        "type": "article",
        "url": url,
        "title": title.strip(),
        "author": author.strip(),
        "html": html,
        "date": format_zhihu_date(data.get("created", 0)),
        "upvotes": data.get("voteup_count", 0),
    }


def build_answer_item(*, url: str, answer_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize single-answer API payload into the internal item shape."""
    author = data.get("author", {}).get("name", "未知作者")
    title = data.get("question", {}).get("title", "未知问题")

    return {
        "id": answer_id,
        "type": "answer",
        "url": url,
        "title": title.strip(),
        "author": author.strip(),
        "html": data.get("content", ""),
        "date": format_zhihu_date(data.get("created_time", 0)),
        "upvotes": data.get("voteup_count", 0),
    }


def build_question_answer_item(*, question_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize one question-page answer into the internal item shape."""
    answer_id = str(data.get("id", ""))
    author = data.get("author", {}).get("name", "未知作者")
    title = data.get("question", {}).get("title", "未知问题")
    return {
        "id": answer_id,
        "type": "answer",
        "url": f"https://www.zhihu.com/question/{question_id}/answer/{answer_id}",
        "title": title.strip(),
        "author": author.strip(),
        "html": data.get("content", ""),
        "date": format_zhihu_date(data.get("created_time", 0)),
        "upvotes": data.get("voteup_count", 0),
    }


def build_creator_profile_payload(url_token: str, creator_profile: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize creator profile payload into the public metadata shape."""
    effective_token = creator_profile.get("url_token", url_token)
    return {
        "user_id": creator_profile.get("id", ""),
        "name": creator_profile.get("name", url_token),
        "url_token": effective_token,
        "headline": creator_profile.get("headline", ""),
        "description": creator_profile.get("description", ""),
        "profile_url": f"https://www.zhihu.com/people/{effective_token}",
        "avatar_url": creator_profile.get("avatar_url") or creator_profile.get("avatar_url_template", ""),
        "follower_count": creator_profile.get("follower_count", 0),
        "following_count": creator_profile.get("following_count", 0),
        "voteup_count": creator_profile.get("voteup_count", 0),
        "answer_count": creator_profile.get("answer_count", 0),
        "articles_count": creator_profile.get("articles_count", 0),
        "question_count": creator_profile.get("question_count", 0),
        "video_count": creator_profile.get("zvideo_count", 0),
        "column_count": creator_profile.get("columns_count", 0),
    }


def build_empty_sync_stats(target_limit: int) -> Dict[str, Any]:
    """Build default sync stats for disabled or empty content types."""
    return {
        "requested_limit": target_limit,
        "saved_count": 0,
        "pages_fetched": 0,
        "last_offset": 0,
        "reached_end": target_limit == 0,
        "stopped_early": False,
    }


def build_creator_answer_item(*, url_token: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize creator-answer payload into the internal item shape."""
    answer_id = str(data.get("id", ""))
    question = data.get("question", {}) or {}
    question_id = question.get("id", "")
    author = data.get("author", {}).get("name", "未知作者")
    return {
        "id": answer_id,
        "type": "answer",
        "url": f"https://www.zhihu.com/question/{question_id}/answer/{answer_id}" if question_id else f"https://www.zhihu.com/answer/{answer_id}",
        "title": (question.get("title") or "未知问题").strip(),
        "author": author.strip(),
        "html": data.get("content", ""),
        "date": format_zhihu_date(data.get("created_time", 0)),
        "upvotes": data.get("voteup_count", 0),
        "creator_url_token": url_token,
    }


def build_creator_article_item(*, url_token: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize creator-article payload into the internal item shape."""
    article_id = str(data.get("id", ""))
    author = data.get("author", {}).get("name", "未知作者")
    created_sec = data.get("created", 0) or data.get("updated", 0)
    html = data.get("content", "")
    image_url = data.get("image_url") or data.get("thumbnail")
    if image_url:
        html = f'<img src="{image_url}" alt="TitleImage"><br>{html}'

    return {
        "id": article_id,
        "type": "article",
        "url": f"https://zhuanlan.zhihu.com/p/{article_id}",
        "title": (data.get("title") or "未知专栏标题").strip(),
        "author": author.strip(),
        "html": html,
        "date": format_zhihu_date(created_sec),
        "upvotes": data.get("voteup_count", 0),
        "creator_url_token": url_token,
    }
