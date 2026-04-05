"""
translator.py - LLM-powered content translation engine.

This module provides a unified interface for translating Markdown content
scraped from Zhihu using OpenAI-compatible APIs.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, List

if TYPE_CHECKING:
    from core.config_schema import TranslationConfig

# Optional import for openai
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore


PROMPT_DIR = Path(__file__).parent / "prompts"
DEFAULT_SYSTEM_PROMPT_PATH = PROMPT_DIR / "translate.txt"


class ContentTranslator:
    """
    Translates Markdown content using LLM.
    Supports OpenAI-compatible endpoints (ChatGPT, DeepSeek, etc.).
    """

    def __init__(self, config: TranslationConfig):
        self.config = config
        self._client = None
        self._system_prompt = ""

        if not self.config.enabled:
            return

        if OpenAI is None:
            raise ImportError(
                "The 'openai' package is required for translation. "
                "Install it with: pip install openai>=1.0"
            )

        # Initialize OpenAI-compatible client
        api_key = self.config.api_key or os.environ.get("ZHIHU_TRANSLATE_API_KEY", "")
        if not api_key:
             # We rely on the caller to handle this or 
             # the constructor might fail if enabled but no key
             pass

        self._client = OpenAI(
            api_key=api_key,
            base_url=self.config.base_url,
        )

        # Load system prompt
        if DEFAULT_SYSTEM_PROMPT_PATH.exists():
            self._system_prompt = DEFAULT_SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
        else:
            self._system_prompt = (
                "You are a professional translator. "
                "Translate the following content into {target_language} while preserving Markdown formatting."
            )

    def translate_markdown(self, content: str) -> str:
        """
        Translate a Markdown document.
        For very long content, it splits by sections to avoid token limits.
        """
        if not self.config.enabled or not self._client:
            return content

        # Simple section splitting (Level 2 headers are usually good boundaries)
        sections = self._split_content(content)
        translated_sections = []

        for section in sections:
            if not section.strip():
                continue
            
            response = self._client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._system_prompt.format(target_language=self.config.target_language),
                    },
                    {"role": "user", "content": section},
                ],
            )
            translated = response.choices[0].message.content
            if translated:
                translated_sections.append(translated)

        return "\n\n".join(translated_sections)

    def _split_content(self, content: str, max_chunk_size: int = 4000) -> List[str]:
        """
        Split a Markdown document into chunks that fit within model context windows.
        Tries to split at header boundaries.
        """
        if len(content) <= max_chunk_size:
            return [content]

        lines = content.splitlines()
        chunks = []
        current_chunk: List[str] = []
        current_size = 0

        for line in lines:
            line_size = len(line) + 1
            # If current line is a header and we are approaching the limit, start a new chunk
            if (line.startswith("## ") or line.startswith("# ")) and current_size > max_chunk_size * 0.7:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_size = 0
            
            if current_size + line_size > max_chunk_size:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_size = 0
            
            current_chunk.append(line)
            current_size += line_size

        if current_chunk:
            chunks.append("\n".join(current_chunk))
        
        return chunks
