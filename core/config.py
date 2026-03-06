"""
config.py - Configuration Management Module

Provides unified configuration loading, validation, and environment variable override.
Uses YAML format configuration files, supports defaults and type safety.

================================================================================
config.py — 配置管理模块

提供统一的配置加载、验证和环境变量覆盖功能。
使用 YAML 格式的配置文件，支持默认值和类型安全。
================================================================================
"""

from pathlib import Path
from typing import Any, Dict, Optional, Union
from dataclasses import dataclass, field

import yaml
import structlog

# ============================================================
# Configuration Data Classes (配置数据类)
# ============================================================

@dataclass
class BrowserConfig:
    """
    Browser configuration / 浏览器配置
    """
    headless: bool = True
    timeout: int = 30000
    viewport: Dict[str, int] = field(default_factory=lambda: {"width": 1920, "height": 1080})
    channel: str = "chrome"
    args: list = field(default_factory=list)

@dataclass
class AntiDetectionConfig:
    """
    Anti-crawling configuration / 反爬配置
    """
    stealth: bool = True
    webgl: bool = True
    navigator: bool = True

@dataclass
class SignatureConfig:
    """
    Signature algorithm configuration / 签名算法配置
    """
    enabled: bool = False

@dataclass
class ZhihuConfig:
    """
    Zhihu-related configuration / 知乎相关配置
    """
    cookies_file: str = "cookies.json"
    cookies_required: bool = True
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    anti_detection: AntiDetectionConfig = field(default_factory=AntiDetectionConfig)
    signature: SignatureConfig = field(default_factory=SignatureConfig)

@dataclass
class RetryConfig:
    """
    Retry configuration / 重试配置
    """
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True

@dataclass
class ScrollConfig:
    """
    Scroll configuration / 滚动配置
    """
    timeout: int = 60000
    pause: int = 1000
    viewport_height: int = 800

@dataclass
class HumanizeConfig:
    """
    Human behavior simulation configuration / 人类行为模拟配置
    """
    enabled: bool = True
    min_delay: float = 1.0       # Minimum request interval (seconds) / 最小请求间隔 (秒)
    max_delay: float = 3.0       # Maximum request interval (seconds) / 最大请求间隔 (秒)
    scroll_delay: float = 0.5    # Wait after scrolling (seconds) / 滚动后等待 (秒)
    page_load_delay: float = 2.0 # Wait after page load (seconds) / 页面加载后等待 (秒)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "HumanizeConfig":
        """
        Build from dictionary, support backward compatibility
        从字典构建，支持向后兼容
        """
        return cls(
            enabled=raw.get("enabled", True),
            min_delay=raw.get("min_delay", 1.0),
            max_delay=raw.get("max_delay", 3.0),
            scroll_delay=raw.get("scroll_delay", 0.5),
            page_load_delay=raw.get("page_load_delay", 2.0),
        )

@dataclass
class ImagesConfig:
    """
    Image download configuration / 图片下载配置
    """
    concurrency: int = 4
    timeout: float = 30.0
    referer: str = "https://www.zhihu.com/"

@dataclass
class CrawlerConfig:
    """
    General crawler configuration / 爬虫通用配置
    """
    retry: RetryConfig = field(default_factory=RetryConfig)
    scroll: ScrollConfig = field(default_factory=ScrollConfig)
    humanize: HumanizeConfig = field(default_factory=HumanizeConfig)
    images: ImagesConfig = field(default_factory=ImagesConfig)

@dataclass
class OutputConfig:
    """
    Export configuration / 导出配置
    """
    directory: str = "data"
    format: str = "markdown"
    images_subdir: str = "images"
    folder_format: str = "[{date}] {title}"

@dataclass
class LoggingConfig:
    """
    Logging configuration / 日志配置
    """
    level: str = "INFO"
    format: str = "console"
    file: Optional[str] = None
    log_exceptions: bool = True

