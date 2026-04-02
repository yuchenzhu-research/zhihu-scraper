"""
state.py - View models for the interactive TUI.
"""

from dataclasses import dataclass
from pathlib import Path

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
class PanelSnapshot:
    """Generic card snapshot used by queue/history panels."""

    title: str
    lines: tuple[str, ...]
    tone: str


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

    @property
    def ready_to_run(self) -> bool:
        """Whether the current draft can be executed immediately."""
        return bool(self.targets) and not self.requires_question_limit


@dataclass(frozen=True)
class ExecutionRecord:
    """Result for one target inside one execution round."""

    target: DraftTarget
    saved_count: int
    markdown_paths: tuple[str, ...]
    error: str | None = None
    log_tail: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        """Whether this target finished without an execution error."""
        return self.error is None


@dataclass(frozen=True)
class ExecutionReport:
    """Aggregated result of one execution round."""

    output_dir: str
    records: tuple[ExecutionRecord, ...]

    @property
    def success_count(self) -> int:
        return sum(1 for record in self.records if record.succeeded)

    @property
    def failure_count(self) -> int:
        return len(self.records) - self.success_count


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
            "回车会先生成归档草案，按 Ctrl+R 执行当前草案。",
            "按 Ctrl+Y 可载入最近一轮失败项，生成重试草案。",
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
            "回车先生成草案；确认后按 Ctrl+R 执行当前归档。",
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
                    f"{describe_target(question_target)}",
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
        preview_lines = tuple(describe_target(target) for target in targets[:3])
        more_count = len(targets) - len(preview_lines)
        extra_lines = (f"其余 {more_count} 个链接也已加入当前草案队列。",) if more_count > 0 else ()
        summary_lines = (
            _summarize_type_counts(targets),
            "检测到问题页时，当前阶段先按每个问题 Top 3 执行。",
        ) + preview_lines + extra_lines + (
            "确认后按 Ctrl+R 执行当前草案。",
        )
        return DraftSummary(
            title="已暂存多链接草案",
            lines=summary_lines,
            tone="accent",
            targets=targets,
        )

    preview_lines = tuple(describe_target(target) for target in targets[:3])
    more_count = len(targets) - len(preview_lines)
    extra_lines = (f"其余 {more_count} 个链接已识别，本轮会按当前顺序顺次执行。",) if more_count > 0 else ()
    return DraftSummary(
        title="已识别归档草案",
        lines=(
            _summarize_type_counts(targets),
        ) + preview_lines + extra_lines + (
            "确认后按 Ctrl+R 开始归档。",
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
        describe_target(question_target) if question_target else f"问题页 · Top {limit}",
        f"抓取数量已设置为 Top {limit}。",
        f"来源：{source}。",
        "确认后按 Ctrl+R 开始归档。",
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


def describe_target(target: DraftTarget | None) -> str:
    """Create a compact one-line description for a parsed target."""
    if target is None:
        return "未知目标"
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


def build_running_summary(
    draft: DraftSummary,
    *,
    current_index: int,
    total: int,
    output_dir: str,
    phase: str,
) -> DraftSummary:
    """Build the transient running-state summary shown during execution."""
    current_target = draft.targets[current_index - 1] if 0 < current_index <= total else None
    return DraftSummary(
        title=f"正在归档 {current_index}/{total}",
        lines=(
            f"当前目标：{describe_target(current_target)}",
            f"阶段：{phase}",
            f"输出目录：{output_dir}",
            "执行期间输入栏会暂时锁定，完成后自动恢复。",
        ),
        tone="accent",
        targets=draft.targets,
    )


def build_execution_summary(report: ExecutionReport) -> DraftSummary:
    """Build the final summary card from one execution report."""
    success = report.success_count
    failure = report.failure_count
    if success and not failure:
        title = "归档完成"
        tone = "success"
    elif success:
        title = "归档部分完成"
        tone = "warn"
    else:
        title = "归档失败"
        tone = "danger"

    lines = [
        f"本轮执行完成：成功 {success} 个，失败 {failure} 个。",
        f"输出目录：{report.output_dir}",
    ]

    for record in report.records[:3]:
        if record.succeeded:
            lines.append(f"{describe_target(record.target)} · 已保存 {record.saved_count} 条内容")
        else:
            lines.append(f"{describe_target(record.target)} · 失败：{record.error}")

    remaining = len(report.records) - min(len(report.records), 3)
    if remaining > 0:
        lines.append(f"其余 {remaining} 个目标已完成，后续阶段会补更完整的结果面板。")

    return DraftSummary(
        title=title,
        lines=tuple(lines),
        tone=tone,
        targets=tuple(record.target for record in report.records),
    )


def build_queue_snapshot(draft: DraftSummary, *, is_running: bool) -> PanelSnapshot:
    """Build the queue panel from the current draft."""
    if not draft.targets:
        return PanelSnapshot(
            title="当前队列为空",
            lines=(
                "输入链接并回车后，这里会显示本轮待执行目标。",
                "多链接会按当前顺序顺次执行。",
            ),
            tone="muted",
        )

    status = "执行中" if is_running else "待补问题页配置" if draft.requires_question_limit else "等待执行"
    tone = "accent" if is_running else "warn" if draft.requires_question_limit else "success"
    preview = tuple(describe_target(target) for target in draft.targets[:4])
    remaining = len(draft.targets) - len(preview)
    extra = (f"其余 {remaining} 个目标仍在当前草案中。",) if remaining > 0 else ()
    return PanelSnapshot(
        title="当前草案队列",
        lines=(
            f"状态：{status} · 共 {len(draft.targets)} 个目标。",
            *_with_queue_prefix(preview),
            *extra,
        ),
        tone=tone,
    )


def build_history_snapshot(reports: tuple[ExecutionReport, ...]) -> PanelSnapshot:
    """Build the recent-results panel from execution history."""
    if not reports:
        return PanelSnapshot(
            title="最近结果为空",
            lines=(
                "执行一次归档后，这里会显示输出路径和失败摘要。",
                "如果最近一轮存在失败项，可按 Ctrl+Y 载入重试草案。",
            ),
            tone="muted",
        )

    latest = reports[0]
    tone = "warn" if latest.failure_count else "success"
    lines = [
        f"最近一轮：成功 {latest.success_count} 个，失败 {latest.failure_count} 个。",
        f"输出目录：{latest.output_dir}",
    ]
    for record in latest.records[:3]:
        if record.succeeded:
            target_path = _short_output_path(record.markdown_paths[0]) if record.markdown_paths else latest.output_dir
            lines.append(f"{describe_target(record.target)} -> {target_path}")
        else:
            detail = record.error or "未知错误"
            if record.log_tail:
                detail = f"{detail} | {record.log_tail[-1]}"
            lines.append(f"{describe_target(record.target)} -> 失败：{detail}")

    if len(reports) > 1:
        lines.append(f"已保留最近 {len(reports)} 轮执行摘要。")

    if latest.failure_count:
        lines.append("按 Ctrl+Y 可从最近一轮失败项生成重试草案。")

    return PanelSnapshot(
        title="最近执行结果",
        lines=tuple(lines),
        tone=tone,
    )


def build_retry_draft(report: ExecutionReport) -> DraftSummary | None:
    """Create a retry draft from the failed targets in the latest report."""
    failed_targets = tuple(record.target for record in report.records if not record.succeeded)
    if not failed_targets:
        return None

    preview = tuple(describe_target(target) for target in failed_targets[:3])
    remaining = len(failed_targets) - len(preview)
    extra = (f"其余 {remaining} 个失败目标也已加入当前重试草案。",) if remaining > 0 else ()
    return DraftSummary(
        title="失败项重试草案",
        lines=(
            f"已从最近一轮失败项生成 {len(failed_targets)} 个目标。",
            *preview,
            *extra,
            "确认后按 Ctrl+R 重新执行。",
        ),
        tone="warn",
        targets=failed_targets,
    )


def _short_output_path(path: str) -> str:
    """Compress a saved markdown path for the recent-results panel."""
    parts = Path(path).parts
    if len(parts) <= 3:
        return path
    return str(Path(*parts[-3:]))


def _with_queue_prefix(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Prefix queue lines to distinguish them from status copy."""
    return tuple(f"队列：{line}" for line in lines)
