#!/usr/bin/env python3
import argparse
import csv
import json
import re
import time
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description="Batch fetch Zhihu question answers by offset")
    p.add_argument("url", help="Zhihu question URL")
    p.add_argument("--total", type=int, default=30, help="total answers target")
    p.add_argument("--batch", type=int, default=10, help="batch size per request")
    p.add_argument("--sleep", type=float, default=1.2, help="sleep seconds between batches")
    p.add_argument("--output", required=True, help="output directory")
    p.add_argument("--retry", type=int, default=2, help="retry per batch when request fails")
    p.add_argument("--dedupe", choices=["id", "id+author"], default="id", help="dedupe strategy")
    return p.parse_args()


def extract_question_id(url: str) -> str:
    m = re.search(r"question/(\d+)", url)
    if not m:
        raise ValueError(f"Invalid question url: {url}")
    return m.group(1)


def dedupe_key(item: dict, mode: str) -> str:
    aid = str(item.get("id", ""))
    if mode == "id":
        return aid
    author = (item.get("author") or {}).get("name", "")
    return f"{aid}::{author}"


def fetch_with_retry(client, qid: str, limit: int, offset: int, retry: int, sleep_s: float):
    attempt = 1
    last_exc = None
    while attempt <= retry:
        try:
            return client.get_question_answers(qid, limit=limit, offset=offset)
        except Exception as e:  # noqa: BLE001
            last_exc = e
            if attempt < retry:
                print(f"[warn] batch offset={offset} attempt={attempt}/{retry} failed: {e}")
                time.sleep(sleep_s)
            attempt += 1
    raise RuntimeError(f"batch offset={offset} failed after {retry} attempts: {last_exc}")


def main():
    args = parse_args()
    qid = extract_question_id(args.url)

    from core.api_client import ZhihuAPIClient

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    client = ZhihuAPIClient()
    all_items = []
    seen = set()

    print(
        f"[info] question_id={qid} total={args.total} batch={args.batch} "
        f"sleep={args.sleep} retry={args.retry} dedupe={args.dedupe}"
    )

    fetched = 0
    for offset in range(0, args.total, args.batch):
        limit = min(args.batch, args.total - fetched)
        print(f"[info] fetching offset={offset} limit={limit}")
        try:
            items = fetch_with_retry(client, qid, limit, offset, args.retry, args.sleep)
        except Exception as e:  # noqa: BLE001
            print(f"[warn] batch failed offset={offset}: {e}")
            break

        if not items:
            print(f"[info] empty batch at offset={offset}, stop")
            break

        added = 0
        for it in items:
            key = dedupe_key(it, args.dedupe)
            if not key or key in seen:
                continue
            seen.add(key)
            all_items.append(it)
            added += 1

        fetched = len(all_items)
        print(f"[info] batch got={len(items)} added={added} total_unique={fetched}")

        if fetched >= args.total:
            break

        time.sleep(args.sleep)

    json_path = out_dir / f"question_{qid}_answers.json"
    json_path.write_text(json.dumps(all_items, ensure_ascii=False, indent=2), encoding="utf-8")

    csv_path = out_dir / f"question_{qid}_answers.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["answer_id", "author", "voteup", "comment_count", "created_time", "updated_time", "url", "excerpt"])
        for it in all_items:
            answer_id = it.get("id", "")
            author = (it.get("author") or {}).get("name", "")
            voteup = it.get("voteup_count", 0)
            comment_count = it.get("comment_count", 0)
            created_time = it.get("created_time", "")
            updated_time = it.get("updated_time", "")
            url = f"https://www.zhihu.com/question/{qid}/answer/{answer_id}" if answer_id else ""
            excerpt = (it.get("excerpt", "") or "").replace("\n", " ").strip()
            w.writerow([answer_id, author, voteup, comment_count, created_time, updated_time, url, excerpt])

    print(f"[ok] saved {len(all_items)} answers")
    print(f"[ok] json: {json_path}")
    print(f"[ok] csv:  {csv_path}")


if __name__ == "__main__":
    main()
