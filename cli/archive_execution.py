"""
archive_execution.py - Shared execution bridge for archive entrypoints.

Provides a small shared layer for CLI, TUI, and compatibility entrypoints so
they can reuse the same workflow service without importing private helpers from
`cli.app`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from rich import print as rprint

from cli.save_pipeline import SavePipelineSettings
from cli.workflow_service import ArchiveWorkflowService, WorkflowServiceConfig
from core.config import get_config, get_logger
from core.structlog_compat import BoundLoggerBase


def build_save_pipeline_settings() -> SavePipelineSettings:
    """Resolve save-pipeline settings from runtime config."""
    cfg = get_config()
    return SavePipelineSettings(
        folder_template=cfg.output.folder_format or "[{date}] {title}",
        images_subdir=cfg.output.images_subdir or "images",
        image_concurrency=cfg.crawler.images.concurrency,
        image_timeout=cfg.crawler.images.timeout,
    )


def get_workflow_service(
    *,
    printer=rprint,
    logger: Optional[BoundLoggerBase] = None,
) -> ArchiveWorkflowService:
    """Construct the shared workflow service for one entrypoint run."""
    return ArchiveWorkflowService(
        WorkflowServiceConfig(
            save_settings=build_save_pipeline_settings(),
            printer=printer,
            logger=get_logger() if logger is None else logger,
        )
    )


async def fetch_and_save(
    url: str,
    output_dir: Path,
    scrape_config: dict,
    download_images: bool = True,
    headless: bool = True,
    collection_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Execute one fetch and return the legacy save-record list.
    执行单条抓取，并返回兼容旧调用方的保存记录列表。
    """
    result = await fetch_and_save_result(
        url=url,
        output_dir=output_dir,
        scrape_config=scrape_config,
        download_images=download_images,
        headless=headless,
        collection_id=collection_id,
    )
    return result.to_legacy_records()


async def fetch_and_save_result(
    url: str,
    output_dir: Path,
    scrape_config: dict,
    download_images: bool = True,
    headless: bool = True,
    collection_id: Optional[str] = None,
):
    """
    Execute one fetch and return the typed save result contract.
    执行单条抓取，并返回类型化保存结果契约。
    """
    result = await get_workflow_service().run_single_fetch(
        url=url,
        output_dir=output_dir,
        scrape_config=scrape_config,
        download_images=download_images,
        headless=headless,
        collection_id=collection_id,
    )
    if not result.success or result.save_result is None:
        raise RuntimeError(result.error or f"Fetch failed for {url}")
    return result.save_result


async def fetch_creator_and_save(
    creator: str,
    output_dir: Path,
    answer_limit: int,
    article_limit: int,
    download_images: bool = True,
) -> None:
    """
    Execute one creator workflow and persist it via the shared save pipeline.
    执行作者抓取工作流，并通过共享保存链路落盘。
    """
    result = await get_workflow_service().run_creator(
        creator=creator,
        output_dir=output_dir,
        answer_limit=answer_limit,
        article_limit=article_limit,
        download_images=download_images,
    )
    if not result.success:
        raise RuntimeError(f"Creator fetch failed for {creator}")
