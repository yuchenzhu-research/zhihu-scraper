"""
save_pipeline.py - Local archive save orchestration

Extracts output naming, Markdown persistence, image downloading, and creator
metadata writing from the main CLI module so command entrypoints stay thin.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence, Tuple

from rich import print as rprint

from cli.creator_metadata import write_creator_metadata
from cli.save_contracts import CreatorSaveResult, SavePipelineError, SaveRunResult, SavedContentRecord
from core.converter import ZhihuConverter
from core.db import ZhihuDatabase
from core.media_downloader import MediaDownloader
from core.scraper import ZhihuCreatorDownloader, ZhihuDownloader
from core.scraper_contracts import ScrapedItem, to_scraped_items
from core.utils import sanitize_filename


Printer = Callable[[str], None]


@dataclass(frozen=True)
class SavePipelineSettings:
    """Runtime knobs required by the local archive save pipeline."""

    folder_template: str
    images_subdir: str
    image_concurrency: int
    image_timeout: int


def build_output_folder_name(
    item_date: str,
    title: str,
    author: str,
    item_key: str,
    *,
    folder_template: Optional[str] = None,
) -> str:
    """
    Render output directory name from a configured template and stable suffix.
    根据配置模板生成输出目录名，并附加稳定唯一后缀。
    """
    template = folder_template or "[{date}] {title}"
    try:
        rendered = template.format(date=item_date, title=title, author=author)
    except KeyError:
        rendered = f"[{item_date}] {title}"

    rendered = sanitize_filename(rendered, max_length=100, shell_safe=True)
    safe_item_key = sanitize_filename(item_key, max_length=80, shell_safe=True)
    return f"{rendered}--{safe_item_key}"


def resolve_entries_output_dir(base_dir: Path) -> Path:
    """Resolve the content root for normal fetch/batch/monitor outputs."""
    if base_dir.name == "entries":
        return base_dir
    return base_dir / "entries"


def resolve_creator_output_dir(base_dir: Path, url_token: str) -> Path:
    """Resolve the content root for creator outputs."""
    safe_token = sanitize_filename(url_token, max_length=80)
    return base_dir / "creators" / safe_token


async def fetch_and_save(
    *,
    url: str,
    output_dir: Path,
    scrape_config: Dict[str, Any],
    settings: SavePipelineSettings,
    download_images: bool = True,
    headless: bool = True,
    collection_id: Optional[str] = None,
    printer: Printer = rprint,
) -> list[dict[str, Any]]:
    """
    Execute scraping and save the result to local files and SQLite.
    执行抓取，并保存到本地文件和 SQLite。
    """
    result = await fetch_and_save_result(
        url=url,
        output_dir=output_dir,
        scrape_config=scrape_config,
        settings=settings,
        download_images=download_images,
        headless=headless,
        collection_id=collection_id,
        printer=printer,
    )
    return result.to_legacy_records()


async def fetch_and_save_result(
    *,
    url: str,
    output_dir: Path,
    scrape_config: Dict[str, Any],
    settings: SavePipelineSettings,
    download_images: bool = True,
    headless: bool = True,
    collection_id: Optional[str] = None,
    printer: Printer = rprint,
) -> SaveRunResult:
    """
    Execute scraping and return a typed save result contract.
    执行抓取，并返回类型化保存结果契约。
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    downloader = ZhihuDownloader(url)
    fetch_kwargs = dict(scrape_config)
    fetch_kwargs["headless"] = headless
    fetch_result = await downloader.fetch_result(**fetch_kwargs)

    if fetch_result.is_empty:
        printer("[yellow]⚠️  No content obtained / 未获取到内容[/yellow]")
        return SaveRunResult(
            source_url=url,
            content_root=resolve_entries_output_dir(output_dir),
            records=(),
            collection_id=collection_id,
        )

    return await save_items_result(
        items=fetch_result.items,
        content_root=resolve_entries_output_dir(output_dir),
        db_root=output_dir,
        settings=settings,
        download_images=download_images,
        source_url_fallback=url,
        collection_id=collection_id,
        printer=printer,
    )


