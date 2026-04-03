"""
runner.py - Execution bridge for the interactive TUI.
"""

from __future__ import annotations

import asyncio
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from typing import Callable

from cli.app import _fetch_and_save_result
from cli.tui.state import (
    DraftSummary,
    DraftTarget,
    ExecutionRecord,
    ExecutionReport,
    build_running_summary,
)
from core.config import get_config, resolve_project_path


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

    for index, target in enumerate(draft.targets, start=1):
        if progress_callback is not None:
            progress_callback(
                build_running_summary(
                    draft,
                    current_index=index,
                    total=total,
                    output_dir=str(output_dir),
                    phase="抓取与写入本地归档",
                )
            )

        buffer = StringIO()
        try:
            with redirect_stdout(buffer), redirect_stderr(buffer):
                save_result = asyncio.run(
                    _fetch_and_save_result(
                        url=target.url,
                        output_dir=output_dir,
                        scrape_config=_build_scrape_config(target),
                        download_images=True,
                        headless=cfg.zhihu.browser.headless,
                    )
                )

            if not save_result.is_empty:
                records.append(
                    ExecutionRecord(
                        target=target,
                        saved_count=save_result.saved_count,
                        markdown_paths=save_result.markdown_paths,
                    )
                )
            else:
                records.append(
                    ExecutionRecord(
                        target=target,
                        saved_count=0,
                        markdown_paths=(),
                        error="未获取到可保存的内容",
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


def _build_scrape_config(target: DraftTarget) -> dict:
    """Convert one parsed target into the existing fetch configuration shape."""
    if target.url_type == "question":
        return {"start": 0, "limit": target.limit or 3}
    return {}


def _tail_lines(buffer: StringIO, limit: int = 3) -> tuple[str, ...]:
    """Return the last few non-empty log lines captured from stdout/stderr."""
    lines = [line.strip() for line in buffer.getvalue().splitlines() if line.strip()]
    return tuple(lines[-limit:])
