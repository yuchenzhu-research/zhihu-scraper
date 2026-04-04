"""
media_downloader.py - Standalone Media Download Module

Handles concurrent image downloading with deduplication and quality preservation.
Extracted from scraper.py to enforce single responsibility.
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import List, Optional

import httpx


class MediaDownloader:
    """
    Handles concurrent file downloads to local directories.
    """

    @classmethod
    async def download_images(
        cls,
        img_urls: List[str],
        dest: Path,
        *,
        concurrency: int = 4,
        timeout: float = 30.0,
        relative_prefix: str = "images",
    ) -> dict[str, str]:
        """
        Download images concurrently with deduplication.

        Image deduplication strategy:
        - Zhihu image naming: v2-xxx_720w.jpg, v2-xxx_r.jpg
        - For same base_name images, download only once, keeping highest quality
        - Returns format "images/xxx.jpg" for Markdown references

        Args:
            img_urls: List of image URLs
            dest: Image save directory
            concurrency: Concurrency count (default 4)
            timeout: Request timeout (default 30s)

        Returns:
            URL -> relative path mapping dict, format "images/xxx.jpg"
        """
        if not img_urls:
            return {}

        dest.mkdir(parents=True, exist_ok=True)
        url_to_local: dict[str, str] = {}

        seen_base: set[str] = set()
        urls_to_download: list[str] = []

        for url in img_urls:
            if url.startswith("//"):
                url = "https:" + url

            if not url or url.startswith("data:") or "noavatar" in url:
                continue

            base_name = url.split("/")[-1].split("?")[0]
            for suffix in ["_720w", "_r", "_l"]:
                if base_name.endswith(suffix + ".jpg"):
                    base_name = base_name.replace(suffix + ".jpg", ".jpg")
                    break
                if base_name.endswith(suffix + ".png"):
                    base_name = base_name.replace(suffix + ".png", ".png")
                    break

            if base_name in seen_base:
                continue
            seen_base.add(base_name)
            urls_to_download.append(url)

        if not urls_to_download:
            return url_to_local

        sem = asyncio.Semaphore(concurrency)
        client = httpx.AsyncClient(headers={
            "Referer": "https://www.zhihu.com/",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        })

        def infer_extension(url: str, content_type: str) -> str:
            lowered_url = url.lower()
            if lowered_url.endswith(".jpg") or lowered_url.endswith(".jpeg"):
                return ".jpg"
            if lowered_url.endswith(".png"):
                return ".png"
            if lowered_url.endswith(".webp"):
                return ".webp"
            if lowered_url.endswith(".gif"):
                return ".gif"
            if lowered_url.endswith(".svg"):
                return ".svg"

            content_type = (content_type or "").split(";")[0].strip().lower()
            mapping = {
                "image/jpeg": ".jpg",
                "image/jpg": ".jpg",
                "image/png": ".png",
                "image/webp": ".webp",
                "image/gif": ".gif",
                "image/svg+xml": ".svg",
            }
            return mapping.get(content_type, ".jpg")

        async def worker(url: str):
            async with sem:
                try:
                    raw_name = url.split("/")[-1].split("?")[0]
                    fname = raw_name
                    for suffix in ["_720w", "_r", "_l"]:
                        if fname.endswith(suffix + ".jpg"):
                            fname = fname.replace(suffix + ".jpg", ".jpg")
                            break
                        if fname.endswith(suffix + ".png"):
                            fname = fname.replace(suffix + ".png", ".png")
                            break

                    stem = Path(fname).stem if "." in fname else (fname or hashlib.sha1(url.encode("utf-8")).hexdigest()[:16])
                    suffix = Path(fname).suffix if "." in fname else ""

                    if suffix:
                        existing_path = dest / f"{stem}{suffix}"
                        if existing_path.exists():
                            url_to_local[url] = f"{relative_prefix}/{existing_path.name}"
                            return
                    else:
                        for existing_path in sorted(dest.glob(f"{stem}.*")):
                            if existing_path.is_file():
                                url_to_local[url] = f"{relative_prefix}/{existing_path.name}"
                                return

                    last_error: Optional[Exception] = None
                    resp: Optional[httpx.Response] = None
                    for attempt in range(1, 4):
                        try:
                            resp = await client.get(url, timeout=timeout)
                            resp.raise_for_status()
                            break
                        except Exception as e:
                            last_error = e
                            if attempt < 3:
                                await asyncio.sleep(0.8 * attempt)
                            else:
                                raise

                    assert resp is not None

                    if not suffix:
                        suffix = infer_extension(url, resp.headers.get("Content-Type", ""))

                    final_name = f"{stem}{suffix}"
                    local_path = dest / final_name

                    if local_path.exists():
                        url_to_local[url] = f"{relative_prefix}/{final_name}"
                        return

                    with open(local_path, "wb") as f:
                        f.write(resp.content)

                    url_to_local[url] = f"{relative_prefix}/{final_name}"

                except Exception as e:
                    print(f"⚠️ 图片下载失败 [{url}]: {e}")

        tasks = [worker(url) for url in urls_to_download]
        await asyncio.gather(*tasks)
        await client.aclose()

        return url_to_local
