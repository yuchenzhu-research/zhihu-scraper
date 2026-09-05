"""Explicit real-browser PDF smoke; ordinary pytest collection never runs this file."""

from __future__ import annotations

import argparse
import io
import struct
import tempfile
import threading
import unicodedata
import zlib
from dataclasses import replace
from datetime import UTC, datetime
from functools import partial
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from pypdf import PdfReader

from zhihu_scraper.archive import LocalArchive
from zhihu_scraper.domain import (
    Article,
    Author,
    Column,
    ColumnArchive,
    FormulaBlock,
    MediaAsset,
    MediaBlock,
    MediaKind,
    MediaRendition,
    Paragraph,
    TableBlock,
    Text,
)
from zhihu_scraper.media import MediaDownloadReceipt
from zhihu_scraper.pdf_export import PlaywrightPdfBrowser, export_pdfs
from zhihu_scraper.platform import RuntimePlatform


def _png_fixture() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    header = chunk(b"IHDR", struct.pack(">IIBBBBB", 32, 16, 8, 2, 0, 0, 0))
    pixels = zlib.compress((b"\0" + b"\x30\x70\xc0" * 32) * 16)
    return b"\x89PNG\r\n\x1a\n" + header + chunk(b"IDAT", pixels) + chunk(b"IEND", b"")


def _check_offline_browser(root: Path, runtime: RuntimePlatform) -> None:
    requests: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            requests.append(self.path)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"unexpected outbound request")

        def log_message(self, format: str, *args: object) -> None:
            pass

    with HTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        browser = PlaywrightPdfBrowser(runtime_platform=runtime)
        try:
            url = f"http://127.0.0.1:{server.server_port}"
            html = root / "network-probe.html"
            html.write_text(
                f'<html><head><title>offline smoke</title><link rel="stylesheet" href="{url}/style.css">'
                f'</head><body><p>offline probe</p><img src="{url}/image.png">'
                f'<script src="{url}/script.js"></script></body></html>',
                encoding="utf-8",
            )
            # Exercise the browser adapter directly, before the exporter's HTML sanitization.
            data = browser.render(html, resource_root=root)
            assert len(PdfReader(io.BytesIO(data)).pages) == 1
        finally:
            try:
                browser.close()
            finally:
                server.shutdown()
                thread.join(timeout=5)
        assert not thread.is_alive(), "network probe thread did not close"
        assert not requests, f"PDF browser requested remote resources: {requests}"


def _check_column(root: Path, runtime: RuntimePlatform) -> tuple[int, int]:
    png = _png_fixture()
    image_url = "https://pic1.zhimg.com/pdf-smoke.png"

    def local_image(
        source_url: str,
        destination: Path,
        *,
        expected_size: int | None = None,
    ) -> MediaDownloadReceipt:
        assert source_url == image_url
        assert expected_size in {None, len(png)}
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(png)
        return MediaDownloadReceipt(source_url, destination, 0, len(png))

    first = Article(
        id="1",
        title="公式与表格",
        source_url="https://zhuanlan.zhihu.com/p/1",
        author=Author("smoke", "中文作者"),
        published_at=datetime(2026, 9, 5, tzinfo=UTC),
        blocks=(
            Paragraph((Text("中文 PDF archive smoke"),)),
            FormulaBlock(r"p(x)=\frac{1}{\sqrt{2\pi}}e^{-x^2/2}"),
            TableBlock(
                headers=((Text("模型 Model"),), (Text("数值 Value"),)),
                rows=(((Text("基线 Baseline"),), (Text("0.95"),)),),
            ),
        ),
    )
    second = replace(
        first,
        id="2",
        title="本地图片",
        source_url="https://zhuanlan.zhihu.com/p/2",
        blocks=(
            MediaBlock(
                MediaAsset(
                    id="smoke-image",
                    kind=MediaKind.IMAGE,
                    renditions=(
                        MediaRendition(image_url, mime_type="image/png", size_bytes=len(png)),
                    ),
                    alt_text="本地图片",
                )
            ),
        ),
    )
    column = ColumnArchive(
        Column("pdf-smoke", "离线 PDF 专栏", "https://www.zhihu.com/column/pdf-smoke", "", None, 2),
        (first, second),
        datetime(2026, 9, 5, tzinfo=UTC),
    )
    sink = LocalArchive(
        root,
        markdown=False,
        pdf=True,
        downloader=local_image,
        pdf_exporter=partial(
            export_pdfs,
            browser_factory=lambda: PlaywrightPdfBrowser(runtime_platform=runtime),
        ),
    )
    receipt = sink.archive(column)
    assert receipt.pdf_path is not None and len(receipt.child_pdf_paths) == 2
    first_pdf = PdfReader(receipt.child_pdf_paths[0])
    text = unicodedata.normalize("NFKC", "".join(page.extract_text() for page in first_pdf.pages))
    assert "中文" in text and "Baseline" in text and "0.95" in text, text
    assert "p(x)=" in "".join(text.split()), "MathML formula is missing from the PDF"
    second_pdf = PdfReader(receipt.child_pdf_paths[1])
    assert any(page.images for page in second_pdf.pages), "local PNG was not embedded in the PDF"

    moved = receipt.entry_directory.with_name("moved-column")
    receipt.entry_directory.rename(moved)
    pdf_files = tuple(moved.rglob("*.pdf"))
    assert len(pdf_files) == 3
    local_links = 0
    for path in pdf_files:
        reader = PdfReader(path, strict=True)
        assert reader.pages and reader.metadata["/Creator"] == "zhihu-scraper"
        for page in reader.pages:
            for annotation in page.get("/Annots", []):
                uri = annotation.get_object().get("/A", {}).get("/URI", "")
                if not uri or urlsplit(uri).scheme:
                    continue
                target = (path.parent / unquote(uri)).resolve()
                assert target.is_relative_to(moved.resolve()) and target.is_file(), uri
                local_links += 1
    assert local_links >= 6, "column navigation was not preserved"
    assert not tuple(moved.rglob("*.html"))
    assert not tuple(moved.rglob(".pdf-*"))
    assert not (moved / "assets").exists()
    return len(pdf_files), local_links


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--system-chrome",
        action="store_true",
        help="Allow detected system Chrome for local validation; CI always uses managed Chromium.",
    )
    options = parser.parse_args()
    runtime = RuntimePlatform.detect()
    if not options.system_chrome:
        runtime = replace(runtime, browser_candidates=())
    with tempfile.TemporaryDirectory(prefix="zhihu-pdf-smoke-") as temporary_directory:
        root = Path(temporary_directory)
        _check_offline_browser(root, runtime)
        pdfs, links = _check_column(root, runtime)
    print(f"PDF smoke passed: {pdfs} readable PDFs, {links} portable links, no remote requests.")


if __name__ == "__main__":
    main()
