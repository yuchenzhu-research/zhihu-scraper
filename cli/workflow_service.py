"""
workflow_service.py - Application-service layer for archive workflows.

This module keeps CLI command handlers thin and provides reusable orchestration
for future entrypoints such as TUI, automation, or API wrappers.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from random import uniform
from typing import Awaitable, Callable, Optional, Sequence

from rich import print as rprint

from cli.save_contracts import CreatorSaveResult, SaveRunResult
from cli.save_pipeline import SavePipelineSettings, fetch_and_save_result, fetch_creator_and_save_result
from cli.workflow_contracts import BatchWorkflowResult, CreatorWorkflowResult, MonitorWorkflowResult, UrlTaskResult
from core.errors import handle_error
from core.monitor import CollectionMonitor
from core.structlog_compat import BoundLoggerBase


FetchRunner = Callable[..., Awaitable[SaveRunResult]]
CreatorRunner = Callable[..., Awaitable[Optional[CreatorSaveResult]]]
MonitorFactory = Callable[..., CollectionMonitor]
Printer = Callable[[str], None]
ErrorHandler = Callable[[Exception, Optional[BoundLoggerBase]], object]
SleepFn = Callable[[float], Awaitable[None]]
DEFAULT_QUESTION_LIMIT = 3


def is_question_listing_url(url: str) -> bool:
    """Return whether the URL points to a question page instead of a single answer."""
    return "/question/" in url and "/answer/" not in url


def build_scrape_config_for_url(
    url: str,
    *,
    question_limit: Optional[int] = None,
    default_question_limit: Optional[int] = None,
    question_start: int = 0,
) -> dict:
    """
    Normalize URL-specific scrape config in one place.
    在一个地方统一归一化不同 URL 的抓取配置。
    """
    if not is_question_listing_url(url):
        return {}

    resolved_limit = question_limit if question_limit is not None else default_question_limit
    if resolved_limit is None:
        return {}

    return {"start": question_start, "limit": resolved_limit}


@dataclass(frozen=True)
class WorkflowServiceConfig:
    save_settings: SavePipelineSettings
    printer: Printer = rprint
    logger: Optional[BoundLoggerBase] = None


class ArchiveWorkflowService:
    """
    Reusable application service for command/TUI archive workflows.
    可复用的应用服务层，统一命令行与交互式入口的任务编排。
    """

    def __init__(
        self,
        config: WorkflowServiceConfig,
        *,
        fetch_runner: FetchRunner = fetch_and_save_result,
        creator_runner: CreatorRunner = fetch_creator_and_save_result,
        monitor_factory: MonitorFactory = CollectionMonitor,
        error_handler: ErrorHandler = handle_error,
        sleep: SleepFn = asyncio.sleep,
    ) -> None:
        self._config = config
        self._fetch_runner = fetch_runner
        self._creator_runner = creator_runner
        self._monitor_factory = monitor_factory
        self._error_handler = error_handler
        self._sleep = sleep

    async def run_fetch_urls(
        self,
        *,
        urls: Sequence[str],
        output_dir: Path,
        limit: Optional[int],
        download_images: bool,
        headless: bool,
        stop_on_error: bool = True,
        collection_id: Optional[str] = None,
    ) -> BatchWorkflowResult:
        items: list[UrlTaskResult] = []
        for url in urls:
            scrape_config = build_scrape_config_for_url(url, question_limit=limit)
            result = await self.run_single_fetch(
                url=url,
                output_dir=output_dir,
                scrape_config=scrape_config,
                download_images=download_images,
                headless=headless,
                collection_id=collection_id,
            )
            items.append(result)
            if stop_on_error and not result.success:
                break

        return BatchWorkflowResult(items=tuple(items))

    async def run_batch(
        self,
        *,
        urls: Sequence[str],
        output_dir: Path,
        concurrency: int,
        download_images: bool,
        headless: bool,
        collection_id: Optional[str] = None,
    ) -> BatchWorkflowResult:
        semaphore = asyncio.Semaphore(concurrency)

        async def fetch_one(url: str, index: int) -> UrlTaskResult:
            async with semaphore:
                if index > 0:
                    delay = uniform(0.5, 2.0) * (index % 3 + 1)
                    await self._sleep(delay)
                return await self.run_single_fetch(
                    url=url,
                    output_dir=output_dir,
                    scrape_config=build_scrape_config_for_url(url),
                    download_images=download_images,
                    headless=headless,
                    collection_id=collection_id,
                )

        return BatchWorkflowResult(items=tuple(await asyncio.gather(*(fetch_one(url, idx) for idx, url in enumerate(urls)))))

    async def run_single_fetch(
        self,
        *,
        url: str,
        output_dir: Path,
        scrape_config: dict,
        download_images: bool,
        headless: bool,
        collection_id: Optional[str] = None,
    ) -> UrlTaskResult:
        try:
            save_result = await self._fetch_runner(
                url=url,
                output_dir=output_dir,
                scrape_config=scrape_config,
                settings=self._config.save_settings,
                download_images=download_images,
                headless=headless,
                collection_id=collection_id,
                printer=self._config.printer,
            )
            return UrlTaskResult(url=url, success=True, save_result=save_result)
        except Exception as error:
            self._error_handler(error, self._config.logger)
            return UrlTaskResult(url=url, success=False, error=str(error))

    async def run_creator(
        self,
        *,
        creator: str,
        output_dir: Path,
        answer_limit: int,
        article_limit: int,
        download_images: bool,
    ) -> CreatorWorkflowResult:
        try:
            result = await self._creator_runner(
                creator=creator,
                output_dir=output_dir,
                answer_limit=answer_limit,
                article_limit=article_limit,
                settings=self._config.save_settings,
                download_images=download_images,
                printer=self._config.printer,
            )
            return CreatorWorkflowResult(creator=creator, result=result)
        except Exception as error:
            self._error_handler(error, self._config.logger)
            return CreatorWorkflowResult(creator=creator, result=None)

    async def run_monitor(
        self,
        *,
        collection_id: str,
        output_dir: Path,
        concurrency: int,
        download_images: bool,
        headless: bool,
    ) -> MonitorWorkflowResult:
        monitor = self._monitor_factory(data_dir=str(output_dir))
        delta = monitor.get_new_items(collection_id)
        if not delta.has_unseen_items:
            return MonitorWorkflowResult(
                collection_id=collection_id,
                discovered_count=0,
                batch=BatchWorkflowResult(items=()),
                pointer_advanced=False,
                unsupported_count=0,
                next_pointer=None,
            )

        if not delta.has_supported_items:
            pointer_advanced = False
            if delta.next_pointer:
                monitor.mark_updated(collection_id, delta.next_pointer)
                pointer_advanced = True

            return MonitorWorkflowResult(
                collection_id=collection_id,
                discovered_count=0,
                batch=BatchWorkflowResult(items=()),
                pointer_advanced=pointer_advanced,
                unsupported_count=delta.unsupported_count,
                next_pointer=delta.next_pointer,
            )

        batch = await self.run_batch(
            urls=[item["url"] for item in delta.items],
            output_dir=output_dir,
            concurrency=min(concurrency, len(delta.items), 8),
            download_images=download_images,
            headless=headless,
            collection_id=collection_id,
        )

        pointer_advanced = False
        if delta.next_pointer and batch.failed_count == 0 and batch.success_count > 0:
            monitor.mark_updated(collection_id, delta.next_pointer)
            pointer_advanced = True

        return MonitorWorkflowResult(
            collection_id=collection_id,
            discovered_count=len(delta.items),
            batch=batch,
            pointer_advanced=pointer_advanced,
            unsupported_count=delta.unsupported_count,
            next_pointer=delta.next_pointer,
        )
