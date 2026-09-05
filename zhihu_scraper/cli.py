"""Non-interactive command-line interface over the public archive workflow."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import replace
from importlib.metadata import version
from pathlib import Path

from .facade import ArchiveReport, archive_url, check_session, login_session
from .settings import (
    ArchiveSettings,
    BrowserFallback,
    generate_default_settings,
    load_settings,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="zhihu",
        description="把知乎文章、回答、问题、专栏和独立视频归档到本地。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""常用选择：
  zhihu fetch URL                    Markdown + 媒体（默认）
  zhihu fetch --html URL             再生成离线 HTML
  zhihu fetch --comments URL         再抓取 10×10 评论
  zhihu fetch --html --comments URL  同时开启 HTML 和评论
  zhihu fetch --no-media URL         不下载媒体，只保留远程链接

准备与检查：
  zhihu init                         生成 settings.toml
  zhihu login                        在浏览器中登录并保存验证后的 Cookie
  zhihu check -s settings.toml       检查 Cookie 登录状态""",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {version('zhihu-scraper')}",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    fetch = subcommands.add_parser("fetch", help="抓取并归档一个知乎链接")
    fetch.add_argument("url", help="知乎文章、回答、问题、专栏或 zvideo 链接")
    _settings_argument(fetch)
    output_options = fetch.add_argument_group("输出选项")
    output_options.add_argument("-o", "--output", type=Path, help="覆盖本次保存目录")
    output_options.add_argument(
        "--html",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="本次开启/关闭离线 HTML 输出（默认关闭）",
    )
    output_options.add_argument(
        "--comments",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="本次开启/关闭 10×10 评论抓取",
    )
    output_options.add_argument(
        "--media",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="本次开启/关闭图片、动图和视频下载",
    )
    fetch_path = fetch.add_argument_group("抓取路径")
    fetch_path.add_argument(
        "--browser",
        choices=tuple(mode.value for mode in BrowserFallback),
        help="覆盖浏览器回退策略：auto、never 或 always",
    )
    fetch_path.add_argument("--cdp", help="连接本机已登录 Chrome 的 CDP 地址")

    login = subcommands.add_parser("login", help="手动登录知乎并安全保存已验证的 Cookie")
    _settings_argument(login)
    login.add_argument(
        "--cookie-file",
        type=Path,
        help="Cookie 保存路径；默认使用配置路径或 .local/cookies.json",
    )
    login.add_argument("--cdp", help="只读取本机已登录 Chrome 的 Cookie，不操作现有页面")

    check = subcommands.add_parser("check", help="检查 Cookie 是否存在且仍可登录")
    _settings_argument(check)
    check.add_argument("--cookie-file", type=Path, help="覆盖 Cookie 文件路径")

    init = subcommands.add_parser("init", help="生成简洁的 settings.toml")
    init.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=Path("settings.toml"),
        help="设置文件路径（默认 ./settings.toml）",
    )

    return parser


def run_cli(argv: Sequence[str] | None = None) -> int:
    _configure_standard_streams()
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "init":
            created = generate_default_settings(arguments.path)
            if created:
                print(f"已生成设置文件：{arguments.path}")
            else:
                print(f"设置文件已存在，未覆盖：{arguments.path}")
            return 0

        settings = load_settings(arguments.settings)
        if arguments.command == "login":
            if arguments.cookie_file is not None:
                settings = replace(settings, cookie_file=arguments.cookie_file)
            if arguments.cdp is not None:
                settings = replace(settings, cdp_url=arguments.cdp)
            if settings.cdp_url is None:
                print("请在打开的浏览器中手动登录知乎；最多等待 180 秒，Ctrl+C 可取消。")
            else:
                print("正在读取本机浏览器的知乎登录状态；现有页面保持不变。")
            login_report = login_session(settings)
            settings_path = arguments.settings or Path("settings.toml")
            print(f"登录状态已验证，Cookie 已安全保存：{login_report.cookie_file}")
            print(f'检查：zhihu check --cookie-file "{login_report.cookie_file}"')
            if arguments.settings is None:
                print(f'生成设置：zhihu init "{settings_path}"')
            cookie_setting = json.dumps(str(login_report.cookie_file.resolve()), ensure_ascii=False)
            print(f"在 {settings_path} 的 [network] 分区中设置：cookie_file = {cookie_setting}")
            print(f'然后抓取：zhihu fetch URL -s "{settings_path}"')
            return 0
        if arguments.command == "check":
            if arguments.cookie_file is not None:
                settings = replace(settings, cookie_file=arguments.cookie_file)
            return _run_check(settings)

        if arguments.output is not None:
            settings = replace(settings, output_dir=arguments.output)
        if arguments.html is not None:
            settings = replace(settings, html=arguments.html)
        if arguments.comments is not None:
            settings = replace(settings, comments=arguments.comments)
        if arguments.media is not None:
            settings = replace(settings, media_download=arguments.media)
        if arguments.browser is not None:
            settings = replace(
                settings,
                browser_fallback=BrowserFallback(arguments.browser),
            )
        if arguments.cdp is not None:
            settings = replace(settings, cdp_url=arguments.cdp)

        report = archive_url(arguments.url, settings)
        _print_archive_report(report)
        return 0
    except KeyboardInterrupt:
        print("已取消。", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"错误：{error}", file=sys.stderr)
        return 1


def main() -> None:
    raise SystemExit(run_cli())


def _configure_standard_streams() -> None:
    """Keep Chinese CLI output usable when Windows redirects legacy streams."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            continue


def _settings_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-s",
        "--settings",
        type=Path,
        help="settings.toml 路径；未提供时使用内置默认值",
    )


def _run_check(settings: ArchiveSettings) -> int:
    report = check_session(settings)
    missing = report.cookie_diagnostic.missing
    if missing:
        print(f"Cookie 字段缺少：{', '.join(missing)}")
    else:
        print("Cookie 字段 z_c0、d_c0 均已配置。")
    if report.login_status is None:
        print("未配置 Cookie 文件，未请求知乎登录状态。")
        return 1
    if report.login_status.authenticated:
        print("知乎登录状态有效。")
        return 0
    print("知乎登录状态无效或已过期。")
    return 1


def _print_archive_report(report: ArchiveReport) -> None:
    target = report.target
    receipt = report.receipt
    print(f"归档完成：{target.title}")
    print(f"目录：{receipt.entry_directory}")
    if receipt.markdown_path is not None:
        print(f"Markdown：{receipt.markdown_path}")
    if receipt.html_path is not None:
        print(f"HTML：{receipt.html_path}")
    if report.used_browser:
        print("抓取路径：浏览器回退")
    else:
        print("抓取路径：HTTP/API")
    media_failures = report.media_failures
    if media_failures:
        print(f"媒体警告：{len(media_failures)} 个非必要媒体下载失败，正文归档已保留。")
        for failure in media_failures:
            message = failure.display_message
            print(f"- {message}")
    if report.embedded_video_warnings:
        print(f"内嵌视频警告：{len(report.embedded_video_warnings)} 个视频未下载，已保留原链接。")
        for warning in report.embedded_video_warnings:
            print(f"- {warning.display_message}")


if __name__ == "__main__":
    main()