@dataclass
class Config:
    """
    Main configuration class / 主配置类
    """
    zhihu: ZhihuConfig
    crawler: CrawlerConfig
    output: OutputConfig
    logging: LoggingConfig

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Config":
        """
        Build configuration from dictionary
        从字典构建配置
        """
        # Parse Zhihu configuration / 解析知乎配置
        zhihu_raw = raw.get("zhihu", {})
        zhihu = ZhihuConfig(
            cookies_file=zhihu_raw.get("cookies", {}).get("file", "cookies.json"),
            cookies_required=zhihu_raw.get("cookies", {}).get("required", True),
            browser=BrowserConfig(**zhihu_raw.get("browser", {})),
            anti_detection=AntiDetectionConfig(**zhihu_raw.get("anti_detection", {})),
            signature=SignatureConfig(**zhihu_raw.get("signature", {})),
        )

        # Parse crawler configuration / 解析爬虫配置
        crawler_raw = raw.get("crawler", {})
        crawler = CrawlerConfig(
            retry=RetryConfig(**crawler_raw.get("retry", {})),
            scroll=ScrollConfig(**crawler_raw.get("scroll", {})),
            humanize=HumanizeConfig.from_dict(crawler_raw.get("humanize", {})),
            images=ImagesConfig(**crawler_raw.get("images", {})),
        )

        # Parse export configuration / 解析导出配置
        output = OutputConfig(**raw.get("output", {}))

        # Parse logging configuration / 解析日志配置
        logging_cfg = LoggingConfig(**raw.get("logging", {}))

        return cls(
            zhihu=zhihu,
            crawler=crawler,
            output=output,
            logging=logging_cfg,
        )

# ============================================================
# Configuration Loader (配置加载器)
# ============================================================

class ConfigLoader:
    """
    Configuration loader supporting multiple paths and defaults
    配置加载器，支持多路径和默认值
    """

    _instance: Optional["ConfigLoader"] = None
    _config: Optional[Config] = None

    def __new__(cls) -> "ConfigLoader":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

    def load(
        self,
        config_path: Optional[Union[str, Path]] = None,
        *,
        override_level: Optional[str] = None,
    ) -> Config:
        """
        Load configuration file
        加载配置文件

        Args:
            config_path: Configuration file path (default: config.yaml in project root)
            override_level: Optional environment variable override level (DEBUG/INFO/WARNING/ERROR)
        """
        if self._config is not None:
            return self._config

        if config_path is None:
            # Default search in project root directory
            # 默认查找项目根目录
            root = get_project_root()
            config_path = root / "config.yaml"
        else:
            config_path = Path(config_path)

        if not config_path.exists():
            self._log_missing_config(config_path)
            self._config = self._get_default_config()
            return self._config

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}

            self._config = Config.from_dict(raw)

            # Environment variable override / 环境变量覆盖
            if override_level:
                self._config.logging.level = override_level

            # Set logging level (must be done before returning)
            # 设置日志级别（必须在返回前）
            setup_logging(self._config)

            return self._config

        except Exception as e:
            print(f"⚠️ Configuration file load failed: {e}")
            print("  Using default configuration / 使用默认配置")
            self._config = self._get_default_config()
            setup_logging(self._config)
            return self._config

    def _get_default_config(self) -> Config:
        """
        Get default configuration (when config file doesn't exist or parsing fails)
        获取默认配置（当配置文件不存在或解析失败时）
        """
        return Config(
            zhihu=ZhihuConfig(),
            crawler=CrawlerConfig(),
            output=OutputConfig(),
            logging=LoggingConfig(),
        )

    def _log_missing_config(self, path: Path) -> None:
        log = structlog.get_logger()
        log.warning("config_file_not_found", path=str(path), using_defaults=True)

    def get(self) -> Config:
        """
        Get loaded configuration / 获取已加载的配置
        """
        if self._config is None:
            return self.load()
        return self._config

    def reload(self, config_path: Optional[Union[str, Path]] = None) -> Config:
        """
        Reload configuration / 重新加载配置
        """
        self._config = None
        return self.load(config_path)


def get_config(config_path: Optional[Union[str, Path]] = None) -> Config:
    """
    Convenience function to get configuration
    便捷函数：获取配置
    """
    loader = ConfigLoader()
    return loader.load(config_path)


def get_project_root() -> Path:
    """
    Get project root path
    获取项目根目录
    """
    return Path(__file__).parent.parent


def resolve_project_path(path: Union[str, Path]) -> Path:
    """
    Resolve relative paths against project root
    将相对路径解析为项目根目录下的绝对路径
    """
    path = Path(path)
    if path.is_absolute():
        return path
    return get_project_root() / path


