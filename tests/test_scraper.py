"""
test_scraper.py - Tests for scraper module
"""

import pytest
from unittest.mock import patch, MagicMock


class TestZhihuDownloader:
    """Test cases for ZhihuDownloader"""

    @patch("core.scraper.ZhihuAPIClient")
    @patch("core.scraper.get_logger")
    def test_detect_type_article(self, mock_log, mock_api_client):
        """Column (zhuanlan) URLs are detected as article type"""
        from core.scraper import ZhihuDownloader

        downloader = ZhihuDownloader("https://zhuanlan.zhihu.com/p/123456")
        assert downloader.page_type == "article"

    @patch("core.scraper.ZhihuAPIClient")
    @patch("core.scraper.get_logger")
    def test_detect_type_answer(self, mock_log, mock_api_client):
        """Answer URLs are detected correctly"""
        from core.scraper import ZhihuDownloader

        downloader = ZhihuDownloader("https://www.zhihu.com/question/28696373/answer/2835848212")
        assert downloader.page_type == "answer"

    @patch("core.scraper.ZhihuAPIClient")
    @patch("core.scraper.get_logger")
    def test_detect_type_question(self, mock_log, mock_api_client):
        """Question URLs are detected correctly"""
        from core.scraper import ZhihuDownloader

        downloader = ZhihuDownloader("https://www.zhihu.com/question/28696373")
        assert downloader.page_type == "question"

    @patch("core.scraper.ZhihuAPIClient")
    @patch("core.scraper.get_logger")
    def test_detect_type_defaults_to_article(self, mock_log, mock_api_client):
        """Unknown URLs default to article type"""
        from core.scraper import ZhihuDownloader

        downloader = ZhihuDownloader("https://example.com/some/path")
        assert downloader.page_type == "article"

    @patch("core.scraper.ZhihuAPIClient")
    @patch("core.scraper.get_logger")
    def test_url_query_params_stripped(self, mock_log, mock_api_client):
        """URL query parameters are stripped"""
        from core.scraper import ZhihuDownloader

        downloader = ZhihuDownloader("https://www.zhihu.com/question/123?utm_source=abc")
        assert "?" not in downloader.url

    @patch("core.scraper.ZhihuAPIClient")
    @patch("core.scraper.get_logger")
    def test_url_stored_after_init(self, mock_log, mock_api_client):
        """Original URL is stored"""
        from core.scraper import ZhihuDownloader

        original_url = "https://www.zhihu.com/question/28696373/answer/2835848212"
        downloader = ZhihuDownloader(original_url)
        assert downloader.url == original_url.split("?")[0]

    @patch("core.scraper.ZhihuAPIClient")
    @patch("core.scraper.get_logger")
    def test_has_valid_cookies_true(self, mock_log, mock_api_client):
        """has_valid_cookies returns True when cookies exist"""
        from core.scraper import ZhihuDownloader

        mock_client = MagicMock()
        mock_client._cookies_dict = {"z_c0": "test_token"}
        mock_api_client.return_value = mock_client

        downloader = ZhihuDownloader("https://www.zhihu.com/question/123")
        assert downloader.has_valid_cookies() is True

    @patch("core.scraper.ZhihuAPIClient")
    @patch("core.scraper.get_logger")
    def test_has_valid_cookies_false(self, mock_log, mock_api_client):
        """has_valid_cookies returns False when no cookies"""
        from core.scraper import ZhihuDownloader

        mock_client = MagicMock()
        mock_client._cookies_dict = {}
        mock_api_client.return_value = mock_client

        downloader = ZhihuDownloader("https://www.zhihu.com/question/123")
        assert downloader.has_valid_cookies() is False


class TestScraperUrlPatterns:
    """Test various URL patterns"""

    @patch("core.scraper.ZhihuAPIClient")
    @patch("core.scraper.get_logger")
    def test_column_with_long_id(self, mock_log, mock_api_client):
        """Long column IDs are handled correctly"""
        from core.scraper import ZhihuDownloader

        downloader = ZhihuDownloader("https://zhuanlan.zhihu.com/p/123456789012345")
        assert downloader.page_type == "article"

    @patch("core.scraper.ZhihuAPIClient")
    @patch("core.scraper.get_logger")
    def test_zhuanlan_alias(self, mock_log, mock_api_client):
        """Alternative zhuanlan URLs work"""
        from core.scraper import ZhihuDownloader

        downloader = ZhihuDownloader("https://www.zhuanlan.zhihu.com/p/123456")
        assert downloader.page_type == "article"

    @patch("core.scraper.ZhihuAPIClient")
    @patch("core.scraper.get_logger")
    def test_question_with_segment(self, mock_log, mock_api_client):
        """Question URL segments work"""
        from core.scraper import ZhihuDownloader

        downloader = ZhihuDownloader("https://www.zhihu.com/question/123456#Segment")
        assert downloader.page_type == "question"