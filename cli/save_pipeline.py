"""
save_pipeline.py - Local archive save orchestration

Extracts output naming, Markdown persistence, image downloading, and creator
metadata writing from the main CLI module so command entrypoints stay thin.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from rich import print as rprint

from core.converter import ZhihuConverter
from core.db import ZhihuDatabase
from core.scraper import ZhihuCreatorDownloader, ZhihuDownloader
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
) -> List[Dict[str, Any]]:
    """
    Execute scraping and save the result to local files and SQLite.
    执行抓取，并保存到本地文件和 SQLite。
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    downloader = ZhihuDownloader(url)
    fetch_kwargs = dict(scrape_config)
    fetch_kwargs["headless"] = headless
    data = await downloader.fetch_page(**fetch_kwargs)

    if not data:
        printer("[yellow]⚠️  No content obtained / 未获取到内容[/yellow]")
        return []

    items = data if isinstance(data, list) else [data]
    return await save_items(
        items=items,
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
) -> None:
    """
    Fetch creator content and persist it using the standard save pipeline.
    抓取作者内容，并复用标准保存链路落地。
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    downloader = ZhihuCreatorDownloader(creator)
    result = await downloader.fetch_items(answer_limit=answer_limit, article_limit=article_limit)
    creator_info = result.get("creator", {})
    items = result.get("items", [])
    sync_info = result.get("sync", {})

    if not items:
        printer("[yellow]⚠️  No creator content obtained / 未获取到作者内容[/yellow]")
        return

    creator_name = creator_info.get("name", creator_info.get("url_token", creator))
    printer(f"[cyan]👤 Creator / 作者[/cyan]: {creator_name} ({creator_info.get('url_token', 'unknown')})")
    if creator_info.get("follower_count") or creator_info.get("following_count"):
        printer(
            f"   👥 Followers / 粉丝: {creator_info.get('follower_count', 0)}"
            f" | Following / 关注: {creator_info.get('following_count', 0)}"
        )

    creator_root = resolve_creator_output_dir(output_dir, creator_info.get("url_token", creator))

    saved_records = await save_items(
        items=items,
        content_root=creator_root,
        db_root=output_dir,
        settings=settings,
        download_images=download_images,
        source_url_fallback=f"https://www.zhihu.com/people/{creator_info.get('url_token', creator)}",
        printer=printer,
    )

    write_creator_metadata(creator_root, creator_info, saved_records, sync_info)


async def save_items(
    *,
    items: List[Dict[str, Any]],
    content_root: Path,
    db_root: Path,
    settings: SavePipelineSettings,
    download_images: bool,
    source_url_fallback: str,
    collection_id: Optional[str] = None,
    printer: Printer = rprint,
) -> List[Dict[str, Any]]:
    """
    Save normalized content items to Markdown, images, and SQLite.
    将标准化内容保存到 Markdown、图片目录和 SQLite。
    """
    content_root.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")

    db = ZhihuDatabase(str(db_root / "zhihu.db"))
    saved_records: List[Dict[str, Any]] = []
    try:
        for item in items:
            title = sanitize_filename(item["title"])
            author = sanitize_filename(item["author"])
            item_date = item.get("date") or today
            source_url = item.get("url") or source_url_fallback
            item_key = sanitize_filename(
                f"{item.get('type', 'item')}-{item.get('id', 'unknown')}",
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
                img_urls = ZhihuConverter.extract_image_urls(item["html"])
                if img_urls:
                    printer(f"   📥 Downloading {len(img_urls)} images... / 下载 {len(img_urls)} 张图片...")
                    img_map = await ZhihuDownloader.download_images(
                        img_urls,
                        folder / settings.images_subdir,
                        concurrency=settings.image_concurrency,
                        timeout=settings.image_timeout,
                        relative_prefix=settings.images_subdir,
                    )

            converter = ZhihuConverter(img_map=img_map)
            md = converter.convert(item["html"])

            header = (
                f"# {item['title']}\n\n"
                f"> **Author / 作者**: {item['author']}  \n"
                f"> **Source / 来源**: [{source_url}]({source_url})  \n"
                f"> **Date / 日期**: {item_date}\n\n"
                "---\n\n"
            )

            out_path = folder / "index.md"
            full_md = header + md
            out_path.write_text(full_md, encoding="utf-8")

            db.save_article(item, full_md, collection_id=collection_id)
            saved_records.append(
                {
                    "item": item,
                    "folder": folder,
                    "markdown_path": out_path,
                }
            )

            printer(f"✅ Saved / 保存: [cyan]{author}[/] - {title[:25]}...")
            printer(f"   📁 {out_path} & DB / 入库 DB")
    finally:
        db.close()

    return saved_records


def write_creator_metadata(
    creator_root: Path,
    creator_info: Dict[str, Any],
    saved_records: List[Dict[str, Any]],
    sync_info: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Write creator metadata files under the creator directory.
    在作者目录下写入元信息文件。
    """
    fetched_at = datetime.now().isoformat(timespec="seconds")
    answer_records = [record for record in saved_records if record["item"].get("type") == "answer"]
    article_records = [record for record in saved_records if record["item"].get("type") == "article"]
    sync_info = sync_info or {}
    answer_sync = sync_info.get("answers", {})
    article_sync = sync_info.get("articles", {})
    recent_records = sorted(
        saved_records,
        key=lambda record: record["item"].get("date", ""),
        reverse=True,
    )[:5]

    creator_payload = {
        "user_id": creator_info.get("user_id", ""),
        "name": creator_info.get("name", creator_info.get("url_token", "unknown")),
        "url_token": creator_info.get("url_token", "unknown"),
        "profile_url": creator_info.get(
            "profile_url",
            f"https://www.zhihu.com/people/{creator_info.get('url_token', 'unknown')}",
        ),
        "avatar_url": creator_info.get("avatar_url", ""),
        "headline": creator_info.get("headline", ""),
        "description": creator_info.get("description", ""),
        "follower_count": creator_info.get("follower_count", 0),
        "following_count": creator_info.get("following_count", 0),
        "voteup_count": creator_info.get("voteup_count", 0),
        "answer_count": creator_info.get("answer_count", 0),
        "articles_count": creator_info.get("articles_count", 0),
        "question_count": creator_info.get("question_count", 0),
        "video_count": creator_info.get("video_count", 0),
        "column_count": creator_info.get("column_count", 0),
        "fetched_at": fetched_at,
        "last_sync_at": fetched_at,
        "saved_answers": len(answer_records),
        "saved_articles": len(article_records),
        "local_root": str(creator_root),
        "sync": {
            "answers": answer_sync,
            "articles": article_sync,
        },
        "recent_items": [
            {
                "id": record["item"].get("id", ""),
                "type": record["item"].get("type", ""),
                "title": record["item"].get("title", ""),
                "date": record["item"].get("date", ""),
                "markdown_path": str(record["markdown_path"].relative_to(creator_root)),
            }
            for record in recent_records
        ],
        "items": [
            {
                "id": record["item"].get("id", ""),
                "type": record["item"].get("type", ""),
                "title": record["item"].get("title", ""),
                "date": record["item"].get("date", ""),
                "url": record["item"].get("url", ""),
                "markdown_path": str(record["markdown_path"].relative_to(creator_root)),
            }
            for record in saved_records
        ],
    }

    creator_json_path = creator_root / "creator.json"
    creator_json_path.write_text(
        json.dumps(creator_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        f"# {creator_payload['name']}",
        "",
        f"> **User ID**: `{creator_payload['user_id'] or 'unknown'}`  ",
        f"> **URL Token**: `{creator_payload['url_token']}`  ",
        f"> **Zhihu Profile / 作者主页**: [{creator_payload['profile_url']}]({creator_payload['profile_url']})  ",
        f"> **Fetched At / 抓取时间**: {creator_payload['fetched_at']}  ",
        f"> **Last Sync / 最近同步**: {creator_payload['last_sync_at']}",
        "",
    ]

    if creator_payload["avatar_url"]:
        lines.extend(
            [
                f"> **Avatar / 头像**: {creator_payload['avatar_url']}",
                "",
            ]
        )

    if creator_payload["headline"]:
        lines.extend(
            [
                f"> **Headline / 简介**: {creator_payload['headline']}",
                "",
            ]
        )

    if creator_payload["description"] and creator_payload["description"] != creator_payload["headline"]:
        lines.extend(
            [
                f"> **Description / 描述**: {creator_payload['description']}",
                "",
            ]
        )

    lines.extend(
        [
            "## Summary / 概览",
            "",
            f"- Followers / 粉丝: {creator_payload['follower_count']}",
            f"- Following / 关注: {creator_payload['following_count']}",
            f"- Total upvotes / 总获赞: {creator_payload['voteup_count']}",
            f"- Zhihu answers / 知乎回答数: {creator_payload['answer_count']}",
            f"- Zhihu articles / 知乎专栏数: {creator_payload['articles_count']}",
            f"- Zhihu questions / 提问数: {creator_payload['question_count']}",
            f"- Zhihu videos / 视频数: {creator_payload['video_count']}",
            f"- Zhihu columns / 专栏数: {creator_payload['column_count']}",
            f"- Saved answers / 已保存回答: {creator_payload['saved_answers']}",
            f"- Saved articles / 已保存专栏: {creator_payload['saved_articles']}",
            f"- Local root / 本地目录: `{creator_payload['local_root']}`",
            "",
            "## Sync Status / 同步状态",
            "",
            f"- Answers: requested {answer_sync.get('requested_limit', 0)}, saved {answer_sync.get('saved_count', 0)}, pages {answer_sync.get('pages_fetched', 0)}, last_offset {answer_sync.get('last_offset', 0)}, reached_end {answer_sync.get('reached_end', False)}, stopped_early {answer_sync.get('stopped_early', False)}",
            f"- Articles: requested {article_sync.get('requested_limit', 0)}, saved {article_sync.get('saved_count', 0)}, pages {article_sync.get('pages_fetched', 0)}, last_offset {article_sync.get('last_offset', 0)}, reached_end {article_sync.get('reached_end', False)}, stopped_early {article_sync.get('stopped_early', False)}",
            "",
            "## Recent Items / 最近内容",
            "",
        ]
    )

    if creator_payload["recent_items"]:
        lines.extend(
            [
                "| Type | Title | Date | Markdown |",
                "|---|---|---|---|",
            ]
        )
        for item in creator_payload["recent_items"]:
            escaped_title = item["title"].replace("|", "\\|")
            lines.append(
                f"| {item['type']} | {escaped_title} | {item['date']} | "
                f"[index.md]({item['markdown_path']}) |"
            )
        lines.append("")

    lines.extend(
        [
            "## Items / 内容列表",
            "",
        ]
    )

    for section_title, records in (
        ("### Answers / 回答", answer_records),
        ("### Articles / 专栏", article_records),
    ):
        lines.extend([section_title, ""])
        if not records:
            lines.extend(["- None / 暂无", ""])
            continue

        lines.extend(
            [
                "| Title | Date | Markdown | Source |",
                "|---|---|---|---|",
            ]
        )
        for record in records:
            item = record["item"]
            title = item.get("title", "").replace("|", "\\|")
            item_date = item.get("date", "")
            markdown_rel = record["markdown_path"].relative_to(creator_root)
            source_url = item.get("url", "")
            lines.append(
                f"| {title} | {item_date} | "
                f"[index.md]({markdown_rel.as_posix()}) | [source]({source_url}) |"
            )
        lines.append("")

    creator_readme_path = creator_root / "README.md"
    creator_readme_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
