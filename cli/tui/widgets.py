"""
widgets.py - Reusable home screen widgets for the interactive TUI.
"""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Static


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


class HomeStage(Vertical):
    """Main stage wrapper for the centered landing view."""

