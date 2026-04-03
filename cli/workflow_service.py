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
            scrape_config = self._build_scrape_config(url, limit)
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
                    scrape_config={},
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
        new_items, new_last_id = monitor.get_new_items(collection_id)
        if not new_items:
            return MonitorWorkflowResult(
                collection_id=collection_id,
                discovered_count=0,
                batch=BatchWorkflowResult(items=()),
                pointer_advanced=False,
                next_pointer=None,
            )

        batch = await self.run_batch(
            urls=[item["url"] for item in new_items],
            output_dir=output_dir,
            concurrency=min(concurrency, len(new_items), 8),
            download_images=download_images,
            headless=headless,
            collection_id=collection_id,
        )

        pointer_advanced = False
        if batch.failed_count == 0 and batch.success_count > 0:
            monitor.mark_updated(collection_id, new_last_id)
            pointer_advanced = True

        return MonitorWorkflowResult(
            collection_id=collection_id,
            discovered_count=len(new_items),
            batch=batch,
            pointer_advanced=pointer_advanced,
            next_pointer=new_last_id,
        )

    @staticmethod
    def _build_scrape_config(url: str, limit: Optional[int]) -> dict:
        if limit and "/question/" in url and "/answer/" not in url:
            return {"start": 0, "limit": limit}
        return {}
