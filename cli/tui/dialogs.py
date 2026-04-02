"""
dialogs.py - Modal screens for the interactive TUI.
"""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static


class QuestionLimitScreen(ModalScreen[int | None]):
    """Prompt for a Top-N limit when the input is a single question page."""

    BINDINGS = [
        ("escape", "dismiss_none", "取消"),
    ]

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("问题页抓取数量", id="dialog-title"),
            Static(
                "问题页不是单条回答。先确定这一轮草案要预览多少条回答，再进入下一阶段的真实抓取。",
                id="dialog-body",
            ),
            Horizontal(
                Button("Top 3", id="limit-3", classes="limit-button"),
                Button("Top 20", id="limit-20", classes="limit-button"),
                id="dialog-presets",
            ),
            Input(
                placeholder="自定义正整数，例如 50",
                restrict=r"[0-9]*",
                id="custom-limit",
            ),
            Horizontal(
                Button("确认自定义", id="limit-custom", variant="primary"),
                Button("取消", id="limit-cancel"),
                id="dialog-actions",
            ),
            Static("", id="dialog-error"),
            id="question-limit-dialog",
        )

    def on_mount(self) -> None:
        """Focus the first preset button to keep the flow keyboard-first."""
        self.query_one("#limit-3", Button).focus()

    def action_dismiss_none(self) -> None:
        """Dismiss the dialog without applying a limit."""
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle preset clicks and custom confirmation."""
        button_id = event.button.id or ""
        if button_id == "limit-3":
            self.dismiss(3)
            return
        if button_id == "limit-20":
            self.dismiss(20)
            return
        if button_id == "limit-cancel":
            self.dismiss(None)
            return
        if button_id == "limit-custom":
            self._dismiss_custom_limit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Allow Enter inside the custom input to confirm immediately."""
        if event.input.id == "custom-limit":
            self._dismiss_custom_limit()

    def _dismiss_custom_limit(self) -> None:
        """Validate custom input and close the modal if it is a positive integer."""
        raw_value = self.query_one("#custom-limit", Input).value.strip()
        if raw_value.isdigit() and int(raw_value) > 0:
            self.dismiss(int(raw_value))
            return
        self.query_one("#dialog-error", Static).update("请输入大于 0 的正整数。")
