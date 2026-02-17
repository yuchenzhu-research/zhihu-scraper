"""
core/config.py — 配置管理模块

提供统一的配置加载、验证和环境变量覆盖功能。
使用 YAML 格式的配置文件，支持默认值和类型安全。
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union
from dataclasses import dataclass, field

import yaml
import structlog

# ============================================================
# 配置数据类
# ============================================================

@dataclass
class BrowserConfig:
    """浏览器配置"""
    headless: bool = True
    timeout: int = 30000
    viewport: Dict[str, int] = field(default_factory=lambda: {"width": 1920, "height": 1080})
    channel: str = "chrome"
    args: list = field(default_factory=list)

@dataclass
class AntiDetectionConfig:
    """反爬配置"""
    stealth: bool = True
    webgl: bool = True
    navigator: bool = True

@dataclass
class SignatureConfig:
    """签名算法配置"""
    enabled: bool = False

@dataclass
class ZhihuConfig:
    """知乎相关配置"""
    cookies_file: str = "cookies.json"
    cookies_required: bool = True
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    anti_detection: AntiDetectionConfig = field(default_factory=AntiDetectionConfig)
    signature: SignatureConfig = field(default_factory=SignatureConfig)

@dataclass
class RetryConfig:
    """重试配置"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True

@dataclass
class ScrollConfig:
    """滚动配置"""
    timeout: int = 60000
    pause: int = 1000
    viewport_height: int = 800

@dataclass
class HumanizeConfig:
    """人类行为模拟配置"""
    enabled: bool = True
    min_delay: float = 0.5
    max_delay: float = 2.0

@dataclass
class ImagesConfig:
    """图片下载配置"""
    concurrency: int = 4
    timeout: float = 30.0
    referer: str = "https://www.zhihu.com/"

@dataclass
class CrawlerConfig:
    """爬虫通用配置"""
    retry: RetryConfig = field(default_factory=RetryConfig)
    scroll: ScrollConfig = field(default_factory=ScrollConfig)
    humanize: HumanizeConfig = field(default_factory=HumanizeConfig)
    images: ImagesConfig = field(default_factory=ImagesConfig)

@dataclass
class OutputConfig:
    """导出配置"""
    directory: str = "data"
    format: str = "markdown"
    images_subdir: str = "images"
    folder_format: str = "[{date}] {title}"

@dataclass
class LoggingConfig:
    """日志配置"""
    level: str = "INFO"
    format: str = "console"
    file: Optional[str] = None
    log_exceptions: bool = True

@dataclass
class Config:
    """主配置类"""
    zhihu: ZhihuConfig
    crawler: CrawlerConfig
    output: OutputConfig
    logging: LoggingConfig

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Config":
        """从字典构建配置"""
        # 解析知乎配置
        zhihu_raw = raw.get("zhihu", {})
        zhihu = ZhihuConfig(
            cookies_file=zhihu_raw.get("cookies", {}).get("file", "cookies.json"),
            cookies_required=zhihu_raw.get("cookies", {}).get("required", True),
            browser=BrowserConfig(**zhihu_raw.get("browser", {})),
            anti_detection=AntiDetectionConfig(**zhihu_raw.get("anti_detection", {})),
            signature=SignatureConfig(**zhihu_raw.get("signature", {})),
        )

        # 解析爬虫配置
        crawler_raw = raw.get("crawler", {})
        crawler = CrawlerConfig(
            retry=RetryConfig(**crawler_raw.get("retry", {})),
            scroll=ScrollConfig(**crawler_raw.get("scroll", {})),
            humanize=HumanizeConfig(**crawler_raw.get("humanize", {})),
            images=ImagesConfig(**crawler_raw.get("images", {})),
        )

        # 解析导出配置
        output = OutputConfig(**raw.get("output", {}))

        # 解析日志配置
        logging_cfg = LoggingConfig(**raw.get("logging", {}))

        return cls(
            zhihu=zhihu,
            crawler=crawler,
            output=output,
            logging=logging_cfg,
        )

# ============================================================
# 配置加载器
# ============================================================

class ConfigLoader:
    """配置加载器，支持多路径和默认值"""

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
        加载配置文件

        Args:
            config_path: 配置文件路径，默认为项目根目录的 config.yaml
            override_level: 可选的环境变量覆盖级别 (DEBUG/INFO/WARNING/ERROR)
        """
        if self._config is not None:
            return self._config

        if config_path is None:
            # 默认查找项目根目录
            root = Path(__file__).parent.parent
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

            # 环境变量覆盖
            if override_level:
                self._config.logging.level = override_level

            # 设置日志级别（必须在返回前）
            setup_logging(self._config)

            return self._config

        except Exception as e:
            print(f"⚠️ 配置文件加载失败: {e}")
            print("  使用默认配置")
            self._config = self._get_default_config()
            setup_logging(self._config)
            return self._config

    def _get_default_config(self) -> Config:
        """获取默认配置（当配置文件不存在或解析失败时）"""
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
        """获取已加载的配置"""
        if self._config is None:
            return self.load()
        return self._config

    def reload(self, config_path: Optional[Union[str, Path]] = None) -> Config:
        """重新加载配置"""
        self._config = None
        return self.load(config_path)


def get_config(config_path: Optional[Union[str, Path]] = None) -> Config:
    """便捷函数：获取配置"""
    loader = ConfigLoader()
    return loader.load(config_path)


# ============================================================
# 日志系统
# ============================================================

def setup_logging(config: Union[Config, LoggingConfig]) -> None:
    """
    初始化结构化日志系统

    Args:
        config: 配置对象或日志配置
    """
    if isinstance(config, Config):
        log_config = config.logging
    else:
        log_config = config

    # 解析日志级别
    import logging as stdlib_logging
    log_level = getattr(stdlib_logging, log_config.level.upper(), stdlib_logging.INFO)

    # 处理器列表
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    # 输出格式
    if log_config.format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        # 美观的控制台输出
        processors.append(structlog.dev.ConsoleRenderer())

    # 配置 structlog
    structlog.configure(
        processors=processors,
        wrapper_class=stdlib_logging.Logger,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )

    # 配置标准日志（防止第三方库日志混乱）
    stdlib_logging.basicConfig(
        level=log_level,
        format="%(message)s" if log_config.format != "json" else "%(message)s",
    )

    log = structlog.get_logger()
    log.info(
        "logging_configured",
        level=log_config.level,
        format=log_config.format,
        file=log_config.file,
    )


def get_logger(name: str = "zhihu-scraper") -> structlog.BoundLoggerBase:
    """获取结构化日志记录器"""
    return structlog.get_logger(name)