"""Print local archive documents to portable PDFs in an isolated offline browser."""

from __future__ import annotations

import io
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Protocol
from urllib.parse import quote, unquote, urlsplit
from urllib.request import url2pathname

from bs4 import BeautifulSoup
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, TextStringObject

from .platform import RuntimePlatform
from .render import HtmlRenderer


class PdfExportError(RuntimeError):
    """A PDF could not be produced or published."""


@dataclass(frozen=True, slots=True)
class PdfDocument:
    destination: Path
    html: str


class PdfBrowser(Protocol):
    def render(self, html_path: Path, *, resource_root: Path) -> bytes: ...

    def close(self) -> None: ...


class PdfExporter(Protocol):
    def __call__(self, documents: Sequence[PdfDocument], *, resource_root: Path) -> None: ...


def export_pdfs(
    documents: Sequence[PdfDocument],
    *,
    resource_root: Path,
    browser_factory: Callable[[], PdfBrowser] | None = None,
) -> None:
    """Save PDFs in caller order, keeping all temporary HTML and PDF files private."""
    if not documents:
        return
    browser = (browser_factory or PlaywrightPdfBrowser)()
    try:
        for document in documents:
            destination = document.destination
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary_html: Path | None = None
            temporary_pdf: Path | None = None
            try:
                with NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    suffix=".html",
                    prefix=".pdf-",
                    dir=destination.parent,
                    delete=False,
                ) as output:
                    temporary_html = Path(output.name)
                    output.write(_print_html(document.html, destination, resource_root))
                data = browser.render(temporary_html, resource_root=resource_root)
                portable = _portable_pdf(data, destination, resource_root)
                with NamedTemporaryFile(
                    mode="wb",
                    suffix=".tmp",
                    prefix=".pdf-",
                    dir=destination.parent,
                    delete=False,
                ) as output:
                    temporary_pdf = Path(output.name)
                    output.write(portable)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary_pdf, destination)
            finally:
                if temporary_html is not None:
                    temporary_html.unlink(missing_ok=True)
                if temporary_pdf is not None:
                    temporary_pdf.unlink(missing_ok=True)
    except PdfExportError:
        raise
    except Exception as error:
        raise PdfExportError("PDF 导出失败；请检查浏览器运行环境和保存目录。") from error
    finally:
        browser.close()


def pdf_source_url(path: Path) -> str | None:
    """Recover the first visible Zhihu source link from an archive PDF."""
    from .urls import UnsupportedZhihuUrlError, route_zhihu_url

    try:
        with path.open("rb") as source:
            reader = PdfReader(source, strict=True)
            if not reader.metadata or reader.metadata.get("/Creator") != "zhihu-scraper":
                return None
            for page in reader.pages:
                for annotation in page.get("/Annots", []):
                    action = annotation.get_object().get("/A")
                    uri = action.get("/URI") if action is not None else None
                    if not isinstance(uri, str):
                        continue
                    try:
                        route_zhihu_url(uri)
                    except UnsupportedZhihuUrlError:
                        continue
                    return uri
    except Exception:
        return None
    return None


def _portable_pdf(data: bytes, destination: Path, resource_root: Path) -> bytes:
    reader = PdfReader(io.BytesIO(data), strict=True)
    if not reader.pages:
        raise PdfExportError("浏览器未生成有效 PDF 页面。")
    writer = PdfWriter(clone_from=reader)
    writer.add_metadata({"/Creator": "zhihu-scraper"})
    for page in writer.pages:
        for annotation in page.get("/Annots", []):
            action = annotation.get_object().get("/A")
            if action is None or not isinstance(action.get("/URI"), str):
                continue
            uri = action["/URI"]
            local = _local_resource(uri, destination.parent, resource_root)
            if local is not None:
                relative = Path(os.path.relpath(local, destination.parent.resolve())).as_posix()
                action[NameObject("/URI")] = TextStringObject(quote(relative, safe="/._~-"))
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _local_resource(url: str, parent: Path, root: Path) -> Path | None:
    parsed = urlsplit(url)
    if parsed.scheme == "file" and parsed.netloc in {"", "localhost"}:
        path = Path(url2pathname(parsed.path))
    elif not parsed.scheme and not parsed.netloc:
        path = parent / unquote(parsed.path)
    else:
        return None
    resolved = path.resolve()
    return resolved if resolved.is_relative_to(root.resolve()) else None