# ============================================================
# Logging System (日志系统)
# ============================================================

def setup_logging(config: Union[Config, LoggingConfig]) -> None:
    """
    Initialize structured logging system
    初始化结构化日志系统
    """
    if isinstance(config, Config):
        log_config = config.logging
    else:
        log_config = config

    import logging

    log_level = getattr(logging, log_config.level.upper(), logging.INFO)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if log_config.format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    handlers = [logging.StreamHandler()]
    if log_config.file:
        log_path = resolve_project_path(log_config.file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(log_level)

    for handler in handlers:
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

    structlog.configure(
        processors=shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


# ============================================================
# Human Behavior Simulation (Humanize) / 人类行为模拟
# ============================================================

import asyncio
from random import uniform
from contextlib import asynccontextmanager


def get_logger(name: str = "zhihu-scraper") -> structlog.BoundLoggerBase:
    """
    Get structured logger
    获取结构化日志记录器
    """
    return structlog.get_logger(name)


class Humanizer:
    """
    Human behavior simulator - random delays to simulate human operations
    人类行为模拟器 - 随机延迟以模拟真人操作

    Usage:
        await humanize.random_delay()      # Random request interval
        await humanize.page_load()         # Wait after page load
        await humanize.scroll()            # Wait after scroll

    用法:
        await humanize.random_delay()      # 随机请求间隔
        await humanize.page_load()         # 页面加载等待
        await humanize.scroll()            # 滚动后等待
    """

    def __init__(self, config: Optional[HumanizeConfig] = None):
        self._config = config

    @property
    def config(self) -> HumanizeConfig:
        """
        Get configuration, singleton pattern to avoid repeated loading
        获取配置，单例模式避免重复加载
        """
        if self._config is None:
            try:
                cfg = get_config()
                self._config = cfg.crawler.humanize
            except Exception:
                # Use safe defaults if config loading fails
                # 如果配置加载失败，使用安全默认值
                self._config = HumanizeConfig()
        return self._config

    def random_delay(self, min_delay: Optional[float] = None, max_delay: Optional[float] = None) -> asyncio.sleep:
        """
        Random delay simulating human request interval
        随机延迟，模拟人类请求间隔
        """
        if not self.config.enabled:
            return  # No delay when disabled / 禁用时不做延迟

        min_d = min_delay if min_delay is not None else self.config.min_delay
        max_d = max_delay if max_delay is not None else self.config.max_delay

        delay = uniform(min_d, max_d)
        return asyncio.sleep(delay)

    async def page_load(self) -> None:
        """
        Wait after page load, simulating reading/rendering time
        页面加载后等待，模拟阅读/渲染时间
        """
        if not self.config.enabled:
            return

        delay = self.config.page_load_delay
        await asyncio.sleep(delay)

    async def scroll(self) -> None:
        """
        Wait after scroll, simulating content loading
        滚动后等待，模拟内容加载
        """
        if not self.config.enabled:
            return

        delay = self.config.scroll_delay
        await asyncio.sleep(delay)

    async def before_action(self, action: str = "request") -> None:
        """
        Wait before action
        操作前等待
        """
        if not self.config.enabled:
            return

        delays = {
            "request": (self.config.min_delay, self.config.max_delay),
            "click": (0.2, 0.5),
            "scroll": (self.config.scroll_delay, self.config.scroll_delay + 0.3),
            "type": (0.05, 0.15),
        }

        min_d, max_d = delays.get(action, delays["request"])
        await asyncio.sleep(uniform(min_d, max_d))


# Global Humanizer instance / 全局 Humanizer 实例
_humanizer: Optional[Humanizer] = None


def get_humanizer() -> Humanizer:
    """
    Get global Humanizer instance
    获取全局 Humanizer 实例
    """
    global _humanizer
    if _humanizer is None:
        try:
            cfg = get_config()
            _humanizer = Humanizer(cfg.crawler.humanize)
        except Exception:
            _humanizer = Humanizer()
    return _humanizer


@asynccontextmanager
async def humanize(action: str = "request"):
    """
    Context manager form of delay
    上下文管理器形式的延迟

    Usage:
        async with humanize("request"):
            await page.goto(url)
    """
    h = get_humanizer()
    await h.before_action(action)
    yield
