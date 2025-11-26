"""Confirmation modal for generate action"""

from typing import List

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Static


class GenerateConfirmModal(ModalScreen[bool]):
    """Modal for confirming chunk generation."""

    CSS = """
    GenerateConfirmModal {
        align: center middle;
    }

    #modal-container {
        width: 50;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #button-row {
        align: center middle;
        height: 3;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("enter", "confirm", "Confirm", show=False, priority=True),
        Binding("escape", "cancel", "Cancel", show=False, priority=True),
        Binding("left", "select_yes", "Yes", show=False, priority=True),
        Binding("right", "select_no", "No", show=False, priority=True),
    ]

    def __init__(self, chunk_ids: List[str]):
        super().__init__()
        self.chunk_ids = chunk_ids
        self.selected = "yes"

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container"):
            yield Static(f"[bold]Generate {len(self.chunk_ids)} chunk(s)?[/bold]")
            yield Static("")
            for chunk_id in self.chunk_ids:
                yield Static(f"  • {chunk_id}")
            yield Static("")
            with Horizontal(id="button-row"):
                yield Static(id="yes-btn")
                yield Static("    ")
                yield Static(id="no-btn")
            yield Static("")
            yield Static("[dim]<-/-> select  |  Enter confirm  |  Esc cancel[/dim]")

    def on_mount(self) -> None:
        self._update_selection()

    def _update_selection(self) -> None:
        """Update button text based on selection"""
        yes_btn = self.query_one("#yes-btn", Static)
        no_btn = self.query_one("#no-btn", Static)

        if self.selected == "yes":
            yes_btn.update("[reverse bold green] YES [/]")
            no_btn.update("[dim] NO [/dim]")
        else:
            yes_btn.update("[dim] YES [/dim]")
            no_btn.update("[reverse bold red] NO [/]")

    def action_select_yes(self) -> None:
        self.selected = "yes"
        self._update_selection()

    def action_select_no(self) -> None:
        self.selected = "no"
        self._update_selection()

    def action_confirm(self) -> None:
        self.dismiss(self.selected == "yes")

    def action_cancel(self) -> None:
        self.dismiss(False)
