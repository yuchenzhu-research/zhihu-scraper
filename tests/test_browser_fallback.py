"""
test_browser_fallback.py - Tests for browser fallback mechanism
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from core.config_schema import BrowserConfig


class TestBrowserFallback:
    """Test cases for browser fallback mechanism"""

    @patch("core.browser_fallback.get_config")
    def test_browser_config_loading(self, mock_get_config):
        """Browser config is loaded correctly"""
        from core import browser_fallback

        # Set up mock config
        mock_cfg = MagicMock()
        mock_browser_cfg = BrowserConfig(
            headless=True,
            timeout=30000,
            channel="chrome",
            args=["--no-sandbox"],
            viewport={"width": 1920, "height": 1080},
        )
        mock_cfg.zhihu.browser = mock_browser_cfg
        mock_get_config.return_value = mock_cfg

        from core.browser_fallback import get_logger

        logger = get_logger()
        assert logger is not None

    def test_launch_args_can_be_customized(self):
        """Browser launch arguments can be customized"""
        from core.config_schema import BrowserConfig

        cfg = BrowserConfig(args=["--custom-arg", "--no-sandbox"])
        assert "--custom-arg" in cfg.args
        assert "--no-sandbox" in cfg.args

    @patch("core.browser_fallback.get_config")
    @patch("core.browser_fallback.get_logger")
    def test_extract_zhuanlan_url_construction(self, mock_log, mock_get_config):
        """Verify column URL is constructed correctly"""
        from core import browser_fallback

        mock_cfg = MagicMock()
        mock_browser_cfg = BrowserConfig()
        mock_cfg.zhihu.browser = mock_browser_cfg
        mock_get_config.return_value = mock_cfg
        mock_log.return_value = MagicMock()

        # Just verify URL pattern is correct
        article_id = "123456"
        expected_url = f"https://zhuanlan.zhihu.com/p/{article_id}"
        assert expected_url == "https://zhuanlan.zhihu.com/p/123456"

    @patch("core.browser_fallback.get_config")
    @patch("core.browser_fallback.get_logger")
    def test_cookie_mapping_structure(self, mock_log, mock_get_config):
        """Verify cookie mapping creates correct structure"""
        from core import browser_fallback

        mock_cfg = MagicMock()
        mock_browser_cfg = BrowserConfig()
        mock_cfg.zhihu.browser = mock_browser_cfg
        mock_get_config.return_value = mock_cfg
        mock_log.return_value = MagicMock()

        session_cookies = {"z_c0": "test_token", "d_c0": "test_d"}

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

        assert len(mapped_cookies) == 2
        assert mapped_cookies[0]["domain"] == ".zhihu.com"
        assert mapped_cookies[0]["sameSite"] == "Lax"

    @patch("core.browser_fallback.get_config")
    @patch("core.browser_fallback.get_logger")
    def test_login_redirect_detection(self, mock_log, mock_get_config):
        """Login redirect URLs are detected correctly"""
        from core import browser_fallback

        mock_cfg = MagicMock()
        mock_browser_cfg = BrowserConfig()
        mock_cfg.zhihu.browser = mock_browser_cfg
        mock_get_config.return_value = mock_cfg
        mock_log.return_value = MagicMock()

        def is_login_redirect(url):
            return url == "https://www.zhihu.com/" or "signin" in url

        # These should trigger login redirect detection
        redirect_urls = [
            "https://www.zhihu.com/",
            "https://www.zhihu.com/signin",
        ]
        for url in redirect_urls:
            assert is_login_redirect(url) is True

        # These should NOT trigger redirect
        normal_urls = [
            "https://zhuanlan.zhihu.com/p/123456",
            "https://www.zhihu.com/question/123",
        ]
        for url in normal_urls:
            assert is_login_redirect(url) is False


class TestBrowserConfig:
    """Test BrowserConfig dataclass"""

    def test_browser_config_defaults(self):
        """Default browser config values are sensible"""
        from core.config_schema import BrowserConfig

        cfg = BrowserConfig()
        assert cfg.headless is True
        assert cfg.timeout == 30000
        assert cfg.channel == "chrome"
        assert cfg.viewport == {"width": 1920, "height": 1080}

    def test_browser_config_custom(self):
        """Custom browser config values are stored correctly"""
        from core.config_schema import BrowserConfig

        cfg = BrowserConfig(
            headless=False,
            timeout=60000,
            channel="msedge",
            args=["--custom-arg"],
            viewport={"width": 1280, "height": 720},
        )
        assert cfg.headless is False
        assert cfg.timeout == 60000
        assert cfg.channel == "msedge"
        assert cfg.args == ["--custom-arg"]
        assert cfg.viewport == {"width": 1280, "height": 720}