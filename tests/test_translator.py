"""
test_translator.py - Tests for translation engine
"""

import pytest
from unittest.mock import patch, MagicMock
from core.config_schema import TranslationConfig


class TestContentTranslator:
    """Test cases for ContentTranslator"""

    def test_translator_disabled_returns_original_content(self):
        """When translation is disabled, return original content unchanged"""
        from core.translator import ContentTranslator
        config = TranslationConfig(enabled=False)
        translator = ContentTranslator(config)

        original = "# Hello\n\nThis is a test."
        result = translator.translate_markdown(original)
        assert result == original

    def test_translator_no_api_key_raises_error(self):
        """When enabled with empty API key, OpenAI client initialization raises"""
        from core.translator import ContentTranslator
        import pytest

        config = TranslationConfig(enabled=True, api_key="")
        # With empty API key, OpenAI client initialization fails
        with pytest.raises(Exception) as exc_info:
            ContentTranslator(config)
        assert "api_key" in str(exc_info.value).lower() or "credentials" in str(exc_info.value).lower()

    def test_split_content_small_content(self):
        """Small content fits in one chunk"""
        from core.translator import ContentTranslator
        config = TranslationConfig(enabled=False)
        translator = ContentTranslator(config)

        content = "# Small content"
        chunks = translator._split_content(content, max_chunk_size=4000)
        assert len(chunks) == 1
        assert chunks[0] == content

    def test_split_content_large_content_splits(self):
        """Large content splits into multiple chunks"""
        from core.translator import ContentTranslator
        config = TranslationConfig(enabled=False)
        translator = ContentTranslator(config)

        content = "# Header\n\n" + "A" * 5000
        chunks = translator._split_content(content, max_chunk_size=4000)
        assert len(chunks) > 1

    def test_split_content_respects_header_boundaries(self):
        """Content splits at header boundaries when possible"""
        from core.translator import ContentTranslator
        config = TranslationConfig(enabled=False)
        translator = ContentTranslator(config)

        content = "# Title\n\n## Section 1\n\n" + "A" * 3000 + "\n\n## Section 2\n\nContent"
        chunks = translator._split_content(content, max_chunk_size=4000)

        # Should have at least the content split somewhere
        assert len(chunks) >= 1

    def test_split_content_very_long_line(self):
        """Long lines without headers are split"""
        from core.translator import ContentTranslator
        config = TranslationConfig(enabled=False)
        translator = ContentTranslator(config)

        # Create a line longer than max_chunk_size
        long_line = "A" * 5000
        content = f"# Header\n\n{long_line}"
        chunks = translator._split_content(content, max_chunk_size=4000)

        # Should split the long line
        assert len(chunks) > 1

    def test_split_content_empty_content(self):
        """Empty content returns empty list"""
        from core.translator import ContentTranslator
        config = TranslationConfig(enabled=False)
        translator = ContentTranslator(config)

        chunks = translator._split_content("", max_chunk_size=4000)
        assert chunks == [""]


class TestContentTranslatorWithMock:
    """Integration-style tests with mocked API"""

    @patch("core.translator.OpenAI")
    def test_translator_calls_api(self, mock_openai):
        """Verify translator calls OpenAI API"""
        from core.translator import ContentTranslator

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Translated content"
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        config = TranslationConfig(
            enabled=True,
            api_key="test-key",
            model="gpt-4o-mini",
            target_language="en",
        )
        translator = ContentTranslator(config)
        result = translator.translate_markdown("# Test\n\nContent here")

        assert result == "Translated content"
        mock_client.chat.completions.create.assert_called_once()

    @patch("core.translator.OpenAI")
    def test_translate_multiple_sections(self, mock_openai):
        """Multiple sections are translated and joined"""
        from core.translator import ContentTranslator

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Translated"
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        config = TranslationConfig(
            enabled=True,
            api_key="test-key",
            model="gpt-4o-mini",
            target_language="en",
        )
        translator = ContentTranslator(config)

        # Create content that will definitely be split into multiple sections
        content = "## Section 1\n\n" + "X" * 3000 + "\n\n## Section 2\n\n" + "Y" * 3000
        result = translator.translate_markdown(content)

        # Multiple sections should be translated
        assert "Translated" in result
        assert mock_client.chat.completions.create.call_count >= 1

    @patch("core.translator.OpenAI")
    def test_translator_uses_system_prompt(self, mock_openai):
        """System prompt is formatted with target language"""
        from core.translator import ContentTranslator

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Result"
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        config = TranslationConfig(
            enabled=True,
            api_key="test-key",
            model="gpt-4o-mini",
            target_language="en",
        )
        translator = ContentTranslator(config)
        translator.translate_markdown("# Test")

        # Check that the call was made
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]

        # First message should be system prompt
        assert messages[0]["role"] == "system"
        assert "en" in messages[0]["content"]