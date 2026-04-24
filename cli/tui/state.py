"""
state.py - View models for the interactive TUI.
"""

from dataclasses import dataclass
from pathlib import Path

from core.config import get_config
from core.cookie_manager import has_available_cookie_sources
from core.i18n import t
from core.utils import detect_url_type, extract_id_from_url, extract_urls


@dataclass(frozen=True)
class HomeSnapshot:
    """Static home screen snapshot."""

    eyebrow: str
    title: str
    subtitle: str
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
    translated_paths: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
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

    return HomeSnapshot(
        eyebrow=t("home.eyebrow"),
        title=t("home.title"),
        subtitle=t("home.subtitle"),
        notes=(
            t("home.hint.enter"),
            t("home.hint.retry"),
            t("home.hint.legacy"),
        ),
        cookie_ready=cookie_ready,
    )


def build_idle_summary() -> DraftSummary:
    """Initial summary card before any input is submitted."""
    return DraftSummary(
        title=t("draft.idle.title"),
        lines=(
            t("draft.idle.line1"),
            t("draft.idle.line2"),
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
            title=t("draft.no_url.title"),
            lines=(
                t("draft.no_url.line1"),
                t("draft.no_url.line2"),
            ),
            tone="warn",
        )

    targets = tuple(DraftTarget(url=url, url_type=detect_url_type(url)) for url in urls)
    question_targets = tuple(target for target in targets if target.url_type == "question")

    if len(targets) == 1 and len(question_targets) == 1:
        question_target = question_targets[0]
        if cookie_ready:
            return DraftSummary(
                title=t("draft.question.title"),
                lines=(
                    f"{describe_target(question_target)}",
                    t("draft.question.hint"),
                    t("draft.question.options"),
                ),
                tone="accent",
                targets=targets,
                pending_question_url=question_target.url,
            )
        return apply_question_limit(
            DraftSummary(
                title=t("draft.question.title"),
                lines=(),
                tone="warn",
                targets=targets,
                pending_question_url=question_target.url,
            ),
            3,
            source=t("summary.guest_default"),
        )

    if question_targets:
        targets = tuple(
            DraftTarget(url=target.url, url_type=target.url_type, limit=3 if target.url_type == "question" else None)
            for target in targets
        )
        preview_lines = tuple(describe_target(target) for target in targets[:3])
        more_count = len(targets) - len(preview_lines)
        extra_lines = (t("summary.extra", count=more_count),) if more_count > 0 else ()
        summary_lines = (
            _summarize_type_counts(targets),
            t("draft.question.top_hint"),
        ) + preview_lines + extra_lines + (
            t("draft.confirm_exec"),
        )
        return DraftSummary(
            title=t("draft.multi.title"),
            lines=summary_lines,
            tone="accent",
            targets=targets,
        )

    preview_lines = tuple(describe_target(target) for target in targets[:3])
    more_count = len(targets) - len(preview_lines)
    extra_lines = (t("summary.extra_seq", count=more_count),) if more_count > 0 else ()
    return DraftSummary(
        title=t("draft.ready.title"),
        lines=(
            _summarize_type_counts(targets),
        ) + preview_lines + extra_lines + (
            t("draft.confirm"),
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
        describe_target(question_target) if question_target else f"{t('type.question')} · Top {limit}",
        t("draft.question_updated.limit", limit=limit),
        t("draft.question_updated.source", source=source),
        t("draft.confirm"),
    )
    return DraftSummary(
        title=t("draft.question_updated.title"),
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
        parts.append(t("summary.answers", count=answer_count))
    if question_count:
        parts.append(t("summary.questions", count=question_count))
    if article_count:
        parts.append(t("summary.articles", count=article_count))

    summary = "、".join(parts) if parts else t("summary.links", count=len(targets))
    return t("summary.count", total=len(targets), detail=summary)


def describe_target(target: DraftTarget | None) -> str:
    """Create a compact one-line description for a parsed target."""
    if target is None:
        return t("type.unknown")
    target_id = extract_id_from_url(target.url)
    type_name = {
        "answer": t("type.answer"),
        "question": t("type.question"),
        "article": t("type.article"),
    }.get(target.url_type, t("type.link"))
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
        title=t("draft.running.title", current=current_index, total=total),
        lines=(
            t("draft.running.target", target=describe_target(current_target)),
            t("draft.running.phase", phase=phase),
            t("draft.running.output", output_dir=output_dir),
            t("draft.running.locked"),
        ),
        tone="accent",
        targets=draft.targets,
    )


def build_execution_summary(report: ExecutionReport) -> DraftSummary:
    """Build the final summary card from one execution report."""
    success = report.success_count
    failure = report.failure_count
    if success and not failure:
        title = t("draft.done.title")
        tone = "success"
    elif success:
        title = t("draft.partial.title")
        tone = "warn"
    else:
        title = t("draft.failed.title")
        tone = "danger"

    lines = [
        t("draft.done.summary", success=success, failure=failure),
        t("draft.done.output", output_dir=report.output_dir),
    ]

    for record in report.records[:3]:
        if record.succeeded:
            lines.append(t("draft.done.saved", target=describe_target(record.target), count=record.saved_count))
            if record.translated_paths:
                lines.append(t("draft.done.translated", count=len(record.translated_paths)))
            for note in record.notes[:1]:
                lines.append(note)
        else:
            lines.append(t("draft.done.error", target=describe_target(record.target), error=record.error))

    remaining = len(report.records) - min(len(report.records), 3)
    if remaining > 0:
        lines.append(t("draft.done.remaining", count=remaining))

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
            title=t("queue.empty.title"),
            lines=(
                t("queue.empty.line1"),
                t("queue.empty.line2"),
            ),
            tone="muted",
        )

    status = t("queue.status_running") if is_running else t("queue.status_pending") if draft.requires_question_limit else t("queue.status_waiting")
    tone = "accent" if is_running else "warn" if draft.requires_question_limit else "success"
    preview = tuple(describe_target(target) for target in draft.targets[:4])
    remaining = len(draft.targets) - len(preview)
    extra = (t("queue.remaining", count=remaining),) if remaining > 0 else ()
    return PanelSnapshot(
        title=t("queue.title"),
        lines=(
            t("queue.status", status=status, count=len(draft.targets)),
            *_with_queue_prefix(preview),
            *extra,
        ),
        tone=tone,
    )


def build_history_snapshot(reports: tuple[ExecutionReport, ...]) -> PanelSnapshot:
    """Build the recent-results panel from execution history."""
    if not reports:
        return PanelSnapshot(
            title=t("history.empty.title"),
            lines=(
                t("history.empty.line1"),
                t("history.empty.line2"),
            ),
            tone="muted",
        )

    latest = reports[0]
    tone = "warn" if latest.failure_count else "success"
    lines = [
        t("history.summary", success=latest.success_count, failure=latest.failure_count),
        t("history.output", output_dir=latest.output_dir),
    ]
    for record in latest.records[:3]:
        if record.succeeded:
            target_path = _short_output_path(record.markdown_paths[0]) if record.markdown_paths else latest.output_dir
            lines.append(f"{describe_target(record.target)} -> {target_path}")
            if record.translated_paths:
                lines.append(t("history.translated", count=len(record.translated_paths)))
            for note in record.notes[:1]:
                lines.append(t("history.note", note=note))
        else:
            detail = record.error or t("history.unknown_error")
            if record.log_tail:
                detail = f"{detail} | {record.log_tail[-1]}"
            lines.append(f"{describe_target(record.target)} -> {t('history.fail_detail', detail=detail)}")

    if len(reports) > 1:
        lines.append(t("history.rounds", count=len(reports)))

    if latest.failure_count:
        lines.append(t("history.retry_hint"))

    return PanelSnapshot(
        title=t("history.title"),
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
    extra = (t("retry.extra", count=remaining),) if remaining > 0 else ()
    return DraftSummary(
        title=t("retry.title"),
        lines=(
            t("retry.summary", count=len(failed_targets)),
            *preview,
            *extra,
            t("retry.confirm"),
        ),
        tone="warn",
        targets=failed_targets,
    )


def build_detail_snapshot(draft: DraftSummary, reports: tuple[ExecutionReport, ...]) -> PanelSnapshot:
    """Build a detail panel for the current draft and latest execution report."""
    if reports:
        latest = reports[0]
        lines = []
        for record in latest.records[:4]:
            if record.succeeded:
                saved_path = _short_output_path(record.markdown_paths[0]) if record.markdown_paths else latest.output_dir
                lines.append(t("detail.exec.saved", target=describe_target(record.target), path=saved_path))
                for translated_path in record.translated_paths[:2]:
                    lines.append(t("detail.exec.translated", path=_short_output_path(translated_path)))
                for note in record.notes[:2]:
                    lines.append(t("detail.exec.note", note=note))
            else:
                lines.append(t("detail.exec.failed", target=describe_target(record.target), error=record.error))
                if record.log_tail:
                    lines.append(t("detail.exec.log_tail", line=record.log_tail[-1]))

        if not lines:
            lines.append(t("detail.exec.empty"))

        if latest.failure_count:
            lines.append(t("detail.exec.retry_hint"))

        return PanelSnapshot(
            title=t("detail.exec.title"),
            lines=tuple(lines),
            tone="warn" if latest.failure_count else "success",
        )

    if draft.targets:
        preview = tuple(describe_target(target) for target in draft.targets[:4])
        remaining = len(draft.targets) - len(preview)
        extra = (t("detail.draft.remaining", count=remaining),) if remaining > 0 else ()
        status = t("detail.draft.pending") if draft.requires_question_limit else t("detail.draft.ready")
        return PanelSnapshot(
            title=t("detail.draft.title"),
            lines=preview + extra + (status,),
            tone="warn" if draft.requires_question_limit else "accent",
        )

    return PanelSnapshot(
        title=t("detail.idle.title"),
        lines=(
            t("detail.idle.line1"),
            t("detail.idle.line2"),
        ),
        tone="muted",
    )


def _short_output_path(path: str) -> str:
    """Compress a saved markdown path for the recent-results panel."""
    parts = Path(path).parts
    if len(parts) <= 3:
        return path
    return str(Path(*parts[-3:]))


def _with_queue_prefix(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Prefix queue lines to distinguish them from status copy."""
    return tuple(t("queue.prefix", line=line) for line in lines)