async def fetch_creator_and_save(
    *,
    creator: str,
    output_dir: Path,
    answer_limit: int,
    article_limit: int,
    settings: SavePipelineSettings,
    download_images: bool = True,
    printer: Printer = rprint,
) -> Optional[CreatorSaveResult]:
    """
    Fetch creator content and persist it using the standard save pipeline.
    抓取作者内容，并复用标准保存链路落地。
    """
    return await fetch_creator_and_save_result(
        creator=creator,
        output_dir=output_dir,
        answer_limit=answer_limit,
        article_limit=article_limit,
        settings=settings,
        download_images=download_images,
        printer=printer,
    )


async def fetch_creator_and_save_result(
    *,
    creator: str,
    output_dir: Path,
    answer_limit: int,
    article_limit: int,
    settings: SavePipelineSettings,
    download_images: bool = True,
    printer: Printer = rprint,
) -> Optional[CreatorSaveResult]:
    """
    Fetch creator content via pagination flow and return a typed save result contract.
    抓取作者内容，并返回类型化保存结果契约。
    """
    import asyncio
    from random import uniform
    from core.config import get_humanizer

    output_dir.mkdir(parents=True, exist_ok=True)

    downloader = ZhihuCreatorDownloader(creator)
    humanizer = get_humanizer()
    creator_info = None
    all_answers = []
    all_articles = []
    answer_stats = {"saved_count": 0, "pages_fetched": 0, "reached_end": False, "last_offset": 0, "requested_limit": answer_limit, "stopped_early": False}
    article_stats = {"saved_count": 0, "pages_fetched": 0, "reached_end": False, "last_offset": 0, "requested_limit": article_limit, "stopped_early": False}

    page_index = 0
    all_records = []
    creator_root = None

    async for info, typ, page in downloader.fetch_items_pages(answer_limit=answer_limit, article_limit=article_limit):
        if creator_info is None:
            creator_info = info
            printer(f"[cyan]👤 Creator / 作者[/cyan]: {creator_info.name} ({creator_info.url_token or 'unknown'})")
            if creator_info.follower_count or creator_info.following_count:
                printer(
                    f"   👥 Followers / 粉丝: {creator_info.follower_count}"
                    f" | Following / 关注: {creator_info.following_count}"
                )
            creator_root = resolve_creator_output_dir(output_dir, creator_info.url_token or creator)

        page_items = page.get("items", [])
        if typ == "answer":
            all_answers.extend(page_items)
            answer_stats = page.get("stats", answer_stats)
        elif typ == "article":
            all_articles.extend(page_items)
            article_stats = page.get("stats", article_stats)

        if not page_items:
            continue

        run_res = await save_items_result(
            items=tuple(page_items),
            content_root=creator_root,
            db_root=output_dir,
            settings=settings,
            download_images=download_images,
            source_url_fallback=f"https://www.zhihu.com/people/{creator_info.url_token or creator}",
            printer=printer,
        )
        all_records.extend(run_res.records)
        page_index += 1

        # Pagination delay control inverted to this caller
        stats = page.get("stats", {})
        if humanizer.config.enabled and not stats.get("reached_end", True):
            if page_index % 3 == 0:
                delay = uniform(15.0, 30.0)
                printer(f"⏸️ 已连续抓取 {page_index} 页，额外休息 {delay:.1f} 秒后继续...")
            else:
                min_delay = max(3.0, humanizer.config.min_delay)
                max_delay = max(min_delay, humanizer.config.max_delay, 8.0)
                delay = uniform(min_delay, max_delay)
                printer(f"⏳ 等待 {delay:.1f} 秒后抓取下一页...")
            await asyncio.sleep(delay)

    if not all_records:
        printer("[yellow]⚠️  No creator content obtained / 未获取到作者内容[/yellow]")
        return None

    save_result = SaveRunResult(
        source_url=f"https://www.zhihu.com/people/{creator_info.url_token or creator}",
        content_root=creator_root,
        records=tuple(all_records),
        collection_id=None,
    )

    from core.scraper_contracts import PaginationStats
    creator_result = CreatorSaveResult(
        creator=creator_info,
        save_result=save_result,
        answers=PaginationStats.from_dict(answer_stats),
        articles=PaginationStats.from_dict(article_stats),
    )
    write_creator_metadata(creator_root, creator_info, save_result, creator_result)
    return creator_result


