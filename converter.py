"""
converter.py — HTML → Markdown 转换模块
处理知乎特有的 LaTeX 公式、代码块、图片链接重写、垃圾内容清洗。

核心策略：在 BeautifulSoup 阶段用占位符保护公式，
         markdownify 转换后再还原为 $ / $$ 定界符。
"""

import re
import uuid

from bs4 import BeautifulSoup, Tag
from markdownify import MarkdownConverter


class ZhihuConverter:
    """
    知乎 HTML → Markdown 转换器。

    每次实例化都拥有独立的公式仓库，不存在全局状态污染。

    用法::

        converter = ZhihuConverter(img_map={"https://...": "images/abc.jpg"})
        markdown  = converter.convert(html_string)
        img_urls  = ZhihuConverter.extract_image_urls(html_string)
    """

    # 占位符前缀（纯字母数字，避免被 markdownify 转义）
    _PID = uuid.uuid4().hex[:8]
    _INLINE_PH = f"IMATH{_PID}X"
    _BLOCK_PH = f"BMATH{_PID}X"

    def __init__(self, img_map: dict[str, str] | None = None):
        self._img_map = img_map or {}
        self._math_store: dict[str, str] = {}
        self._math_counter = 0

    # ── 公式仓库 ─────────────────────────────────────────────

    def _store_math(self, formula: str, is_block: bool) -> str:
        """将公式存入实例仓库，返回占位符。"""
        prefix = self._BLOCK_PH if is_block else self._INLINE_PH
        key = f"{prefix}{self._math_counter}E"
        self._math_store[key] = formula
        self._math_counter += 1
        return key

    # ── 对外接口 ─────────────────────────────────────────────

    def convert(self, html: str) -> str:
        """一步到位：HTML → 清洁 Markdown。"""
        cleaned = self._preprocess(html)
        md = self._to_markdown(cleaned)
        return self._postprocess(md)

    @staticmethod
    def extract_image_urls(html: str) -> list[str]:
        """从 HTML 中抽取所有需要下载的图片 URL（不含公式图片）。"""
        soup = BeautifulSoup(html, "html.parser")
        urls: list[str] = []

        for img in soup.find_all("img"):
            if "ztext-math" in (img.get("class") or []):
                continue
            src = (
                img.get("data-actualsrc")
                or img.get("data-original")
                or img.get("src")
                or ""
            )
            if not src or src.startswith("data:") or "noavatar" in src:
                continue
            urls.append(src)

        return list(dict.fromkeys(urls))  # 去重保序

    # ── 预处理 HTML ──────────────────────────────────────────

    def _preprocess(self, html: str) -> str:
        """在交给 markdownify 之前做知乎特定的 HTML 清洗。"""
        soup = BeautifulSoup(html, "html.parser")

        # 1) 移除视频 / 卡片 / 按钮等干扰元素
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

        # 2) 处理数学公式
        #    知乎 2024+ 格式: <span class="ztext-math" data-tex="...">
        #    块级公式的 data-tex 以 \[ 开头、\] 结尾
        for span in soup.find_all("span", class_="ztext-math"):
            tex = span.get("data-tex", "")
            if not tex:
                continue
            is_block = tex.startswith(r"\[") and tex.endswith(r"\]")
            if is_block:
                tex = tex[2:-2].strip()
            placeholder = self._store_math(tex, is_block)
            marker = soup.new_tag("var")
            marker.string = placeholder
            span.replace_with(marker)

        #    兼容旧版: <img class="ztext-math" data-formula="...">
        for img in soup.select("img.ztext-math"):
            formula = img.get("data-formula", "")
            if not formula:
                continue
            is_block = (
                img.parent
                and img.parent.name in ("p", "div", "figure")
                and len(img.parent.get_text(strip=True)) == 0
            )
            placeholder = self._store_math(formula, is_block)
            marker = soup.new_tag("var")
            marker.string = placeholder
            img.replace_with(marker)

        # 3) <code> 里的 <br> 换成换行符
        for code in soup.find_all("code"):
            for br in code.find_all("br"):
                br.replace_with("\n")

        # 4) 代码块语言标注
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

    # ── markdownify 桥接 ─────────────────────────────────────

    def _to_markdown(self, html: str) -> str:
        """调用 markdownify，使用自定义的图片处理逻辑。"""
        md_converter = _MarkdownBridge(
            img_map=self._img_map,
            heading_style="atx",
            bullets="-",
            strip=["script", "style", "noscript"],
        )
        return md_converter.convert(html)

    # ── 后处理 Markdown ──────────────────────────────────────

    def _postprocess(self, md: str) -> str:
        """清理噪音 + 还原公式占位符。"""
        # 压缩连续空行
        md = re.sub(r"\n{3,}", "\n\n", md)
        # 清理行尾空白
        md = "\n".join(line.rstrip() for line in md.splitlines())

        # 还原公式 (并做 KaTeX 兼容性处理)
        for key, formula in self._math_store.items():
            fixed_formula = self._fix_katex_array(formula)
            if key.startswith(self._BLOCK_PH):
                md = md.replace(key, f"\n\n$$\n{fixed_formula}\n$$\n\n")
            elif key.startswith(self._INLINE_PH):
                md = md.replace(key, f"${fixed_formula}$")

        # 再次压缩
        md = re.sub(r"\n{3,}", "\n\n", md)
        return md.strip() + "\n"

    @staticmethod
    def _fix_katex_array(formula: str) -> str:
        """
        修复 KaTeX 不支持的 array 列定义语法。
        GitHub 的 KaTeX 不识别 {*{N}{X}} 这种重复语法，需要展开。
        例如: {*{20}{c}} → {cccccccccccccccccccc}
        """
        def expand_repeat(match):
            count = int(match.group(1))
            char = match.group(2)
            return char * count

        # 匹配 *{数字}{单字符} 并展开
        return re.sub(r'\*\{(\d+)\}\{(.)\}', expand_repeat, formula)


# ── markdownify 内部桥接类（不对外暴露）─────────────────────

class _MarkdownBridge(MarkdownConverter):
    """继承 markdownify，仅覆盖图片标签的转换逻辑。"""

    def __init__(self, img_map: dict[str, str] | None = None, **kwargs):
        self.img_map = img_map or {}
        super().__init__(**kwargs)

    def convert_img(self, el: Tag, text: str, parent_tags: set) -> str:
        src = (
            el.get("data-actualsrc")
            or el.get("data-original")
            or el.get("src")
            or ""
        )
        if not src:
            return ""
        if "zhihu.com/equation" not in src and any(
            kw in src for kw in ["data:image", "noavatar"]
        ):
            return ""
        alt = el.get("alt", "")
        local = self.img_map.get(src, src)
        return f"![{alt}]({local})\n\n"