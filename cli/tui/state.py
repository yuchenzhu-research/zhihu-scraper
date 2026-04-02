"""
state.py - View models and stage-3 draft parsing for the interactive TUI.
"""

from dataclasses import dataclass

from core.config import get_config
from core.cookie_manager import has_available_cookie_sources
from core.utils import detect_url_type, extract_id_from_url, extract_urls


@dataclass(frozen=True)
class StatusItem:
    """Single status pill shown on the TUI home screen."""

    label: str
    value: str
    tone: str


@dataclass(frozen=True)
class HomeSnapshot:
    """Static home screen snapshot."""

    eyebrow: str
    title: str
    subtitle: str
    statuses: tuple[StatusItem, ...]
    notes: tuple[str, ...]
    cookie_ready: bool


@dataclass(frozen=True)
class DraftTarget:
    """Single parsed target from the input bar."""

    url: str
    url_type: str
    limit: int | None = None


@dataclass(frozen=True)
class DraftSummary:
    """User-facing draft summary shown below the input bar."""

    title: str
    lines: tuple[str, ...]
    tone: str
    targets: tuple[DraftTarget, ...] = ()
    pending_question_url: str | None = None

    @property
    def requires_question_limit(self) -> bool:
        """Whether a single question-page draft still needs a Top-N choice."""
        return self.pending_question_url is not None


def build_home_snapshot() -> HomeSnapshot:
    """Build the current home snapshot from runtime configuration."""
    cfg = get_config()
    cookie_ready = has_available_cookie_sources(
        cfg.zhihu.cookies_file,
        cfg.zhihu.cookies_pool_dir,
    )

    browser_mode = "无头" if cfg.zhihu.browser.headless else "显示窗口"
    return HomeSnapshot(
        eyebrow="ZHIHU ARCHIVE",
        title="知乎归档台",
        subtitle="一个围绕抓取、归档与后续检索而设计的全屏终端工作台",
        statuses=(
            StatusItem("Cookie", "已就绪" if cookie_ready else "未检测到", "success" if cookie_ready else "warn"),
            StatusItem("浏览器", browser_mode, "accent" if not cfg.zhihu.browser.headless else "muted"),
            StatusItem("旧版回退", "--legacy", "muted"),
        ),
        notes=(
            "现在可以直接在工作台内粘贴知乎链接，应用会先生成归档草案。",
            "单个问题页链接会先询问抓取数量；多链接场景先保持轻量预览。",
            "旧版 Rich / questionary 流程仍然可用：zhihu interactive --legacy",
        ),
        cookie_ready=cookie_ready,
    )


def build_idle_summary() -> DraftSummary:
    """Initial summary card before any input is submitted."""
    return DraftSummary(
        title="等待输入链接",
        lines=(
            "支持回答、问题页、专栏链接，也支持从一段混合文本中自动提取。",
            "这一阶段先完成输入流和问题页选项，不执行真实抓取。",
        ),
        tone="muted",
    )


def parse_input_to_draft(text: str, cookie_ready: bool) -> DraftSummary:
    """Parse free-form input into a draft archive summary."""
    stripped = text.strip()
    if not stripped:
        return build_idle_summary()

    urls = tuple(extract_urls(stripped))
    if not urls:
        return DraftSummary(
            title="未识别到知乎链接",
            lines=(
                "请粘贴回答、问题页或专栏链接。",
                "如果是一段长文本，应用会自动抽取其中的知乎 URL。",
            ),
            tone="warn",
        )

    targets = tuple(DraftTarget(url=url, url_type=detect_url_type(url)) for url in urls)
    question_targets = tuple(target for target in targets if target.url_type == "question")

    if len(targets) == 1 and len(question_targets) == 1:
        question_target = question_targets[0]
        if cookie_ready:
            return DraftSummary(
                title="检测到问题页链接",
                lines=(
                    f"{_describe_target(question_target)}",
                    "这不是单条回答。请先选择本轮要预览的回答数量。",
                    "可选 Top 3、Top 20 或自定义正整数。",
                ),
                tone="accent",
                targets=targets,
                pending_question_url=question_target.url,
            )
        return apply_question_limit(
            DraftSummary(
                title="检测到问题页链接",
                lines=(),
                tone="warn",
                targets=targets,
                pending_question_url=question_target.url,
            ),
            3,
            source="游客模式默认值",
        )

    if question_targets:
        targets = tuple(
            DraftTarget(url=target.url, url_type=target.url_type, limit=3 if target.url_type == "question" else None)
            for target in targets
        )
        preview_lines = tuple(_describe_target(target) for target in targets[:3])
        more_count = len(targets) - len(preview_lines)
        extra_lines = (f"其余 {more_count} 个链接将在下一阶段接入真实任务队列。",) if more_count > 0 else ()
        summary_lines = (
            _summarize_type_counts(targets),
            f"检测到 {len(question_targets)} 个问题页，阶段 3 先统一按 Top 3 预览。",
        ) + preview_lines + extra_lines
        return DraftSummary(
            title="已暂存多链接草案",
            lines=summary_lines,
            tone="accent",
            targets=targets,
        )

    preview_lines = tuple(_describe_target(target) for target in targets[:3])
    more_count = len(targets) - len(preview_lines)
    extra_lines = (f"其余 {more_count} 个链接已识别，真实执行会在阶段 4 接入。",) if more_count > 0 else ()
    return DraftSummary(
        title="已识别归档草案",
        lines=(
            _summarize_type_counts(targets),
        ) + preview_lines + extra_lines + (
            "当前阶段只验证输入流，不会真正写入归档目录。",
        ),
        tone="success",
        targets=targets,
    )


def apply_question_limit(draft: DraftSummary, limit: int, source: str) -> DraftSummary:
    """Resolve a pending question-page draft into a concrete Top-N plan."""
    updated_targets = tuple(
        DraftTarget(url=target.url, url_type=target.url_type, limit=limit if target.url_type == "question" else target.limit)
        for target in draft.targets
    )
    question_target = next((target for target in updated_targets if target.url_type == "question"), None)
    lines = (
        _describe_target(question_target) if question_target else f"问题页 · Top {limit}",
        f"抓取数量已设置为 Top {limit}。",
        f"来源：{source}。",
        "当前阶段只保留草案，真实抓取会在下一阶段接入。",
    )
    return DraftSummary(
        title="问题页草案已更新",
        lines=lines,
        tone="success",
        targets=updated_targets,
        pending_question_url=None,
    )


def _summarize_type_counts(targets: tuple[DraftTarget, ...]) -> str:
    """Build a short aggregate summary for the parsed targets."""
    answer_count = sum(1 for target in targets if target.url_type == "answer")
    question_count = sum(1 for target in targets if target.url_type == "question")
    article_count = sum(1 for target in targets if target.url_type == "article")

    parts = []
    if answer_count:
        parts.append(f"{answer_count} 个回答")
    if question_count:
        parts.append(f"{question_count} 个问题页")
    if article_count:
        parts.append(f"{article_count} 篇专栏")

    summary = "，".join(parts) if parts else f"{len(targets)} 个知乎链接"
    return f"识别到 {len(targets)} 个链接：{summary}。"


def _describe_target(target: DraftTarget) -> str:
    """Create a compact one-line description for a parsed target."""
    target_id = extract_id_from_url(target.url)
    type_name = {
        "answer": "回答",
        "question": "问题页",
        "article": "专栏",
    }.get(target.url_type, "链接")
    base = f"{type_name} #{target_id}" if target_id else f"{type_name} · {target.url}"
    if target.url_type == "question" and target.limit:
        return f"{base} · Top {target.limit}"
    return base
