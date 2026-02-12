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
from datetime import datetime
from pathlib import Path

from typing import Optional
from core.converter import ZhihuConverter
from core.scraper import ZhihuDownloader

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
    pattern = r"https?://(?:www\.|zhuanlan\.)?zhihu\.com/(?:p/\d+|question/\d+(?:/answer/\d+)?)"
    return list(dict.fromkeys(re.findall(pattern, text)))

def parse_question_options(user_input: str) -> dict:
    """
    解析用户对问题抓取的选项。
    - 空或回车: 默认抓取前 3 个 (稳定)
    - 数字 N: 抓取前 N 个 (自定义)
    """
    user_input = user_input.lower().strip()
    
    # -------------------------------------------------------------
    # 模式 A: 游客模式 (无 Cookie) -> 强制默认 Top 3
    # -------------------------------------------------------------
    if not ZhihuDownloader(url="").has_valid_cookies():
        return {"start": 0, "limit": 3}

    # -------------------------------------------------------------
    # 模式 B: 登录模式 (有 Cookie) -> 显示子菜单
    # -------------------------------------------------------------
    print("\n   [1] 按数量: 抓取前 N 个回答")
    print("   [2] 按范围: 指定起止答主/链接 (闭区间)")
    print("👉 请输入 (1/2): ", end="", flush=True)
    
    mode_choice = sys.stdin.readline().strip()
    
    # --- 模式 2.1: 按数量 ---
    if mode_choice == "1":
        print("👉 请输入要抓取的数量: ", end="", flush=True)
        try:
            limit = int(sys.stdin.readline().strip())
            return {"start": 0, "limit": limit}
        except:
            print("⚠️输入无效，使用默认值 20")
            return {"start": 0, "limit": 20}
            
    # --- 模式 2.2: 按范围 ---
    elif mode_choice == "2":
        print("👉 请输入起始 (答主名字或回答链接): ", end="", flush=True)
        start_input = sys.stdin.readline().strip()
        print("👉 请输入结束 (答主名字或回答链接): ", end="", flush=True)
        end_input = sys.stdin.readline().strip()
        
        start_anchor = _parse_anchor(start_input)
        end_anchor = _parse_anchor(end_input)
        
        if not start_anchor or not end_anchor:
            print("⚠️ 输入无效，回退到默认 Top 3")
            return {"start": 0, "limit": 3}
            
        return {
            "start": 0, 
            "limit": 3, # 占位
            "start_anchor": start_anchor,
            "end_anchor": end_anchor
        }
    
    # --- 默认 fallback ---
    else:
        # 兼容旧习惯：如果直接输数字，当做模式 2.1
        try:
            limit = int(mode_choice)
            print(f"💡 识别为抓取前 {limit} 个")
            return {"start": 0, "limit": limit}
        except:
            print("⚠️ 选项无效，使用默认 Top 3")
            return {"start": 0, "limit": 3}

def _parse_anchor(val: str) -> Optional[dict]:
    """解析锚点输入: 链接 -> answer_id, 名字 -> author"""
    if not val: return None
    
    # 尝试提取 answer id
    # https://www.zhihu.com/question/xxx/answer/12345
    m = re.search(r"answer/(\d+)", val)
    if m:
        return {"type": "answer_id", "value": m.group(1)}
    
    # 纯数字也当做 answer id? 不，名字可能是纯数字。
    # 默认当做名字
    return {"type": "author", "value": val}


# ── 流水线 ───────────────────────────────────────────────────

