"""
app.py - Stage 3 Textual shell for zhihu interactive mode.
"""

from textual.app import App, ComposeResult
from textual.containers import Container, Grid
from textual.events import Mount, Resize
from textual.widgets import Footer, Input

from cli.tui.dialogs import QuestionLimitScreen
from cli.tui.state import (
    DraftSummary,
    apply_question_limit,
    build_home_snapshot,
    build_idle_summary,
    parse_input_to_draft,
)
from cli.tui.widgets import HeroCard, HintCard, HomeStage, InputCard, StatusPill, SummaryCard


class ZhihuInteractiveShell(App[None]):
    """Stage 3 shell for the rebuilt interactive experience."""

    CSS_PATH = "theme.tcss"
    TITLE = "zhihu interactive"
    SUB_TITLE = "Zhihu Archive"

    BINDINGS = [
        ("ctrl+l", "focus_input", "输入"),
        ("q", "quit", "退出"),
        ("escape", "quit", "退出"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._snapshot = build_home_snapshot()
        self._draft = build_idle_summary()
        self._pending_question_draft: DraftSummary | None = None

    def compose(self) -> ComposeResult:
        yield Container(
            HomeStage(
                HeroCard(self._snapshot.eyebrow, self._snapshot.title, self._snapshot.subtitle),
                Grid(
                    *(StatusPill(item.label, item.value, item.tone) for item in self._snapshot.statuses),
                    id="status-grid",
                ),
                InputCard(),
                SummaryCard(self._draft.title, self._draft.lines, self._draft.tone),
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

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Parse user input inside the TUI instead of delegating to questionary."""
        if event.input.id != "url-input":
            return

        draft = parse_input_to_draft(event.value, cookie_ready=self._snapshot.cookie_ready)
        event.input.value = ""

        if draft.requires_question_limit:
            self._pending_question_draft = draft
            self._set_draft(draft)
            self.push_screen(QuestionLimitScreen(), self._handle_question_limit)
            return

        self._set_draft(draft)
        event.input.focus()

    def action_focus_input(self) -> None:
        """Move keyboard focus back to the primary input field."""
        self.query_one("#url-input", Input).focus()

    def _sync_layout_mode(self, width: int) -> None:
        """Update screen classes based on current terminal width."""
        self.screen.set_class(width < 110, "compact")
        self.screen.set_class(width < 84, "narrow")

    def _set_draft(self, draft: DraftSummary) -> None:
        """Update the mutable summary card below the input bar."""
        self._draft = draft
        self.query_one(SummaryCard).update_content(draft.title, draft.lines, draft.tone)

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


def launch_tui() -> None:
    """Run the stage-3 Textual shell."""
    ZhihuInteractiveShell().run()
