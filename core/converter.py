"""
converter.py - HTML to Markdown Conversion Module

Handles Zhihu-specific LaTeX formulas, code blocks, image link rewriting, and content cleaning.

Core strategy: Use placeholders to protect formulas during BeautifulSoup preprocessing,
              then restore them as $ / $$ delimiters after markdownify conversion.

================================================================================
converter.py — HTML → Markdown 转换模块

处理知乎特有的 LaTeX 公式、代码块、图片链接重写、垃圾内容清洗。

核心策略：在 BeautifulSoup 阶段用占位符保护公式，
         markdownify 转换后再还原为 $ / $$ 定界符。
================================================================================
"""

import re
import uuid

from urllib.parse import urljoin, urlparse, parse_qs
from typing import Optional, Dict
from bs4 import BeautifulSoup, Tag
from markdownify import MarkdownConverter


class ZhihuConverter:
    """
    Chinese: 知乎 HTML → Markdown 转换器
    English: Zhihu HTML to Markdown converter

    Each instance has an isolated formula store, no global state pollution.

    Usage:
        converter = ZhihuConverter(img_map={"https://...": "images/abc.jpg"})
        markdown  = converter.convert(html_string)
        img_urls  = ZhihuConverter.extract_image_urls(html_string)
    """

    # Placeholder prefix (alphanumeric only to avoid markdownify escaping)
    # 占位符前缀（纯字母数字，避免被 markdownify 转义）
    _PID = uuid.uuid4().hex[:8]
    _INLINE_PH = f"IMATH{_PID}X"
    _BLOCK_PH = f"BMATH{_PID}X"

    def __init__(self, img_map: Optional[Dict[str, str]] = None):
        self._img_map = img_map or {}
        self._math_store: dict[str, dict[str, object]] = {}
        self._math_counter = 0

    # ── Formula Store (公式仓库) ─────────────────────────────────────────────

    def _store_math(self, formula: str, is_block: bool, *, in_quote: bool = False) -> str:
        """
        Store formula in instance warehouse and return placeholder
        将公式存入实例仓库，返回占位符
        """
        prefix = self._BLOCK_PH if is_block else self._INLINE_PH
        key = f"{prefix}{self._math_counter}E"
        self._math_store[key] = {
            "formula": formula,
            "is_block": is_block,
            "in_quote": in_quote,
        }
        self._math_counter += 1
        return key

    # ── Public Interface (对外接口) ─────────────────────────────────────────────

    def convert(self, html: str) -> str:
        """
        One-step: HTML → Clean Markdown
        一步到位：HTML → 清洁 Markdown
        """
        cleaned = self._preprocess(html)
        md = self._to_markdown(cleaned)
        return self._postprocess(md)

    @staticmethod
    def extract_image_urls(html: str) -> list[str]:
        """
        Extract all image URLs from HTML (excluding formula images and duplicate sizes)
        从 HTML 中抽取所有需要下载的图片 URL（不含公式图片、不含重复尺寸）
        """
        soup = BeautifulSoup(html, "html.parser")
        urls: list[str] = []
        seen_base: set[str] = set()  # For deduplicating similar theme images / 用于去重同主题图片

        for img in soup.find_all("img"):
            if ZhihuConverter._extract_formula_from_img(img):
                continue
            src = (
                img.get("data-actualsrc")
                or img.get("data-original")
                or img.get("src")
                or ""
            )
            if not src or src.startswith("data:") or "noavatar" in src:
                continue

            # Extract base name for deduplication: v2-xxx_720w.jpg → v2-xxx
            # 提取基础名用于去重：v2-xxx_720w.jpg → v2-xxx
            # Zhihu image naming rules: v2-xxx_720w.jpg, v2-xxx_r.jpg
            # 知乎图片命名规则：v2-xxx_720w.jpg, v2-xxx_r.jpg
            base_name = src.split("/")[-1].split("?")[0]
            for suffix in ["_720w", "_r", "_l"]:
                if base_name.endswith(suffix + ".jpg"):
                    base_name = base_name.replace(suffix + ".jpg", ".jpg")
                    break
                if base_name.endswith(suffix + ".png"):
                    base_name = base_name.replace(suffix + ".png", ".png")
                    break

            # Skip if already seen similar theme image
            # 如果已经见过同主题图片，跳过
            if base_name in seen_base:
                continue
            seen_base.add(base_name)
            urls.append(src)

        return urls

    # ── HTML Preprocessing (预处理 HTML) ──────────────────────────────────────────

    def _preprocess(self, html: str) -> str:
        """
        Perform Zhihu-specific HTML cleaning before passing to markdownify
        在交给 markdownify 之前做知乎特定的 HTML 清洗
        """
        soup = BeautifulSoup(html, "html.parser")

        # 0) Remove style/script-like nodes completely before markdownify.
        # markdownify 的 strip 只会去标签，不会自动丢弃 style 里的 CSS 文本，
        # 所以这里必须先彻底删除整棵节点。
        for tag in soup.find_all(["style", "script", "noscript"]):
            tag.decompose()
        for link in soup.find_all("link"):
            rel = [item.lower() for item in (link.get("rel") or []) if isinstance(item, str)]
            if "stylesheet" in rel:
                link.decompose()

        # 0.5) Convert Zhihu link cards into plain anchors before removing cards.
        # 先把知乎链接卡片提炼成普通链接，否则后续清洗会把整块卡片删掉。
        for card in list(soup.select(".LinkCard, .RichText-LinkCard, .FileLinkCard")):
            replacement = self._extract_link_card(soup, card)
            if replacement is not None:
                card.replace_with(replacement)

        # 1) Remove interference elements: videos / cards / buttons / etc.
        # 移除视频 / 卡片 / 按钮等干扰元素
        for selector in (
            "div.VideoCard, .RichText-video, .VideoCard-player",
            ".LinkCard, .RichText-LinkCard, .Card, .Reward",
            ".ContentItem-actions, .RichContent-actions",
            ".Post-SideActions, .BottomActions",
            ".css-1gomreu, .Voters",
            "noscript",
        ):
            for tag in soup.select(selector):
                tag.decompose()

        # 2) Process math formulas
        # 处理数学公式
        #    Zhihu 2024+ format: <span class="ztext-math" data-tex="...">
        #    Block formula's data-tex starts with \[ and ends with \]
        #    知乎 2024+ 格式: <span class="ztext-math" data-tex="...">
        #    块级公式的 data-tex 以 \[ 开头、\] 结尾
        for span in soup.find_all("span", class_="ztext-math"):
            tex = span.get("data-tex", "")
            if not tex:
                continue
            is_block = self._is_block_formula(span, tex)
            tex = self._normalize_formula(tex, is_block)
            placeholder = self._store_math(
                tex,
                is_block,
                in_quote=span.find_parent("blockquote") is not None,
            )
            marker = soup.new_tag("var")
            marker.string = placeholder
            span.replace_with(marker)

        #    Legacy format and equation-image fallback:
        #    - <img class="ztext-math" data-formula="...">
        #    - <img src="https://www.zhihu.com/equation?tex=...">
        #    兼容旧版与 equation 图片格式:
        #    - <img class="ztext-math" data-formula="...">
        #    - <img src="https://www.zhihu.com/equation?tex=...">
        for img in list(soup.find_all("img")):
            formula = self._extract_formula_from_img(img)
            if not formula:
                continue
            is_block = self._is_block_formula(img, formula) or (
                img.parent
                and img.parent.name in ("p", "div", "figure")
                and len(img.parent.get_text(strip=True)) == 0
            )
            formula = self._normalize_formula(formula, is_block)
            placeholder = self._store_math(
                formula,
                is_block,
                in_quote=img.find_parent("blockquote") is not None,
            )
            marker = soup.new_tag("var")
            marker.string = placeholder
            img.replace_with(marker)

        # 3) Replace <br> in <code> with newlines
        # <code> 里的 <br> 换成换行符
        for code in soup.find_all("code"):
            for br in code.find_all("br"):
                br.replace_with("\n")

        # 4) Code block language labels
        # 代码块语言标注
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

    @staticmethod
    def _extract_formula_from_img(img: Tag) -> str:
        """
        Extract formula text from Zhihu formula images.
        从知乎公式图片中提取公式文本。
        """
        if not img or img.name != "img":
            return ""

        css_classes = img.get("class") or []
        if "ztext-math" in css_classes:
            return (
                img.get("data-formula")
                or img.get("data-tex")
                or img.get("alt")
                or ""
            ).strip()

        for candidate in (
            img.get("data-actualsrc"),
            img.get("data-original"),
            img.get("src"),
        ):
            if not candidate or "zhihu.com/equation" not in candidate:
                continue
            parsed = urlparse(candidate)
            tex_values = parse_qs(parsed.query).get("tex") or []
            if tex_values:
                return tex_values[0].strip()
            alt = (img.get("alt") or "").strip()
            if alt:
                return alt

        return ""

    def _extract_link_card(self, soup: BeautifulSoup, card: Tag) -> Optional[Tag]:
        """
        Convert a Zhihu rich link card into a simple paragraph anchor.
        将知乎富链接卡片转换成一个简单的段落链接。
        """
        href = ""
        anchor = card if card.name == "a" and card.get("href") else card.find("a", href=True)
        if anchor and anchor.get("href"):
            href = anchor.get("href", "").strip()
        if not href:
            raw_text = card.get_text(" ", strip=True)
            match = re.search(r"https?://[^\s]+|www\.[^\s]+", raw_text)
            if match:
                href = match.group(0).strip()

        if not href:
            return None

        if href.startswith("//"):
            href = f"https:{href}"
        elif href.startswith("/"):
            href = urljoin("https://www.zhihu.com", href)
        elif href.startswith("www."):
            href = f"https://{href}"

        title = ""
        for selector in (".LinkCard-title", ".FileLinkCard-name", ".ZhidaLinkCard-footer-text"):
            node = card.select_one(selector)
            if node:
                title = node.get_text(" ", strip=True)
                if title:
                    break

        if not title:
            title = anchor.get_text(" ", strip=True) if anchor else ""
        if not title:
            title = href

        paragraph = soup.new_tag("p")
        link = soup.new_tag("a", href=href)
        link.string = title
        paragraph.append(link)
        return paragraph

    # ── markdownify Bridge (markdownify 桥接) ─────────────────────────────────────

    def _to_markdown(self, html: str) -> str:
        """
        Call markdownify with custom image handling logic
        调用 markdownify，使用自定义的图片处理逻辑
        """
        md_converter = _MarkdownBridge(
            img_map=self._img_map,
            heading_style="atx",
            bullets="-",
            strip=["script", "style", "noscript"],
        )
        return md_converter.convert(html)

    # ── Markdown Post-processing (后处理 Markdown) ──────────────────────────────────────

    def _postprocess(self, md: str) -> str:
        """
        Clean noise + restore formula placeholders
        清理噪音 + 还原公式占位符
        """
        # Compress consecutive blank lines
        # 压缩连续空行
        md = re.sub(r"\n{3,}", "\n\n", md)
        # Clean trailing whitespace
        # 清理行尾空白
        md = "\n".join(line.rstrip() for line in md.splitlines())

        # Restore formulas (with KaTeX compatibility fix)
        # 还原公式 (并做 KaTeX 兼容性处理)
        for key, meta in self._math_store.items():
            formula = str(meta["formula"])
            fixed_formula = self._fix_katex_array(formula)
            if bool(meta["is_block"]):
                if bool(meta["in_quote"]):
                    replacement = (
                        "\n> $$\n"
                        f"> {fixed_formula}\n"
                        "> $$\n"
                        "> "
                    )
                else:
                    replacement = f"\n\n$$\n{fixed_formula}\n$$\n\n"
                md = md.replace(key, replacement)
            else:
                md = md.replace(key, f"${fixed_formula}$")

        # Compress again
        # 再次压缩
        md = re.sub(r"\n{3,}", "\n\n", md)
        return md.strip() + "\n"

    @staticmethod
    def _fix_katex_array(formula: str) -> str:
        """
        Fix KaTeX unsupported array column definition syntax.
        GitHub's KaTeX doesn't recognize {*{N}{X}} repeat syntax, needs expansion.
        Example: {*{20}{c}} → {cccccccccccccccccccc}

        修复 KaTeX 不支持的 array 列定义语法。
        GitHub 的 KaTeX 不识别 {*{N}{X}} 这种重复语法，需要展开。
        例如: {*{20}{c}} → {cccccccccccccccccccc}
        """
        def expand_repeat(match):
            count = int(match.group(1))
            char = match.group(2)
            return char * count

        # Match *{digit}{single_char} and expand
        # 匹配 *{数字}{单字符} 并展开
        return re.sub(r'\*\{(\d+)\}\{(.)\}', expand_repeat, formula)

    @staticmethod
    def _is_block_formula(node: Tag, formula: str) -> bool:
        """
        Detect display-style formulas in Zhihu HTML.
        知乎有些块级公式不会包在 \\[ ... \\] 里，而是直接给 data-tex。
        这里补一层启发式判断，避免整段块公式被误判成行内公式。
        """
        tex = formula.strip()
        if tex.startswith(r"\[") and tex.endswith(r"\]"):
            return True
        if re.search(r"\\begin\{[a-zA-Z*]+\}", tex):
            return True
        if tex.endswith(r"\\"):
            return True
        parent = node.parent if node else None
        if node and node.name == "img" and str(node.get("eeimg", "")).strip() == "2":
            return True
        if parent and parent.name in ("p", "div", "figure"):
            text = parent.get_text(" ", strip=True)
            if text == node.get_text(" ", strip=True):
                return True
        return False

    @staticmethod
    def _normalize_formula(formula: str, is_block: bool) -> str:
        """
        Normalize formula text before restoring into Markdown.
        对恢复前的公式文本做清洗，避免把知乎富文本里的尾部换行标记原样写进 Markdown。
        """
        tex = formula.strip()
        if tex.startswith(r"\[") and tex.endswith(r"\]"):
            tex = tex[2:-2].strip()
        if is_block:
            tex = re.sub(r"(?:\\\\)+\s*$", "", tex)
        return tex


