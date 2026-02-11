"""
converter.py — HTML → Markdown 转换模块
处理知乎特有的 LaTeX 公式、代码块、图片链接重写、垃圾内容清洗。

核心策略：在 BeautifulSoup 阶段用占位符保护公式，
         markdownify 转换后再还原为 $ / $$ 定界符。
"""

import re
import uuid
from pathlib import Path

from bs4 import BeautifulSoup, Tag
from markdownify import MarkdownConverter

# 占位符前缀（纯字母数字，不含下划线，避免被 markdownify 转义）
_PID = uuid.uuid4().hex[:8]
_INLINE_PH = f"IMATH{_PID}X"
_BLOCK_PH = f"BMATH{_PID}X"

# 全局公式仓库：由 _preprocess_html 填充，由 _postprocess_md 消费
_math_store: dict[str, str] = {}
_math_counter = 0


def _store_math(formula: str, is_block: bool) -> str:
    """将公式存入仓库，返回占位符。"""
    global _math_counter
    prefix = _BLOCK_PH if is_block else _INLINE_PH
    key = f"{prefix}{_math_counter}E"
    _math_store[key] = formula
    _math_counter += 1
    return key


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
    global _math_counter
    _math_store.clear()
    _math_counter = 0

    soup = BeautifulSoup(html, "html.parser")

    # 1) 移除视频播放器
    for tag in soup.select("div.VideoCard, .RichText-video, .VideoCard-player"):
        tag.decompose()

    # 2) 移除知乎内嵌卡片
    for tag in soup.select(
        ".LinkCard, .RichText-LinkCard, .Card, .Reward, "
        ".ContentItem-actions, .RichContent-actions, "
        ".Post-SideActions, .BottomActions"
    ):
        tag.decompose()

    # 3) 移除点赞提醒文本
    for tag in soup.select(".css-1gomreu, .Voters"):
        tag.decompose()

    # ── 核心：处理数学公式 ──────────────────────────────────
    #
    # 知乎渲染公式的方式 (2024+):
    #   <span class="ztext-math" data-eeimg="1" data-tex="\alpha">
    #     <span class="ztext-math-scrollable">...</span>  (MathJax 渲染)
    #     <span class="ztext-math-fallback">...</span>    (纯文本 fallback)
    #   </span>
    #
    # 块级公式的 data-tex 以 \[ 开头，以 \] 结尾。
    # 行内公式的 data-tex 不包含 \[ \]。

    for span in soup.find_all("span", class_="ztext-math"):
        tex = span.get("data-tex", "")
        if not tex:
            continue

        # 判断块级 vs 行内
        is_block = tex.startswith(r"\[") and tex.endswith(r"\]")
        if is_block:
            # 去掉 \[ \] 包裹，我们会用 $$ 替代
            tex = tex[2:-2].strip()

        placeholder = _store_math(tex, is_block)

        # 用 <var> 标签包裹占位符，防止 markdownify 转义其中的字符
        marker = soup.new_tag("var")
        marker.string = placeholder
        span.replace_with(marker)

    # 兼容旧版: <img class="ztext-math" data-formula="...">
    for img in soup.select("img.ztext-math"):
        formula = img.get("data-formula", "")
        if not formula:
            continue
        is_block = (
            img.parent
            and img.parent.name in ("p", "div", "figure")
            and len(img.parent.get_text(strip=True)) == 0
        )
        placeholder = _store_math(formula, is_block)
        marker = soup.new_tag("var")
        marker.string = placeholder
        img.replace_with(marker)

    # 5) 把 <code> 里的 <br> 换成换行符
    for code in soup.find_all("code"):
        for br in code.find_all("br"):
            br.replace_with("\n")

    # 6) 代码块：确保 highlight 容器能被正确识别
    for pre in soup.find_all("pre"):
        code = pre.find("code")
        if code:
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
    """清理 markdownify 输出中的常见噪音，并还原公式占位符。"""
    # 连续空行压缩到 2 行
    md = re.sub(r"\n{3,}", "\n\n", md)

    # 清理行尾空白
    md = "\n".join(line.rstrip() for line in md.splitlines())

    # ── 核心：还原公式占位符 ──
    for key, formula in _math_store.items():
        if key.startswith(_BLOCK_PH):
            md = md.replace(key, f"\n\n$$\n{formula}\n$$\n\n")
        elif key.startswith(_INLINE_PH):
            md = md.replace(key, f"${formula}$")

    # 再次压缩多余空行
    md = re.sub(r"\n{3,}", "\n\n", md)

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
    name = re.sub(r'[/\\:*?"<>|\x00-\x1f]', "_", name)
    name = name.strip(" .")
    if len(name) > 100:
        name = name[:100].rstrip(" .")
    return name or "untitled"