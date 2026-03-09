"""
utils.py - Universal Utility Functions

Provides reusable utility functions across the entire project.

================================================================================
utils.py — 通用工具函数集合

提供全项目复用的工具函数。
================================================================================
"""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional


# ============================================================
# URL Extraction / URL 提取
# ============================================================

_ZHIHU_URL_PATTERN = re.compile(
    r"(?:https?://)?"                                    # Optional protocol / 可选协议
    r"(?:www\.|zhuanlan\.)?"                             # zhihu.com or zhuanlan.zhihu.com
    r"zhihu\.com/"
    r"(?:p/\d+|question/\d+(?:/answer/\d+)?)"           # article / answer / question
)


def extract_urls(text: str) -> List[str]:
    """
    Extract Zhihu links from any text content.
    从任意文本内容中提取知乎链接。

    Supported URL formats:
    - Column article: https://zhuanlan.zhihu.com/p/123456
    - Single answer: https://www.zhihu.com/question/123/answer/456
    - Question page: https://www.zhihu.com/question/123

    Args:
        text: Input text containing URLs / 包含 URL 的输入文本

    Returns:
        List of unique URLs with protocol prefix / 去重后的 URL 列表（含协议头）
    """
    matches = _ZHIHU_URL_PATTERN.findall(text)
    results = []
    for m in matches:
        if not m.startswith("http"):
            m = "https://" + m
        results.append(m)
    return list(dict.fromkeys(results))


def detect_url_type(url: str) -> str:
    """
    Detect the type of a Zhihu URL.
    检测知乎 URL 的类型。

    Args:
        url: Zhihu URL / 知乎链接

    Returns:
        URL type: 'article', 'answer', 'question', or 'unknown'
        URL 类型: 'article', 'answer', 'question', 或 'unknown'
    """
    url = url.lower()
    if "zhuanlan.zhihu.com" in url:
        return "article"
    if "/answer/" in url:
        return "answer"
    if "/question/" in url:
        return "question"
    return "unknown"


def extract_id_from_url(url: str) -> Optional[str]:
    """
    Extract the ID from a Zhihu URL.
    从知乎 URL 中提取 ID。

    Examples:
        - https://zhuanlan.zhihu.com/p/123456 → '123456'
        - https://www.zhihu.com/question/123/answer/456 → '456'

    Args:
        url: Zhihu URL / 知乎链接

    Returns:
        Extracted ID or None if not found / 提取的 ID，未找到返回 None
    """
    # Article ID: /p/{id}
    article_match = re.search(r"/p/(\d+)", url)
    if article_match:
        return article_match.group(1)

    # Answer ID: /answer/{id}
    answer_match = re.search(r"/answer/(\d+)", url)
    if answer_match:
        return answer_match.group(1)

    # Question ID (used when viewing question page): /question/{id}
    question_match = re.search(r"/question/(\d+)(?:/|$)", url)
    if question_match:
        return question_match.group(1)

    return None


def extract_creator_token(value: str) -> Optional[str]:
    """
    Extract Zhihu creator token from a profile URL or accept a raw token.
    从知乎用户主页 URL 中提取用户 token，或直接接受裸 token。
    """
    value = value.strip()
    if not value:
        return None

    if re.fullmatch(r"[A-Za-z0-9._-]+", value):
        return value

    match = re.search(r"(?:https?://)?www\.zhihu\.com/people/([^/?#]+)", value)
    if match:
        return match.group(1)

    return None


# ============================================================
# Filename Sanitization / 文件名清洗
# ============================================================

def sanitize_filename(name: str, max_length: int = 50) -> str:
    """
    Sanitize string to be safely used as filename.
    清洗字符串以安全用作文件名。

    Removes or replaces:
    - / \\ : * ? " < > | (control characters)

    Args:
        name: Original filename / 原始文件名
        max_length: Maximum length limit / 最大长度限制

    Returns:
        Sanitized filename / 清洗后的文件名
    """
    name = re.sub(r"[/\\:*?\"<>|\x00-\x1f]", "_", name)
    name = name.strip(" .")
    return name[:max_length] or "untitled"


def sanitize_author_name(name: str) -> str:
    """
    Sanitize author name (often contains special characters).
    清洗作者名称。

    Args:
        name: Original author name / 原始作者名

    Returns:
        Sanitized name / 清洗后的名称
    """
    # Remove extra whitespace and special chars
    name = re.sub(r'\s+', ' ', name)
    return sanitize_filename(name, max_length=30)