_PRINT_CSS = """
@media print {
  :root { color-scheme: light; line-height: 1.65; }
  body { background: white; margin: 0; padding: 0; max-width: none; font-size: 11pt; }
  main { max-width: none; padding: 0; margin: 0; }
  h1 { margin-top: 0; font-size: 21pt; }
  h1, h2, h3, h4 { break-after: avoid; }
  .metadata p { margin: 0.25em 0; }
  pre { white-space: pre-wrap; overflow-wrap: anywhere; }
  tr, figure, img { break-inside: avoid; }
  table { display: table; max-width: 100%; font-size: 10pt; }
  th, td { overflow-wrap: anywhere; }
  .math-display { overflow: visible; break-inside: avoid; }
  img { max-height: 230mm; object-fit: contain; }
  a { overflow-wrap: anywhere; }
}
"""


def _print_html(markup: str, destination: Path, resource_root: Path) -> str:
    soup = BeautifulSoup(markup, "html.parser")
    for node in soup.find_all(["script", "iframe", "object", "embed", "base", "link"]):
        node.decompose()
    for node in soup.find_all(["img", "video", "source"]):
        source = str(node.get("src") or "")
        path = _local_resource(source, destination.parent, resource_root) if source else None
        if path is None:
            node.decompose()
        else:
            node["src"] = path.as_uri()
    head = soup.head
    if head is None:
        raise PdfExportError("PDF 导出需要完整的本地 HTML 文档。")
    policy = soup.new_tag("meta")
    policy["http-equiv"] = "Content-Security-Policy"
    policy["content"] = (
        "default-src 'none'; style-src 'unsafe-inline'; img-src file:; font-src data:"
    )
    head.insert(0, policy)
    style = soup.new_tag("style")
    style.string = "\n".join((*HtmlRenderer.assets().values(), _PRINT_CSS))
    head.append(style)
    return str(soup)


class PlaywrightPdfBrowser:
    """Ephemeral Chromium adapter; no cookies, profiles, proxies or remote requests."""

    def __init__(self, *, runtime_platform: RuntimePlatform | None = None) -> None:
        self._runtime = runtime_platform or RuntimePlatform.detect()
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None

    def _start(self) -> None:
        if self._context is not None:
            return
        try:
            from playwright.sync_api import sync_playwright

            self._playwright = sync_playwright().start()
            candidates = [
                Path(candidate)
                for candidate in self._runtime.browser_candidates
                if Path(candidate).is_file()
            ]
            for executable in [*candidates, None]:
                options: dict[str, Any] = {
                    "headless": True,
                    "args": [
                        "--disable-background-networking",
                        "--disable-component-update",
                        "--disable-sync",
                        "--no-first-run",
                    ],
                }
                if executable is not None:
                    options["executable_path"] = str(executable)
                try:
                    self._browser = self._playwright.chromium.launch(**options)
                    break
                except Exception:
                    continue
            if self._browser is None:
                raise PdfExportError(
                    "PDF 浏览器启动失败：请安装 Chrome 或运行 playwright install chromium。"
                )
            self._context = self._browser.new_context(
                java_script_enabled=False,
                service_workers="block",
                offline=True,
            )
            self._context.route(
                "**/*",
                lambda route: (
                    route.abort()
                    if urlsplit(route.request.url).scheme not in {"file", "data", "about"}
                    else route.continue_()
                ),
            )
        except PdfExportError:
            raise
        except Exception as error:
            raise PdfExportError("PDF 浏览器不可用：请安装 Playwright 及 Chromium。") from error

    def render(self, html_path: Path, *, resource_root: Path) -> bytes:
        self._start()
        page = self._context.new_page()

        def local_request(route: Any) -> None:
            url = route.request.url
            scheme = urlsplit(url).scheme
            if scheme in {"data", "about"} or (
                scheme == "file"
                and _local_resource(url, html_path.parent, resource_root) is not None
            ):
                route.continue_()
            else:
                route.abort()

        try:
            page.route("**/*", local_request)
            page.goto(html_path.resolve().as_uri(), wait_until="load", timeout=30_000)
            return bytes(
                page.pdf(
                    format="A4",
                    print_background=True,
                    prefer_css_page_size=True,
                    margin={"top": "18mm", "right": "16mm", "bottom": "18mm", "left": "16mm"},
                )
            )
        finally:
            page.close()

    def close(self) -> None:
        try:
            if self._context is not None:
                self._context.close()
        finally:
            try:
                if self._browser is not None:
                    self._browser.close()
            finally:
                if self._playwright is not None:
                    self._playwright.stop()
                self._context = self._browser = self._playwright = None
