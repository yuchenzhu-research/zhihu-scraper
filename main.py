"""
main.py — 知乎离线化工具入口
支持用户粘贴含 URL 的杂乱文本，自动提取并逐个处理。
"""

import asyncio
import re
import sys
from pathlib import Path

from converter import get_image_urls, html_to_markdown, sanitize_filename
from scraper import ZhihuDownloader

# ==========================================
# 批量下载列表 (如果你不想使用命令行输入，可以在这里填入链接)
# 格式: ["https://...", "https://..."]
# ==========================================
BATCH_URLS = [
    # "https://zhuanlan.zhihu.com/p/xxxxx",
    # "https://www.zhihu.com/question/xxx/answer/xxx",
]

DATA_DIR = Path(__file__).parent / "data"


def extract_urls(text: str) -> list[str]:
    """从任意文本中提取知乎链接。"""
    pattern = r"https?://(?:zhuanlan\.zhihu\.com/p/\d+|www\.zhihu\.com/question/\d+/answer/\d+)"
    return list(dict.fromkeys(re.findall(pattern, text)))


async def process_one(url: str) -> None:
    """处理单个知乎链接：抓取 → 下载图片 → 转换 → 保存。"""
    print(f"\n{'='*60}")
    print(f"📥 正在抓取: {url}")

    downloader = ZhihuDownloader(url)

    # 1. 抓取页面
    info = await downloader.fetch_page()
    title = info["title"]
    author = info["author"]
    date = info["date"]
    html = info["html"]

    print(f"📄 标题: {title}")
    print(f"✍️  作者: {author}")

    # 2. 构建输出目录
    folder_name = sanitize_filename(f"[{date}] {title} - {author}")
    out_dir = DATA_DIR / folder_name
    img_dir = out_dir / "images"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 3. 提取并下载图片
    img_urls = get_image_urls(html)
    print(f"🖼️  发现 {len(img_urls)} 张图片，正在下载...")

    img_map = await ZhihuDownloader.download_images(img_urls, img_dir)
    print(f"✅ 成功下载 {len(img_map)} 张图片")

    # 4. 转换 Markdown
    md_content = html_to_markdown(html, img_map)

    # 加上元信息头
    header = (
        f"# {title}\n\n"
        f"> **作者**: {author}  \n"
        f"> **来源**: [{url}]({url})  \n"
        f"> **日期**: {date}\n\n"
        f"---\n\n"
    )
    md_content = header + md_content

    # 5. 保存
    md_path = out_dir / "index.md"
    md_path.write_text(md_content, encoding="utf-8")
    print(f"💾 已保存至: {out_dir}")

    # 如果没有图片就删除空目录
    if img_dir.exists() and not any(img_dir.iterdir()):
        img_dir.rmdir()


async def main() -> None:
    """主循环：持续接收用户输入。"""
    print("=" * 60)
    print("📚 知乎离线化工具")
    print("=" * 60)
    print("支持链接类型:")
    print("  - 专栏文章: https://zhuanlan.zhihu.com/p/xxxxxxx")
    print("  - 问题回答: https://www.zhihu.com/question/xxx/answer/xxx")
    print("输入 q 退出\n")

    while True:
        # 优先处理 BATCH_URLS
        if BATCH_URLS:
            print(f"📋 检测到 BATCH_URLS 中有 {len(BATCH_URLS)} 个链接，开始自动处理...")
            target_urls = list(BATCH_URLS)
            # 处理完批次链接后清空，避免重复处理，并退出循环
            BATCH_URLS.clear()
        else:
            try:
                print(f"\n🔗 请粘贴知乎链接 (可包含其它文字): ", end="", flush=True)
                user_input = sys.stdin.readline().strip()
            except (EOFError, KeyboardInterrupt):
                print("\n👋 再见!")
                break

            if user_input.lower() == "q":
                print("👋 再见!")
                break

            target_urls = re.findall(
                r"https?://(?:www\.|zhuanlan\.)?zhihu\.com/(?:p/\d+|question/\d+/answer/\d+)",
                user_input,
            )

        if not target_urls:
            print("⚠️ 未检测到有效链接，请重新输入")
            if not BATCH_URLS: # Only continue if not in batch mode
                continue
            else: # If BATCH_URLS was empty, break
                break

        print(f"🔍 检测到 {len(target_urls)} 个链接")

        for url in target_urls:
            try:
                await process_one(url)
            except Exception as e:
                err_msg = str(e)
                if "ERR_PROXY_CONNECTION_FAILED" in err_msg or "Connection refused" in err_msg:
                    print(f"\n❌ 代理连接失败: {e}")
                    print("💡 提示: 请检查本地代理 (127.0.0.1:1082) 是否开启。")
                    print("   或者在 scraper.py 中将 PROXY_SERVER 设置为 None。")
                else:
                    print(f"❌ 处理失败 [{url}]: {e}")
                
                # 批量处理时不因为单个失败而中断
                if BATCH_URLS:
                    print("🔄 跳过当前链接，继续处理下一个...")
                    continue

        print(f"\n✨ 本批次处理完成！文件保存在 {DATA_DIR.resolve()}")


if __name__ == "__main__":
    asyncio.run(main())