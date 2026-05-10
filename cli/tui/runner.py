"""
runner.py - Execution bridge for the interactive TUI.
"""

from __future__ import annotations

import asyncio
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Callable

from cli.archive_execution import fetch_and_save_result
from cli.tui.state import (
    DraftSummary,
    DraftTarget,
    ExecutionRecord,
    ExecutionReport,
    build_running_summary,
)
from cli.workflow_service import DEFAULT_QUESTION_LIMIT, build_scrape_config_for_url
from core.config import get_config, resolve_project_path
from core.i18n import t


ProgressCallback = Callable[[DraftSummary], None]


def execute_draft_run(
    draft: DraftSummary,
    progress_callback: ProgressCallback | None = None,
) -> ExecutionReport:
    """Execute one draft as a single run and return a compact report."""
    cfg = get_config()
    output_dir = resolve_project_path(cfg.output.directory)
    records: list[ExecutionRecord] = []
    total = max(1, len(draft.targets))

    # Lazily initialize translator only when translation is enabled
    translator = None
    translation_start_note: str | None = None
    if cfg.translation.enabled:
        try:
            from core.translator import ContentTranslator
            translator = ContentTranslator(cfg.translation)
        except ImportError:
            translation_start_note = t("runner.translation.unavailable")
        except Exception as exc:
            translation_start_note = t("runner.translation.config_failed", error=str(exc))

    for index, target in enumerate(draft.targets, start=1):
        if progress_callback is not None:
            progress_callback(
                build_running_summary(
                    draft,
                    current_index=index,
                    total=total,
                    output_dir=str(output_dir),
                    phase=t("runner.phase.scraping"),
                )
            )

        buffer = StringIO()
        try:
            with redirect_stdout(buffer), redirect_stderr(buffer):
                save_result = asyncio.run(
                    fetch_and_save_result(
                        url=target.url,
                        output_dir=output_dir,
                        scrape_config=build_scrape_config_for_url(
                            target.url,
                            question_limit=target.limit,
                            default_question_limit=DEFAULT_QUESTION_LIMIT,
                        ),
                        download_images=True,
                        headless=cfg.zhihu.browser.headless,
                    )
                )

            if not save_result.is_empty:
                # --- Translation post-processing ---
                translated_paths: list[str] = []
                notes: list[str] = []
                if translation_start_note:
                    notes.append(translation_start_note)
                if translator and save_result.markdown_paths:
                    if progress_callback is not None:
                        progress_callback(
                            build_running_summary(
                                draft,
                                current_index=index,
                                total=total,
                                output_dir=str(output_dir),
                                phase=t("runner.phase.translating", lang=cfg.translation.target_language),
                            )
                        )
                    for md_path in save_result.markdown_paths:
                        try:
                            translated_path = _translate_file(translator, md_path, cfg.translation.target_language)
                            if translated_path:
                                translated_paths.append(translated_path)
                        except Exception as exc:
                            notes.append(t("runner.translation.failed", error=str(exc)))

                records.append(
                    ExecutionRecord(
                        target=target,
                        saved_count=save_result.saved_count,
                        markdown_paths=save_result.markdown_paths,
                        translated_paths=tuple(translated_paths),
                        notes=tuple(notes),
                    )
                )
            else:
                records.append(
                    ExecutionRecord(
                        target=target,
                        saved_count=0,
                        markdown_paths=(),
                        error=t("runner.error.empty"),
                        log_tail=_tail_lines(buffer),
                    )
                )
        except Exception as exc:
            records.append(
                ExecutionRecord(
                    target=target,
                    saved_count=0,
                    markdown_paths=(),
                    error=str(exc),
                    log_tail=_tail_lines(buffer),
                )
            )

    return ExecutionReport(output_dir=str(output_dir), records=tuple(records))


def _translate_file(translator, md_path: str, target_lang: str) -> str | None:
    """Read a Markdown file, translate it, and write to ``[LANG] original_name.md``."""
    src = Path(md_path)
    if not src.exists():
        return None

    content = src.read_text(encoding="utf-8")
    translated = translator.translate_markdown(content)
    if not translated or translated == content:
        return None

    lang_tag = target_lang.upper()
    dest = src.parent / f"[{lang_tag}] {src.name}"
    dest.write_text(translated, encoding="utf-8")
    return str(dest)


def _tail_lines(buffer: StringIO, limit: int = 3) -> tuple[str, ...]:
    """Return the last few non-empty log lines captured from stdout/stderr."""
    lines = [line.strip() for line in buffer.getvalue().splitlines() if line.strip()]
    return tuple(lines[-limit:])