# ============================================================
# Image URL Processing / 图片 URL 处理
# ============================================================

def get_image_base_name(url: str) -> str:
    """
    Get base name from image URL for deduplication.
    从图片 URL 获取基础名称（用于去重）。

    Zhihu image naming rules:
    - v2-abc123_720w.jpg → v2-abc123.jpg
    - v2-abc123_r.jpg → v2-abc123.jpg
    - v2-abc123_l.jpg → v2-abc123.jpg

    Args:
        url: Image URL / 图片 URL

    Returns:
        Base name without size suffix / 去重后的基础名称
    """
    base_name = url.split("/")[-1].split("?")[0]

    for suffix in ["_720w", "_r", "_l"]:
        if base_name.endswith(suffix + ".jpg"):
            return base_name.replace(suffix + ".jpg", ".jpg")
        if base_name.endswith(suffix + ".png"):
            return base_name.replace(suffix + ".png", ".png")

    return base_name


# ============================================================
# Time / Date Utilities / 时间日期工具
# ============================================================

def parse_zhihu_timestamp(timestamp: int) -> str:
    """
    Convert Unix timestamp to ISO format date string.
    将 Unix 时间戳转换为 ISO 格式日期字符串。

    Args:
        timestamp: Unix timestamp / Unix 时间戳

    Returns:
        ISO date string like '2026-03-03' / ISO 日期字符串
    """
    from datetime import datetime
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")


def get_today_date() -> str:
    """
    Get today's date in standard format.
    获取今天的日期（标准格式）。

    Returns:
        Date string like '2026-03-03' / 日期字符串
    """
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")


# ============================================================
# Markdown Utilities / Markdown 工具
# ============================================================

def make_markdown_header(title: str, level: int = 1) -> str:
    """
    Create a markdown header.
    创建 Markdown 标题。

    Args:
        title: Header text / 标题文本
        level: Header level (1-6) / 标题级别 (1-6)

    Returns:
        Markdown header string / Markdown 标题字符串
    """
    if level < 1:
        level = 1
    if level > 6:
        level = 6
    return "#" * level + " " + title


def make_markdown_link(text: str, url: str) -> str:
    """
    Create a markdown link.
    创建 Markdown 链接。

    Args:
        text: Link text / 链接文本
        url: Link URL / 链接 URL

    Returns:
        Markdown link string / Markdown 链接字符串
    """
    return f"[{text}]({url})"


# ============================================================
# Configuration Helpers / 配置辅助
# ============================================================

def resolve_path(path: str, base_dir: Optional[Path] = None) -> Path:
    """
    Resolve path, supporting relative and absolute paths.
    解析路径，支持相对路径和绝对路径。

    Args:
        path: Path string / 路径字符串
        base_dir: Base directory for relative paths / 相对路径的基准目录

    Returns:
        Resolved absolute Path / 解析后的绝对 Path
    """
    p = Path(path)
    if not p.is_absolute() and base_dir:
        p = base_dir / p
    return p.resolve()


def merge_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge two dictionaries recursively.
    递归合并两个字典。

    Args:
        base: Base dictionary / 基础字典
        override: Override dictionary / 覆盖字典

    Returns:
        Merged result / 合并后的结果
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


# ============================================================
# Logging Helpers / 日志辅助
# ============================================================

def log_error_context(error: Exception, extra_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Create a context dictionary for error logging.
    创建错误日志的上下文字典。

    Args:
        error: Exception object / 异常对象
        extra_context: Additional context / 额外上下文

    Returns:
        Context dictionary ready for logging / 准备用于日志的上下文字典
    """
    context = {
        "error_type": type(error).__name__,
        "error_message": str(error),
    }
    if extra_context:
        context.update(extra_context)
    return context


# Example / 示例
if __name__ == "__main__":
    # Test URL extraction
    test_text = """
    Check out this article: https://zhuanlan.zhihu.com/p/123456
    And this answer: https://www.zhihu.com/question/789/answer/123
    """
    print("Extracted URLs:", extract_urls(test_text))

    # Test ID extraction
    url = "https://zhuanlan.zhihu.com/p/123456"
    print(f"ID from {url}:", extract_id_from_url(url))

    # Test filename sanitization
    print("Sanitized filename:", sanitize_filename('test/file:name?"<>|.txt'))