# ── markdownify Internal Bridge Class (不对外暴露) ──────────────────────

class _MarkdownBridge(MarkdownConverter):
    """
    Inherit markdownify, only override image tag conversion logic
    继承 markdownify，仅覆盖图片标签的转换逻辑
    """

    def __init__(self, img_map: Optional[Dict[str, str]] = None, **kwargs):
        self.img_map = img_map or {}
        self._img_map_by_base = {
            self._normalize_image_basename(url): local
            for url, local in self.img_map.items()
            if self._normalize_image_basename(url)
        }
        super().__init__(**kwargs)

    def convert_img(self, el: Tag, text: str, parent_tags: set) -> str:
        candidates = []
        for candidate in (
            el.get("data-actualsrc"),
            el.get("data-original"),
            el.get("src"),
        ):
            if candidate and candidate not in candidates:
                candidates.append(candidate)

        src = candidates[0] if candidates else ""
        if not src:
            return ""
        if "zhihu.com/equation" not in src and any(
            kw in src for kw in ["data:image", "noavatar"]
        ):
            return ""
        alt = el.get("alt", "")
        local = ""
        for candidate in candidates:
            local = self.img_map.get(candidate, "")
            if local:
                break
            base_name = self._normalize_image_basename(candidate)
            if base_name:
                local = self._img_map_by_base.get(base_name, "")
                if local:
                    break
        if not local:
            local = src
        return f"![{alt}]({local})\n\n"

    @staticmethod
    def _normalize_image_basename(url: str) -> str:
        if not url:
            return ""
        base_name = url.split("/")[-1].split("?")[0]
        for suffix in ["_720w", "_r", "_l"]:
            if base_name.endswith(suffix + ".jpg"):
                return base_name.replace(suffix + ".jpg", ".jpg")
            if base_name.endswith(suffix + ".png"):
                return base_name.replace(suffix + ".png", ".png")
        return base_name
