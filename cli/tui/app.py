"""
app.py - Stage 2 Textual home screen for zhihu interactive mode

This stage upgrades the phase-1 shell into a structured, resize-aware home
screen that can support later input and task states.
"""

from textual.app import App, ComposeResult
from textual.containers import Container, Grid
from textual.events import Mount, Resize

from cli.tui.state import build_home_snapshot
from cli.tui.widgets import HeroCard, HintCard, HomeStage, StatusPill


class ZhihuInteractiveShell(App[None]):
    """Stage 2 shell for the rebuilt interactive experience."""

    CSS_PATH = "theme.tcss"
    TITLE = "zhihu interactive"
    SUB_TITLE = "Zhihu Archive"

    BINDINGS = [
        ("q", "quit", "退出"),
        ("escape", "quit", "退出"),
    ]

    def compose(self) -> ComposeResult:
        snapshot = build_home_snapshot()
        yield Container(
            HomeStage(
                HeroCard(snapshot.eyebrow, snapshot.title, snapshot.subtitle),
                Grid(
                    *(StatusPill(item.label, item.value, item.tone) for item in snapshot.statuses),
                    id="status-grid",
                ),
                HintCard(snapshot.notes),
                id="center-stage",
            ),
            id="viewport",
        )

    def on_mount(self, _: Mount) -> None:
        """Apply the initial responsive layout class."""
        self._sync_layout_mode(self.size.width)

    def on_resize(self, event: Resize) -> None:
        """Re-apply responsive layout classes whenever the terminal changes."""
        self._sync_layout_mode(event.size.width)

    def _sync_layout_mode(self, width: int) -> None:
        """Update screen classes based on current terminal width."""
        self.screen.set_class(width < 110, "compact")
        self.screen.set_class(width < 84, "narrow")


def launch_tui() -> None:
    """Run the stage-2 Textual shell."""
    ZhihuInteractiveShell().run()
