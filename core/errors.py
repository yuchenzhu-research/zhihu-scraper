"""
errors.py - Error Handling System

Defines Zhihu scraper exception classifications, supporting smart retry and error recovery.

================================================================================
errors.py — 错误处理体系

定义知乎爬虫的异常分类，支持智能重试和错误恢复。
================================================================================
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from pathlib import Path

from .structlog_compat import BoundLoggerBase, structlog


class ErrorSeverity(Enum):
    """
    Error severity level / 错误严重级别
    """
    FATAL = auto()       # Config error, signature failure - no retry, code fix needed
                         # 配置错误、签名失败 - 不重试，需修复代码
    RETRIABLE = auto()   # Network timeout, element not found - can retry
                         # 网络超时、元素未找到 - 可重试
    RECOVERABLE = auto() # Single answer failed - skip and continue
                         # 单个回答失败 - 跳过继续，不影响其他任务


class ErrorCategory(Enum):
    """
    Error classification / 错误分类
    """
    NETWORK = auto()          # Network related / 网络相关
    ANTI_DETECTION = auto()   # Anti-crawling detection / 反爬检测
    PARSE = auto()            # Parse failure / 解析失败
    CONTENT = auto()          # Content not exists / 内容不存在
    CONFIG = auto()           # Config error / 配置错误
    BROWSER = auto()          # Browser related / 浏览器相关
    UNKNOWN = auto()          # Unknown error / 未知错误


@dataclass
class ZhihuScraperError(Exception):
    """
    Base exception for Zhihu scraper / 知乎爬虫基类异常

    Attributes:
        message: Error message / 错误信息
        severity: Severity level / 严重级别
        category: Error category / 错误分类
        context: Additional context information / 额外上下文信息
        recoverable_hint: Hint for recoverable action / 可恢复操作的提示
    """
    message: str
    severity: ErrorSeverity = ErrorSeverity.RETRIABLE
    category: ErrorCategory = ErrorCategory.UNKNOWN
    context: Dict[str, Any] = field(default_factory=dict)
    recoverable_hint: Optional[str] = None

    def __str__(self) -> str:
        return self.message

    def to_log_dict(self) -> Dict[str, Any]:
        """
        Convert to log dictionary / 转换为日志字典
        """
        return {
            "message": self.message,
            "severity": self.severity.name,
            "category": self.category.name,
            "context": self.context,
            "recoverable_hint": self.recoverable_hint,
        }


class NetworkError(ZhihuScraperError):
    """
    Network request failed / 网络请求失败
    """
    def __init__(
        self,
        message: str = "Network request failed / 网络请求失败",
        url: Optional[str] = None,
        status_code: Optional[int] = None,
        timeout: bool = False,
        **kwargs
    ):
        context = {}
        if url:
            context["url"] = url
        if status_code:
            context["status_code"] = status_code
        if timeout:
            context["timeout"] = True

        super().__init__(
            message=message,
            severity=ErrorSeverity.RETRIABLE,
            category=ErrorCategory.NETWORK,
            context=context,
            recoverable_hint="Wait for network recovery and retry automatically / 等待网络恢复后自动重试",
            **kwargs
        )


class AntiDetectionError(ZhihuScraperError):
    """
    Triggered anti-crawling mechanism / 触发反爬机制
    """
    def __init__(
        self,
        message: str = "Triggered Zhihu anti-crawling mechanism / 触发知乎反爬机制",
        detection_type: Optional[str] = None,
        **kwargs
    ):
        context = {}
        if detection_type:
            context["detection_type"] = detection_type

        super().__init__(
            message=message,
            severity=ErrorSeverity.FATAL,
            category=ErrorCategory.ANTI_DETECTION,
            context=context,
            recoverable_hint="Please change IP or wait before retrying / 请更换 IP 或等待一段时间后重试",
            **kwargs
        )


class ContentParseError(ZhihuScraperError):
    """
    Content parsing failed / 内容解析失败
    """
    def __init__(
        self,
        message: str = "Content parsing failed / 内容解析失败",
        selector: Optional[str] = None,
        element_type: Optional[str] = None,
        **kwargs
    ):
        context = {}
        if selector:
            context["selector"] = selector
        if element_type:
            context["element_type"] = element_type

        hint_map = {
            "title": "Page structure may have updated, check selector / 页面结构可能已更新，检查选择器",
            "content": "Content container selector invalid / 内容容器选择器失效",
            "author": "Author info extraction failed / 作者信息提取失败",
        }

        super().__init__(
            message=message,
            severity=ErrorSeverity.RECOVERABLE,
            category=ErrorCategory.PARSE,
            context=context,
            recoverable_hint=hint_map.get(element_type or "", "Skip this content / 跳过此内容"),
            **kwargs
        )


class ContentNotFoundError(ZhihuScraperError):
    """
    Content does not exist / 内容不存在
    """
    def __init__(
        self,
        message: str = "Content does not exist / 内容不存在",
        content_type: str = "unknown",
        identifier: Optional[str] = None,
        **kwargs
    ):
        context = {"content_type": content_type}
        if identifier:
            context["identifier"] = identifier

        type_names = {
            "question": "Question / 问题",
            "answer": "Answer / 回答",
            "article": "Article / 文章",
        }

        display_type = type_names.get(content_type, content_type)
        super().__init__(
            message=f"{display_type} does not exist or has been deleted / {display_type}不存在或已被删除",
            severity=ErrorSeverity.RECOVERABLE,
            category=ErrorCategory.CONTENT,
            context=context,
            recoverable_hint=f"This {display_type} may have been deleted or set to private / 该{display_type}可能已被删除或设为私密",
            **kwargs
        )


class ConfigError(ZhihuScraperError):
    """
    Configuration error / 配置错误
    """
    def __init__(
        self,
        message: str = "Configuration error / 配置错误",
        config_key: Optional[str] = None,
        **kwargs
    ):
        context = {}
        if config_key:
            context["config_key"] = config_key

        super().__init__(
            message=message,
            severity=ErrorSeverity.FATAL,
            category=ErrorCategory.CONFIG,
            context=context,
            recoverable_hint="Please check configuration file and fix errors / 请检查配置文件并修正错误",
            **kwargs
        )


class BrowserError(ZhihuScraperError):
    """
    Browser-related error / 浏览器相关错误
    """
    def __init__(
        self,
        message: str = "Browser operation failed / 浏览器操作失败",
        operation: Optional[str] = None,
        **kwargs
    ):
        context = {}
        if operation:
            context["operation"] = operation

        super().__init__(
            message=message,
            severity=ErrorSeverity.RETRIABLE,
            category=ErrorCategory.BROWSER,
            context=context,
            recoverable_hint="Browser may be unresponsive, try resetting browser context / 浏览器可能无响应，尝试重置浏览器上下文",
            **kwargs
        )


class ImageDownloadError(ZhihuScraperError):
    """
    Image download failed / 图片下载失败
    """
    def __init__(
        self,
        message: str = "Image download failed / 图片下载失败",
        url: Optional[str] = None,
        path: Optional[Path] = None,
        **kwargs
    ):
        context = {}
        if url:
            context["url"] = url
        if path:
            context["path"] = str(path)

        super().__init__(
            message=message,
            severity=ErrorSeverity.RECOVERABLE,
            category=ErrorCategory.UNKNOWN,
            context=context,
            recoverable_hint="Will skip this image and continue processing other content / 将跳过此图片，继续处理其他内容",
            **kwargs
        )


# ============================================================
# Error Handling Utility Functions (错误处理工具函数)
# ============================================================

def classify_error(error: Exception) -> ZhihuScraperError:
    """
    Classify generic exception into scraper-specific exception
    将通用异常分类为爬虫特定异常

    Args:
        error: Caught exception / 捕获的异常

    Returns:
        Classified exception object / 分类后的异常对象
    """
    error_msg = str(error).lower()

    # Network related / 网络相关
    if "timeout" in error_msg or "连接" in error_msg or "connection" in error_msg:
        return NetworkError(message=str(error), timeout="timeout" in error_msg)

    # Anti-crawling related / 反爬相关
    if any(kw in error_msg for kw in ["403", "40362", "反爬", "verify", "captcha", "ant"]):
        if "403" in error_msg or "40362" in error_msg:
            return AntiDetectionError(
                message="Triggered Zhihu anti-crawling mechanism (403) / 触发知乎反爬机制 (403)",
                detection_type="rate_limit"
            )
        return AntiDetectionError(message="Triggered anti-crawling detection / 触发反爬检测")

    # Content not exists / 内容不存在
    if any(kw in error_msg for kw in ["不存在", "已删除", "404", "not found", "gone"]):
        return ContentNotFoundError(message=str(error))

    # Config error / 配置错误
    if any(kw in error_msg for kw in ["config", "yaml", "cookie"]):
        return ConfigError(message=str(error))

    # If known exception, return directly
    # 如果是已知异常，直接返回
    if isinstance(error, ZhihuScraperError):
        return error

    # Unknown error wrapper / 未知错误包装
    return ZhihuScraperError(
        message=str(error)[:200],
        category=ErrorCategory.UNKNOWN,
        context={"original_type": type(error).__name__},
    )


def handle_error(error: Exception, logger: Optional[BoundLoggerBase] = None) -> None:
    """
    Unified entry point for exception handling
    处理异常的统一入口

    Args:
        error: Caught exception / 捕获的异常
        logger: Optional logger / 可选的日志记录器
    """
    scraper_error = classify_error(error)

    if logger is None:
        logger = structlog.get_logger()

    log_method = {
        ErrorSeverity.FATAL: logger.error,
        ErrorSeverity.RETRIABLE: logger.warning,
        ErrorSeverity.RECOVERABLE: logger.warning,
    }.get(scraper_error.severity, logger.warning)

    log_method(
        "error_occurred",
        **scraper_error.to_log_dict()
    )

    # Print recovery hint if available / 如果有恢复提示，也打印
    if scraper_error.recoverable_hint:
        logger.info("hint", message=scraper_error.recoverable_hint)

    return scraper_error
