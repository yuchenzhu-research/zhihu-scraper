"""
main.py — 知乎离线化工具入口

免责声明：
本项目代码仅用于学习研究，严禁用于任何商业目的。
请在合法合规的前提下使用，开发者不承担任何由使用此工具引起的法律风险。
职责：用户交互、文件系统操作、流水线串联。
"""

import asyncio
import re
import sys
from pathlib import Path

from converter import ZhihuConverter
from scraper import ZhihuDownloader

# ==========================================
# 批量下载列表 (不想用命令行输入时，在这里填入链接)
# 格式: ["https://...", "https://..."]
# ==========================================
BATCH_URLS = [
    # "https://zhuanlan.zhihu.com/p/xxxxx",
    # "https://www.zhihu.com/question/xxx/answer/xxx",
]

DATA_DIR = Path(__file__).parent / "data"


# ── 工具函数 ─────────────────────────────────────────────────

def sanitize_filename(name: str) -> str:
    """清理文件名中 macOS / Windows 不允许的字符。"""
    name = re.sub(r'[/\\:*?"<>|\x00-\x1f]', "_", name)
    name = name.strip(" .")
    if len(name) > 100:
        name = name[:100].rstrip(" .")
    return name or "untitled"


def extract_urls(text: str) -> list[str]:
    """从任意文本中提取知乎链接。"""
    pattern = r"https?://(?:www\.|zhuanlan\.)?zhihu\.com/(?:p/\d+|question/\d+/answer/\d+)"
    return list(dict.fromkeys(re.findall(pattern, text)))


# ── 流水线 ───────────────────────────────────────────────────

class Pipeline:
    """单篇文章的处理流水线：抓取 → 下载图片 → 转换 → 保存。"""

    def __init__(self, url: str, output_dir: Path = DATA_DIR):
        self.url = url
        self.output_dir = output_dir

    async def run(self) -> Path:
        """执行完整流程，返回输出目录路径。"""
        # 1. 抓取页面
        info = await ZhihuDownloader(self.url).fetch_page()
        title = info["title"]
        author = info["author"]
        date = info["date"]
        html = info["html"]

        print(f"📄 标题: {title}")
        print(f"✍️  作者: {author}")

        # 2. 准备输出目录
        folder_name = sanitize_filename(f"[{date}] {title} - {author}")
        folder = self.output_dir / folder_name
        img_dir = folder / "images"
        folder.mkdir(parents=True, exist_ok=True)

        # 3. 提取图片 URL 并下载
        img_urls = ZhihuConverter.extract_image_urls(html)
        print(f"🖼️  发现 {len(img_urls)} 张图片，正在下载...")
        img_map = await ZhihuDownloader.download_images(img_urls, img_dir)
        print(f"✅ 成功下载 {len(img_map)} 张图片")

        # 4. HTML → Markdown
        converter = ZhihuConverter(img_map=img_map)
        md = converter.convert(html)

        # 5. 拼接元信息头 + 保存
        header = (
            f"# {title}\n\n"
            f"> **作者**: {author}  \n"
            f"> **来源**: [{self.url}]({self.url})  \n"
            f"> **日期**: {date}\n\n"
            f"---\n\n"
        )
        (folder / "index.md").write_text(header + md, encoding="utf-8")
        print(f"💾 已保存至: {folder}")

        # 清理空图片目录
        if img_dir.exists() and not any(img_dir.iterdir()):
            img_dir.rmdir()

        return folder


# ── 主循环 ───────────────────────────────────────────────────

async def main() -> None:
    """持续接收用户输入，逐个处理链接。"""
    print("=" * 60)
    print("📚 知乎离线化工具")
    print("=" * 60)
    print("支持链接类型:")
    print("  - 专栏文章: https://zhuanlan.zhihu.com/p/xxxxxxx")
    print("  - 问题回答: https://www.zhihu.com/question/xxx/answer/xxx")
    print("输入 q 退出\n")

    while True:
        # ── 获取待处理链接 ──
        if BATCH_URLS:
            print(f"📋 检测到 BATCH_URLS 中有 {len(BATCH_URLS)} 个链接，开始自动处理...")
            target_urls = list(BATCH_URLS)
            BATCH_URLS.clear()
        else:
            try:
                print("\n🔗 请粘贴知乎链接 (可包含其它文字): ", end="", flush=True)
                user_input = sys.stdin.readline().strip()
            except (EOFError, KeyboardInterrupt):
                print("\n👋 再见!")
                break

            if user_input.lower() == "q":
                print("👋 再见!")
                break

            target_urls = extract_urls(user_input)

        if not target_urls:
            print("⚠️ 未检测到有效链接，请重新输入")
            continue

        # ── 逐个处理 ──
        print(f"🔍 检测到 {len(target_urls)} 个链接")

        for url in target_urls:
            print(f"\n{'='*60}")
            print(f"📥 正在抓取: {url}")
            try:
                await Pipeline(url).run()
            except Exception as e:
                err_msg = str(e)
                if "ERR_PROXY_CONNECTION_FAILED" in err_msg or "Connection refused" in err_msg:
                    print(f"\n❌ 代理连接失败: {e}")
                    print("💡 提示: 请检查本地代理是否开启，或在 scraper.py 中将 PROXY_SERVER 设为 None。")
                else:
                    print(f"❌ 处理失败 [{url}]: {e}")
                print("🔄 跳过当前链接，继续处理下一个...")

        print(f"\n✨ 本批次处理完成！文件保存在 {DATA_DIR.resolve()}")


if __name__ == "__main__":
    asyncio.run(main())