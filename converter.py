"""
converter.py — HTML → Markdown 转换模块
处理知乎特有的 LaTeX 公式、代码块、图片链接重写、垃圾内容清洗。
"""

import re
from pathlib import Path

from bs4 import BeautifulSoup, Tag
from markdownify import MarkdownConverter


# ── 自定义 Converter ─────────────────────────────────────────

class ZhihuConverter(MarkdownConverter):
    """继承 markdownify，覆盖知乎特殊标签的处理逻辑。"""

    def __init__(self, img_map: dict[str, str] | None = None, **kwargs):
        self.img_map = img_map or {}
        super().__init__(**kwargs)

    def convert_img(self, el: Tag, text: str, parent_tags: set) -> str:
        """图片：优先 data-actualsrc，替换为本地路径。"""
        src = (
            el.get("data-actualsrc")
            or el.get("data-original")
            or el.get("src")
            or ""
        )
        if not src:
            return ""

        # 过滤知乎表情包 / 装饰图
        if "zhihu.com/equation" not in src and any(
            kw in src for kw in ["data:image", "noavatar"]
        ):
            return ""

        alt = el.get("alt", "")
        local = self.img_map.get(src, src)
        return f"![{alt}]({local})\n\n"


# ── 预处理 HTML ──────────────────────────────────────────────

def _preprocess_html(html: str) -> str:
    """在交给 markdownify 之前做知乎特定的 HTML 清洗。"""
    soup = BeautifulSoup(html, "html.parser")

    # 1) 移除视频播放器
    for tag in soup.select("div.VideoCard, .RichText-video, .VideoCard-player"):
        tag.decompose()

    # 2) 移除知乎内嵌卡片 (想法、收藏夹、推荐等)
    for tag in soup.select(
        ".LinkCard, .RichText-LinkCard, .Card, .Reward, "
        ".ContentItem-actions, .RichContent-actions, "
        ".Post-SideActions, .BottomActions"
    ):
        tag.decompose()

    # 3) 移除点赞提醒文本
    for tag in soup.select(".css-1gomreu, .Voters"):
        tag.decompose()

    # 4) 处理数学公式 <img class="ztext-math" data-formula="...">
    for img in soup.select("img.ztext-math"):
        formula = img.get("data-formula", "")
        if formula:
            # 行内与块级公式
            if img.parent and img.parent.name == "p":
                img.replace_with(f" ${formula}$ ")
            else:
                img.replace_with(f"\n\n$${formula}$$\n\n")

    # 5) 处理知乎用 <span> 包裹的公式 (新版)
    for span in soup.select("span.ztext-math"):
        formula = span.get("data-formula", "") or span.get_text()
        if formula:
            span.replace_with(f" ${formula}$ ")

    # 6) 把 <code> 里的 <br> 换成换行符
    for code in soup.find_all("code"):
        for br in code.find_all("br"):
            br.replace_with("\n")

    # 7) 代码块：确保 highlight 容器能被正确识别
    for pre in soup.find_all("pre"):
        code = pre.find("code")
        if code:
            # 尝试提取语言
            lang = ""
            for cls in code.get("class", []):
                if cls.startswith("language-"):
                    lang = cls[len("language-"):]
                    break
            if lang:
                code["class"] = [f"language-{lang}"]

    return str(soup)


def _extract_image_urls(html: str) -> list[str]:
    """从 HTML 中抽取所有需要下载的图片 URL。"""
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []

    for img in soup.find_all("img"):
        # 跳过公式图（已转 LaTeX）
        if "ztext-math" in (img.get("class") or []):
            continue

        src = img.get("data-actualsrc") or img.get("data-original") or img.get("src") or ""
        if not src:
            continue

        # 过滤 base64 / 头像
        if src.startswith("data:") or "noavatar" in src:
            continue

        urls.append(src)

    return list(dict.fromkeys(urls))  # 去重保序


# ── Markdown 后处理 ──────────────────────────────────────────

def _postprocess_md(md: str) -> str:
    """清理 markdownify 输出中的常见噪音。"""
    # 连续空行压缩到 2 行
    md = re.sub(r"\n{3,}", "\n\n", md)

    # 清理行尾空白
    md = "\n".join(line.rstrip() for line in md.splitlines())

    # 修复行内公式前后多余空格
    md = re.sub(r"\s*\$\s+", " $", md)
    md = re.sub(r"\s+\$\s*", "$ ", md)

    return md.strip() + "\n"


# ── 对外接口 ─────────────────────────────────────────────────

def html_to_markdown(
    html: str,
    img_map: dict[str, str] | None = None,
) -> str:
    """完整的知乎 HTML → Markdown 管线。"""
    cleaned = _preprocess_html(html)
    converter = ZhihuConverter(
        img_map=img_map,
        heading_style="atx",
        bullets="-",
        strip=["script", "style", "noscript"],
    )
    md = converter.convert(cleaned)
    return _postprocess_md(md)


def get_image_urls(html: str) -> list[str]:
    """提取需要下载的图片列表。"""
    return _extract_image_urls(html)


def sanitize_filename(name: str) -> str:
    """清理文件名中 macOS 不允许的字符。"""
    # 替换 / : \ 和控制字符
    name = re.sub(r'[/\\:*?"<>|\x00-\x1f]', "_", name)
    # 去首尾空格和点
    name = name.strip(" .")
    # 限制长度
    if len(name) > 100:
        name = name[:100].rstrip(" .")
    return name or "untitled"