class Pipeline:
    """单篇文章的处理流水线：抓取 → 下载图片 → 转换 → 保存。"""

    def __init__(self, url: str, output_dir: Path = DATA_DIR, scrape_config: Optional[dict] = None):
        self.url = url
        self.output_dir = output_dir
        self.scrape_config = scrape_config or {}

    async def run(self) -> None:
        """执行完整流程，支持单个或多个结果。"""
        downloader = ZhihuDownloader(self.url)
        # 传递配置给 fetch_page
        data = await downloader.fetch_page(**self.scrape_config)

        if isinstance(data, list):
            print(f"📦 抓取到 {len(data)} 个内容，开始处理...")
            for i, item in enumerate(data):
                print(f"  > ({i+1}/{len(data)}) 处理: {item.get('author', 'Unknown')}")
                await self._process_one(item, downloader.page_type)
        else:
            await self._process_one(data, downloader.page_type)

    async def _process_one(self, info: dict, page_type: str) -> Path:
        title = info["title"]
        author = info["author"]
        date = info["date"]
        html = info["html"]

        today = datetime.now().strftime("%Y-%m-%d")
        safe_title = sanitize_filename(title)
        safe_author = sanitize_filename(author)

        if page_type == "question":
            # data/[Date] QuestionTitle / Author.md
            folder_name = sanitize_filename(f"[{today}] {title}")
            file_name = f"{safe_author}.md"
        else:
            # data/[Date] Title - Author / index.md
            folder_name = sanitize_filename(f"[{date}] {title} - {author}")
            file_name = "index.md"

        folder = self.output_dir / folder_name
        img_dir = folder / "images"
        folder.mkdir(parents=True, exist_ok=True)

        # 3. 提取图片 URL 并下载
        img_urls = ZhihuConverter.extract_image_urls(html)
        if img_urls:
            print(f"🖼️  发现 {len(img_urls)} 张图片，正在下载...")
            img_map = await ZhihuDownloader.download_images(img_urls, img_dir)
            print(f"✅ 成功下载 {len(img_map)} 张图片")
        else:
            img_map = {}

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

        (folder / file_name).write_text(header + md, encoding="utf-8")
        print(f"💾 已保存至: {folder / file_name}")

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
    print("  - 完整问题: https://www.zhihu.com/question/xxx")
    print("\n💡 提示: 默认抓取 3 条最稳定。如需大量抓取，请在 cookies.json 中填入 z_c0")
    print("输入 q 退出\n")

    should_prompt = True
    while True:
        # ── 获取待处理链接 ──
        if BATCH_URLS:
            print(f"📋 检测到 BATCH_URLS 中有 {len(BATCH_URLS)} 个链接，开始自动处理...")
            target_urls = list(BATCH_URLS)
            BATCH_URLS.clear()
            should_prompt = True
        else:
            try:
                if should_prompt:
                    print("\n🔗 请粘贴知乎链接 (可包含其它文字): ", end="", flush=True)
                    should_prompt = False

                user_input = sys.stdin.readline().strip()
            except (EOFError, KeyboardInterrupt):
                print("\n👋 再见!")
                break

            if user_input.lower() == "q":
                print("👋 再见!")
                break

            target_urls = extract_urls(user_input)

        if not target_urls:
            # 只有当用户输入为空时才提示，避免因为复制了标题行导致报错刷屏
            if not user_input:
                 should_prompt = True
            continue

        # ── 逐个处理 ──
        print(f"🔍 检测到 {len(target_urls)} 个链接")

        for url in target_urls:
            print(f"\n{'='*60}")
            
            # 检测是否为问题链接，如果是，询问抓取范围
            scrape_config = {}
            if "/question/" in url and "/answer/" not in url:
                try:
                    print(f"⚙️  检测到问题链接: {url}")
                    print(f"⚙️  检测到问题链接: {url}")
                    
                    is_login = ZhihuDownloader(url).has_valid_cookies()
                    status = "✅ 已登录 (解锁全部功能)" if is_login else "❌ 游客模式 (仅限前 3 条)"
                    print(f"   🍪 Cookie 状态: {status}")
                    
                    if not is_login:
                        print("   (按 Enter 继续抓取前 3 条)")
                        sys.stdin.readline()
                        scrape_config = {"start": 0, "limit": 3}
                    else:
                        scrape_config = parse_question_options("") # 传入空串触发内部交互
                        
                    if "start_anchor" in scrape_config:
                        s = scrape_config['start_anchor']['value']
                        e = scrape_config['end_anchor']['value']
                        print(f"✅ 已设定: 抓取范围 {s} -> {e}")
                    else:
                        print(f"✅ 已设定: 抓取前 {scrape_config['limit']} 个回答")
                except (KeyboardInterrupt, EOFError):
                    print("\n🛑 取消操作")
                    continue

            print(f"📥 正在抓取: {url}")
            try:
                await Pipeline(url, scrape_config=scrape_config).run()
            except Exception as e:
                err_msg = str(e)
                if "ERR_PROXY_CONNECTION_FAILED" in err_msg or "Connection refused" in err_msg:
                    print(f"\n❌ 代理连接失败: {e}")
                    print("💡 提示: 请检查本地代理是否开启，或在 scraper.py 中将 PROXY_SERVER 设为 None。")
                else:
                    print(f"❌ 处理失败 [{url}]: {e}")
                print("🔄 跳过当前链接，继续处理下一个...")

        print(f"\n✨ 本批次处理完成！文件保存在 {DATA_DIR.resolve()}")
        should_prompt = True


if __name__ == "__main__":
    asyncio.run(main())