async def save_items(
    *,
    items: Sequence[ScrapedItem] | Sequence[dict[str, Any]],
    content_root: Path,
    db_root: Path,
    settings: SavePipelineSettings,
    download_images: bool,
    source_url_fallback: str,
    collection_id: Optional[str] = None,
    printer: Printer = rprint,
) -> list[dict[str, Any]]:
    """
    Save normalized content items to Markdown, images, and SQLite.
    将标准化内容保存到 Markdown、图片目录和 SQLite。
    """
    result = await save_items_result(
        items=items,
        content_root=content_root,
        db_root=db_root,
        settings=settings,
        download_images=download_images,
        source_url_fallback=source_url_fallback,
        collection_id=collection_id,
        printer=printer,
    )
    return result.to_legacy_records()


async def save_items_result(
    *,
    items: Sequence[ScrapedItem] | Sequence[dict[str, Any]],
    content_root: Path,
    db_root: Path,
    settings: SavePipelineSettings,
    download_images: bool,
    source_url_fallback: str,
    collection_id: Optional[str] = None,
    printer: Printer = rprint,
) -> SaveRunResult:
    """
    Save normalized content items to Markdown, images, and SQLite.
    将标准化内容保存到 Markdown、图片目录和 SQLite。
    """
    content_root.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    typed_items = _coerce_scraped_items(items)

    db = ZhihuDatabase(str(db_root / "zhihu.db"))
    saved_records: list[SavedContentRecord] = []
    try:
        for item in typed_items:
            title = sanitize_filename(item.title)
            author = sanitize_filename(item.author)
            item_date = item.date or today
            source_url = item.url or source_url_fallback
            item_key = sanitize_filename(
                f"{item.type or 'item'}-{item.id or 'unknown'}",
                max_length=80,
            )

            folder_name = build_output_folder_name(
                item_date,
                title,
                author,
                item_key,
                folder_template=settings.folder_template,
            )
            folder = content_root / folder_name
            folder.mkdir(parents=True, exist_ok=True)

            img_map: Dict[str, str] = {}
            if download_images:
                img_urls = ZhihuConverter.extract_image_urls(item.html)
                if img_urls:
                    printer(f"   📥 Downloading {len(img_urls)} images... / 下载 {len(img_urls)} 张图片...")
                    img_map = await MediaDownloader.download_images(
                        img_urls,
                        folder / settings.images_subdir,
                        concurrency=settings.image_concurrency,
                        timeout=settings.image_timeout,
                        relative_prefix=settings.images_subdir,
                    )

            converter = ZhihuConverter(img_map=img_map)
            md = converter.convert(item.html)

            header = (
                f"# {item.title}\n\n"
                f"> **Author / 作者**: {item.author}  \n"
                f"> **Source / 来源**: [{source_url}]({source_url})  \n"
                f"> **Date / 日期**: {item_date}\n\n"
                "---\n\n"
            )

            out_path = folder / "index.md"
            full_md = header + md
            out_path.write_text(full_md, encoding="utf-8")

            db_saved = db.save_article(item.to_dict(), full_md, collection_id=collection_id)
            if not db_saved:
                partial_result = SaveRunResult(
                    source_url=source_url_fallback,
                    content_root=content_root,
                    records=tuple(saved_records),
                    collection_id=collection_id,
                )
                raise SavePipelineError(
                    (
                        f"SQLite save failed after writing Markdown for {item.type}:{item.id}; "
                        f"{partial_result.saved_count} item(s) were already archived to disk"
                    ),
                    partial_result=partial_result,
                    failed_item=item,
                    failed_markdown_path=out_path,
                )
            saved_records.append(
                SavedContentRecord(
                    item=item,
                    folder=folder,
                    markdown_path=out_path,
                )
            )

            printer(f"✅ Saved / 保存: [cyan]{author}[/] - {title[:25]}...")
            printer(f"   📁 {out_path} & DB / 入库 DB")
    finally:
        db.close()

    return SaveRunResult(
        source_url=source_url_fallback,
        content_root=content_root,
        records=tuple(saved_records),
        collection_id=collection_id,
    )


def _coerce_scraped_items(items: Sequence[ScrapedItem] | Sequence[dict[str, Any]]) -> Tuple[ScrapedItem, ...]:
    if not items:
        return ()
    first = items[0]
    if isinstance(first, ScrapedItem):
        return tuple(items)  # type: ignore[arg-type]
    return to_scraped_items(items)  # type: ignore[arg-type]
