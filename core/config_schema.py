"""
config_schema.py - Configuration schema and parsing helpers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .runtime_paths import DEFAULT_COOKIE_FILE, DEFAULT_COOKIE_POOL_DIR, DEFAULT_LOG_FILE


@dataclass
class BrowserConfig:
    headless: bool = True
    timeout: int = 30000
    viewport: Dict[str, int] = field(default_factory=lambda: {"width": 1920, "height": 1080})
    channel: str = "chrome"
    args: list = field(default_factory=list)


@dataclass
class AntiDetectionConfig:
    stealth: bool = True
    webgl: bool = True
    navigator: bool = True


@dataclass
class SignatureConfig:
    enabled: bool = False


@dataclass
class ZhihuConfig:
    cookies_file: str = str(DEFAULT_COOKIE_FILE)
    cookies_pool_dir: str = str(DEFAULT_COOKIE_POOL_DIR)
    cookies_required: bool = True
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    anti_detection: AntiDetectionConfig = field(default_factory=AntiDetectionConfig)
    signature: SignatureConfig = field(default_factory=SignatureConfig)


@dataclass
class RetryConfig:
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True


@dataclass
class ScrollConfig:
    timeout: int = 60000
    pause: int = 1000
    viewport_height: int = 800


@dataclass
class HumanizeConfig:
    enabled: bool = True
    min_delay: float = 1.0
    max_delay: float = 3.0
    scroll_delay: float = 0.5
    page_load_delay: float = 2.0

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "HumanizeConfig":
        return cls(
            enabled=raw.get("enabled", True),
            min_delay=raw.get("min_delay", 1.0),
            max_delay=raw.get("max_delay", 3.0),
            scroll_delay=raw.get("scroll_delay", 0.5),
            page_load_delay=raw.get("page_load_delay", 2.0),
        )


@dataclass
class ImagesConfig:
    concurrency: int = 4
    timeout: float = 30.0
    referer: str = "https://www.zhihu.com/"


@dataclass
class CrawlerConfig:
    retry: RetryConfig = field(default_factory=RetryConfig)
    scroll: ScrollConfig = field(default_factory=ScrollConfig)
    humanize: HumanizeConfig = field(default_factory=HumanizeConfig)
    images: ImagesConfig = field(default_factory=ImagesConfig)


@dataclass
class OutputConfig:
    directory: str = "data"
    format: str = "markdown"
    images_subdir: str = "images"
    folder_format: str = "[{date}] {title}"
    download_images: Optional[bool] = None


@dataclass
class LoggingConfig:
    level: str = "INFO"
    format: str = "console"
    file: Optional[str] = str(DEFAULT_LOG_FILE)
    log_exceptions: bool = True


@dataclass
class Config:
    zhihu: ZhihuConfig
    crawler: CrawlerConfig
    output: OutputConfig
    logging: LoggingConfig

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Config":
        return build_config_from_dict(raw)


def build_config_from_dict(raw: Dict[str, Any]) -> Config:
    zhihu_raw = raw.get("zhihu", {})
    cookies_raw = zhihu_raw.get("cookies", {})
    zhihu = ZhihuConfig(
        cookies_file=cookies_raw.get("file", str(DEFAULT_COOKIE_FILE)),
        cookies_pool_dir=cookies_raw.get("pool_dir", str(DEFAULT_COOKIE_POOL_DIR)),
        cookies_required=cookies_raw.get("required", True),
        browser=BrowserConfig(**zhihu_raw.get("browser", {})),
        anti_detection=AntiDetectionConfig(**zhihu_raw.get("anti_detection", {})),
        signature=SignatureConfig(**zhihu_raw.get("signature", {})),
    )

    crawler_raw = raw.get("crawler", {})
    crawler = CrawlerConfig(
        retry=RetryConfig(**crawler_raw.get("retry", {})),
        scroll=ScrollConfig(**crawler_raw.get("scroll", {})),
        humanize=HumanizeConfig.from_dict(crawler_raw.get("humanize", {})),
        images=ImagesConfig(**crawler_raw.get("images", {})),
    )

    output = OutputConfig(**raw.get("output", {}))
    logging_cfg = LoggingConfig(**raw.get("logging", {}))

    return Config(
        zhihu=zhihu,
        crawler=crawler,
        output=output,
        logging=logging_cfg,
    )


def build_default_config() -> Config:
    return Config(
        zhihu=ZhihuConfig(),
        crawler=CrawlerConfig(),
        output=OutputConfig(),
        logging=LoggingConfig(),
    )
