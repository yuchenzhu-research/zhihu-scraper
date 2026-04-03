"""
creator_metadata.py - Creator archive metadata serialization and README rendering.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any, Optional, Sequence, Tuple

from cli.save_contracts import CreatorSaveResult, SaveRunResult, SavedContentRecord
from core.scraper_contracts import CreatorProfileSummary


def write_creator_metadata(
    creator_root: Path,
    creator_info: dict[str, Any] | CreatorProfileSummary,
    saved_records: SaveRunResult | Sequence[SavedContentRecord] | Sequence[dict[str, Any]],
    sync_info: Optional[dict[str, Any] | CreatorSaveResult] = None,
) -> None:
    """
    Write creator metadata files under the creator directory.
    在作者目录下写入元信息文件。
    """
    fetched_at = datetime.now().isoformat(timespec="seconds")
    creator_payload = creator_info.to_dict() if isinstance(creator_info, CreatorProfileSummary) else dict(creator_info)
    typed_records = _coerce_saved_records(saved_records)
    answer_records = [record for record in typed_records if record.item.type == "answer"]
    article_records = [record for record in typed_records if record.item.type == "article"]
    answer_sync, article_sync = _coerce_creator_sync(sync_info)
    recent_records = sorted(
        typed_records,
        key=lambda record: record.item.date,
        reverse=True,
    )[:5]

    creator_payload = {
        "user_id": creator_payload.get("user_id", ""),
        "name": creator_payload.get("name", creator_payload.get("url_token", "unknown")),
        "url_token": creator_payload.get("url_token", "unknown"),
        "profile_url": creator_payload.get(
            "profile_url",
            f"https://www.zhihu.com/people/{creator_payload.get('url_token', 'unknown')}",
        ),
        "avatar_url": creator_payload.get("avatar_url", ""),
        "headline": creator_payload.get("headline", ""),
        "description": creator_payload.get("description", ""),
        "follower_count": creator_payload.get("follower_count", 0),
        "following_count": creator_payload.get("following_count", 0),
        "voteup_count": creator_payload.get("voteup_count", 0),
        "answer_count": creator_payload.get("answer_count", 0),
        "articles_count": creator_payload.get("articles_count", 0),
        "question_count": creator_payload.get("question_count", 0),
        "video_count": creator_payload.get("video_count", 0),
        "column_count": creator_payload.get("column_count", 0),
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
                "id": record.item.id,
                "type": record.item.type,
                "title": record.item.title,
                "date": record.item.date,
                "markdown_path": str(record.markdown_path.relative_to(creator_root)),
            }
            for record in recent_records
        ],
        "items": [
            {
                "id": record.item.id,
                "type": record.item.type,
                "title": record.item.title,
                "date": record.item.date,
                "url": record.item.url,
                "markdown_path": str(record.markdown_path.relative_to(creator_root)),
            }
            for record in typed_records
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
            title = record.item.title.replace("|", "\\|")
            item_date = record.item.date
            markdown_rel = record.markdown_path.relative_to(creator_root)
            source_url = record.item.url
            lines.append(
                f"| {title} | {item_date} | "
                f"[index.md]({markdown_rel.as_posix()}) | [source]({source_url}) |"
            )
        lines.append("")

    creator_readme_path = creator_root / "README.md"
    creator_readme_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _coerce_saved_records(
    saved_records: SaveRunResult | Sequence[SavedContentRecord] | Sequence[dict[str, Any]],
) -> Tuple[SavedContentRecord, ...]:
    if isinstance(saved_records, SaveRunResult):
        return saved_records.records
    if not saved_records:
        return ()
    first = saved_records[0]
    if isinstance(first, SavedContentRecord):
        return tuple(saved_records)  # type: ignore[arg-type]
    return tuple(SavedContentRecord.from_legacy_dict(record) for record in saved_records)  # type: ignore[arg-type]


def _coerce_creator_sync(sync_info: Optional[dict[str, Any] | CreatorSaveResult]) -> Tuple[dict[str, Any], dict[str, Any]]:
    if isinstance(sync_info, CreatorSaveResult):
        return sync_info.answers.to_dict(), sync_info.articles.to_dict()
    if not sync_info:
        return {}, {}
    return sync_info.get("answers", {}), sync_info.get("articles", {})
