"""
widgets.py - Reusable home screen widgets for the interactive TUI.
"""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Input, Static


class HeroCard(Widget):
    """Centered hero section."""

    def __init__(self, eyebrow: str, title: str, subtitle: str) -> None:
        super().__init__(id="hero")
        self._eyebrow = eyebrow
        self._title = title
        self._subtitle = subtitle

    def compose(self) -> ComposeResult:
        yield Static(self._eyebrow, classes="hero-eyebrow")
        yield Static(self._title, classes="hero-title")
        yield Static(self._subtitle, classes="hero-subtitle")


class StatusPill(Widget):
    """Compact status block for the home overview."""

    def __init__(self, label: str, value: str, tone: str) -> None:
        super().__init__(classes="status-pill")
        self._label = label
        self._value = value
        self._tone = tone

    def compose(self) -> ComposeResult:
        yield Static(self._label, classes="status-label")
        yield Static(self._value, classes=f"status-value tone-{self._tone}")


class HintCard(Widget):
    """Secondary copy block below the hero content."""

    def __init__(self, notes: tuple[str, ...]) -> None:
        super().__init__(id="hint")
        self._notes = notes

    def compose(self) -> ComposeResult:
        for index, note in enumerate(self._notes):
            tone = "callout" if index == 0 else "callout dim"
            yield Static(note, classes=tone)


class InputCard(Widget):
    """Input surface for pasting Zhihu links into the TUI."""

    def __init__(self) -> None:
        super().__init__(id="input-card")

    def compose(self) -> ComposeResult:
        yield Static("输入知乎链接", classes="section-label")
        yield Input(
            placeholder="粘贴回答、问题页或专栏链接；支持从混合文本中自动提取",
            id="url-input",
        )
        yield Static("回车生成归档草案；按 q 或 Esc 退出。", classes="section-caption")


class SummaryCard(Widget):
    """Mutable card that reflects the current parsed draft."""

    _TONES = ("muted", "accent", "success", "warn", "danger")

    def __init__(self, title: str, lines: tuple[str, ...], tone: str) -> None:
        super().__init__(id="draft-card")
        self._title = title
        self._lines = lines
        self._tone = tone

    def compose(self) -> ComposeResult:
        yield Static(self._title, id="draft-title")
        yield Static(self._format_lines(self._lines), id="draft-body")

    def on_mount(self) -> None:
        """Apply the initial tone class."""
        self._sync_tone()

    def update_content(self, title: str, lines: tuple[str, ...], tone: str) -> None:
        """Update the summary body after the app parses new input."""
        self._title = title
        self._lines = lines
        self._tone = tone
        self.query_one("#draft-title", Static).update(title)
        self.query_one("#draft-body", Static).update(self._format_lines(lines))
        self._sync_tone()

    def _sync_tone(self) -> None:
        for candidate in self._TONES:
            self.set_class(candidate == self._tone, f"tone-{candidate}")

    @staticmethod
    def _format_lines(lines: tuple[str, ...]) -> str:
        return "\n".join(f"• {line}" for line in lines)


class HomeStage(Vertical):
    """Main stage wrapper for the centered landing view."""
