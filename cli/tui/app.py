"""
app.py - Stage 5 Textual shell for zhihu interactive mode.
"""

from typing import Callable

from textual.app import App, ComposeResult
from textual.containers import Container, Grid
from textual.events import Mount, Resize
from textual.widgets import Footer

from cli.tui.dialogs import QuestionLimitScreen
from cli.tui.runner import ProgressCallback, execute_draft_run
from cli.tui.state import (
    DraftSummary,
    ExecutionReport,
    apply_question_limit,
    build_detail_snapshot,
    build_execution_summary,
    build_history_snapshot,
    build_home_snapshot,
    build_idle_summary,
    build_queue_snapshot,
    build_retry_draft,
    build_running_summary,
    parse_input_to_draft,
)
from cli.tui.widgets import (
    ArchiveInput,
    DetailCard,
    HistoryCard,
    HeroCard,
    HintCard,
    HomeStage,
    InputCard,
    QueueCard,
    SummaryCard,
)


DraftExecutor = Callable[[DraftSummary, ProgressCallback | None], ExecutionReport]


class ZhihuInteractiveShell(App[None]):
    """Stage 5 shell for the rebuilt interactive experience."""

    CSS_PATH = "theme.tcss"
    TITLE = "zhihu interactive"
    SUB_TITLE = "Zhihu Archive"

    BINDINGS = [
        ("ctrl+l", "focus_input", "输入"),
        ("ctrl+r", "run_current_draft", "执行"),
        ("ctrl+y", "load_retry_draft", "重试"),
        ("q", "quit", "退出"),
        ("escape", "quit", "退出"),
    ]

    def __init__(self, draft_executor: DraftExecutor | None = None) -> None:
        super().__init__()
        self._snapshot = build_home_snapshot()
        self._draft = build_idle_summary()
        self._pending_question_draft: DraftSummary | None = None
        self._draft_executor = draft_executor or execute_draft_run
        self._is_running = False
        self._history: list[ExecutionReport] = []

    def compose(self) -> ComposeResult:
        queue = build_queue_snapshot(self._draft, is_running=False)
        history = build_history_snapshot(())
        detail = build_detail_snapshot(self._draft, ())
        yield Container(
            HomeStage(
                HeroCard(self._snapshot.eyebrow, self._snapshot.title, self._snapshot.subtitle),
                InputCard(),
                SummaryCard(self._draft.title, self._draft.lines, self._draft.tone),
                Grid(
                    QueueCard(queue.title, queue.lines, queue.tone),
                    HistoryCard(history.title, history.lines, history.tone),
                    id="workflow-grid",
                ),
                DetailCard(detail.title, detail.lines, detail.tone),
                HintCard(self._snapshot.notes),
                id="center-stage",
            ),
            id="viewport",
        )
        yield Footer()

    def on_mount(self, _: Mount) -> None:
        """Apply the initial responsive layout class and focus the input bar."""
        self._sync_layout_mode(self.size.width)
        self.call_after_refresh(self.action_focus_input)

    def on_resize(self, event: Resize) -> None:
        """Re-apply responsive layout classes whenever the terminal changes."""
        self._sync_layout_mode(event.size.width)

    async def on_archive_input_submitted(self, event: ArchiveInput.Submitted) -> None:
        """Parse user input inside the TUI instead of delegating to questionary."""
        if event.input.id != "url-input":
            return

        draft = parse_input_to_draft(event.value, cookie_ready=self._snapshot.cookie_ready)

        if draft.requires_question_limit:
            self._pending_question_draft = draft
            self._set_draft(draft)
            self.push_screen(QuestionLimitScreen(), self._handle_question_limit)
            return

        self._set_draft(draft)
        event.input.focus()
        if draft.ready_to_run:
            self.notify("草案已生成，按 Ctrl+R 即可执行！", title="解析完成", severity="information")

    def action_focus_input(self) -> None:
        """Move keyboard focus back to the primary input field."""
        self.query_one("#url-input", ArchiveInput).focus()

    def action_run_current_draft(self) -> None:
        """Execute the current draft in a background worker."""
        if self._is_running:
            self._set_draft(
                DraftSummary(
                    title="任务仍在执行中",
                    lines=(
                        "当前归档尚未完成，请等待本轮执行结束。",
                        "阶段 5 仍保持单轮执行，不允许并发启动多个任务。",
                    ),
                    tone="warn",
                    targets=self._draft.targets,
                )
            )
            return

        if self._draft.requires_question_limit:
            self._set_draft(
                DraftSummary(
                    title="请先完成问题页配置",
                    lines=(
                        "当前草案还缺少问题页的抓取数量。",
                        "先完成 Top 3、Top 20 或自定义选择，再执行归档。",
                    ),
                    tone="warn",
                    targets=self._draft.targets,
                    pending_question_url=self._draft.pending_question_url,
                )
            )
            return

        if not self._draft.ready_to_run:
            self._set_draft(
                DraftSummary(
                    title="还没有可执行的草案",
                    lines=(
                        "请先粘贴知乎链接并回车生成当前草案。",
                        "阶段 5 已接入真实执行、最近结果和失败重试，但仍以当前草案为单次运行边界。",
                    ),
                    tone="warn",
                )
            )
            return

        draft = self._draft
        self._is_running = True
        self.query_one("#url-input", ArchiveInput).disabled = True
        self.notify("后端任务已激活，请耐心等待...", title="任务启动", severity="information")
        self._set_draft(
            build_running_summary(
                draft,
                current_index=1,
                total=max(1, len(draft.targets)),
                output_dir="准备启动...",
                phase="正在初始化后台任务",
            )
        )
        self.run_worker(
            lambda: self._run_draft_worker(draft),
            name="archive-execution",
            group="archive",
            exclusive=True,
            exit_on_error=False,
            thread=True,
        )

    def action_load_retry_draft(self) -> None:
        """Load a retry draft from the latest failed execution records."""
        if self._is_running:
            self._set_draft(
                DraftSummary(
                    title="任务仍在执行中",
                    lines=(
                        "当前归档尚未完成，暂时不能切换到失败重试草案。",
                        "等待本轮执行结束后再加载失败项。",
                    ),
                    tone="warn",
                    targets=self._draft.targets,
                )
            )
            return

        latest_report = self._history[0] if self._history else None
        if latest_report is None:
            self._set_draft(
                DraftSummary(
                    title="还没有可重试的结果",
                    lines=(
                        "先执行至少一轮归档，最近结果面板才会出现失败项。",
                        "阶段 5 的失败重试入口依赖最近一轮执行报告。",
                    ),
                    tone="warn",
                )
            )
            return

        retry_draft = build_retry_draft(latest_report)
        if retry_draft is None:
            self._set_draft(
                DraftSummary(
                    title="最近一轮没有失败项",
                    lines=(
                        "最近一次执行全部成功，不需要生成重试草案。",
                        "你可以继续输入新链接，或直接执行新的当前草案。",
                    ),
                    tone="success",
                    targets=self._draft.targets,
                )
            )
            return

        self._set_draft(retry_draft)
        self.action_focus_input()

    def action_quit(self) -> None:
        """Prevent quitting while an execution run is still active."""
        if self._is_running:
            self._set_draft(
                DraftSummary(
                    title="归档进行中",
                    lines=(
                        "当前后台任务仍在执行，暂不退出工作台。",
                        "等待本轮归档完成后再退出，避免留下半完成状态。",
                    ),
                    tone="warn",
                    targets=self._draft.targets,
                )
            )
            return
        self.exit()

    def _sync_layout_mode(self, width: int) -> None:
        """Update screen classes based on current terminal width."""
        self.screen.set_class(width < 110, "compact")
        self.screen.set_class(width < 84, "narrow")

    def _set_draft(self, draft: DraftSummary) -> None:
        """Update the mutable summary card below the input bar."""
        self._draft = draft
        self.query_one(SummaryCard).update_content(draft.title, draft.lines, draft.tone)
        self._refresh_panels()

    def _handle_question_limit(self, selected_limit: int | None) -> None:
        """Resolve the pending question-page draft when the modal closes."""
        pending = self._pending_question_draft
        self._pending_question_draft = None
        if pending is None:
            self.action_focus_input()
            return

        if selected_limit is None:
            self._set_draft(
                DraftSummary(
                    title="已取消问题页配置",
                    lines=(
                        "问题页草案尚未写入抓取数量。",
                        "重新提交该链接后，可以再次选择 Top 3、Top 20 或自定义。",
                    ),
                    tone="warn",
                    targets=pending.targets,
                )
            )
            self.action_focus_input()
            return

        source = "Top 3 预设" if selected_limit == 3 else "Top 20 预设" if selected_limit == 20 else "自定义输入"
        self._set_draft(apply_question_limit(pending, selected_limit, source))
        self.action_focus_input()

    def _run_draft_worker(self, draft: DraftSummary) -> ExecutionReport:
        """Execute one draft inside a background thread worker."""
        try:
            report = self._draft_executor(
                draft,
                lambda summary: self.call_from_thread(self._set_draft, summary),
            )
        except Exception as exc:
            self.call_from_thread(self._finish_run_with_error, str(exc))
            raise

        self.call_from_thread(self._finish_run, report)
        return report

    def _finish_run(self, report: ExecutionReport) -> None:
        """Restore the UI after a successful worker completion."""
        self._is_running = False
        self._history.insert(0, report)
        self._history = self._history[:5]
        input_widget = self.query_one("#url-input", ArchiveInput)
        input_widget.disabled = False
        self._set_draft(build_execution_summary(report))
        input_widget.focus()

        if report.success_count and not report.failure_count:
            self.notify(f"已成功归档 {report.success_count} 个目标！", title="执行成功", severity="success")
        elif report.success_count:
            self.notify(f"任务部分完成，成功 {report.success_count} 个，失败 {report.failure_count} 个。", title="包含失败项", severity="warning")
        else:
            self.notify(f"所有 {report.failure_count} 个目标全部执行失败。", title="任务失败", severity="error")

    def _finish_run_with_error(self, error: str) -> None:
        """Restore the UI after an unexpected worker failure."""
        self._is_running = False
        input_widget = self.query_one("#url-input", ArchiveInput)
        input_widget.disabled = False
        self._set_draft(
            DraftSummary(
                title="归档任务异常终止",
                lines=(
                    f"错误：{error}",
                    "这不是目标级失败，而是执行桥本身中断了。",
                ),
                tone="danger",
                targets=self._draft.targets,
            )
        )
        input_widget.focus()

    def _refresh_panels(self) -> None:
        """Refresh secondary workflow panels from current draft and history."""
        queue = build_queue_snapshot(self._draft, is_running=self._is_running)
        history = build_history_snapshot(tuple(self._history))
        detail = build_detail_snapshot(self._draft, tuple(self._history))
        self.query_one(QueueCard).update_content(queue.title, queue.lines, queue.tone)
        self.query_one(HistoryCard).update_content(history.title, history.lines, history.tone)
        self.query_one(DetailCard).update_content(detail.title, detail.lines, detail.tone)


def launch_tui() -> None:
    """Run the stage-5 Textual shell."""
    ZhihuInteractiveShell().run()
