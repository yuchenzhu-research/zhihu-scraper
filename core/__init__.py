"""
Core 模块 - 知乎爬虫核心组件
"""

__all__ = [
    "ZhihuDownloader",
    "ZhihuConverter",
    "get_config",
    "get_logger",
    "get_humanizer",
    "ZhihuScraperError",
    "extract_urls",
    "sanitize_filename",
    "detect_url_type",
]


def __getattr__(name: str):
    if name == "ZhihuDownloader":
        from .scraper import ZhihuDownloader

        return ZhihuDownloader
    if name == "ZhihuConverter":
        from .converter import ZhihuConverter

        return ZhihuConverter
    if name in {"get_config", "get_logger"}:
        from .config import get_config, get_logger

        return {"get_config": get_config, "get_logger": get_logger}[name]
    if name == "get_humanizer":
        from .humanizer import get_humanizer

        return get_humanizer
    if name == "ZhihuScraperError":
        from .errors import ZhihuScraperError

        return ZhihuScraperError
    if name in {"extract_urls", "sanitize_filename", "detect_url_type"}:
        from .utils import detect_url_type, extract_urls, sanitize_filename

        return {
            "extract_urls": extract_urls,
            "sanitize_filename": sanitize_filename,
            "detect_url_type": detect_url_type,
        }[name]
    raise AttributeError(name)
