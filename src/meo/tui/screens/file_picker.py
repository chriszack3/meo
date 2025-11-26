"""File picker screen - Select a markdown file to edit"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Static, Footer, ListView, ListItem, Label

from meo.models.config import MeoConfig
from meo.core.sidecar import get_sidecar_path


class FileListItem(ListItem):
    """A list item representing a markdown file"""

    def __init__(self, file_path: Path):
        super().__init__()
        self.file_path = file_path

    def compose(self) -> ComposeResult:
        # Get file info
        stat = self.file_path.stat()
        size_kb = stat.st_size / 1024
        modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")

        # Check if sidecar exists
        sidecar_path = get_sidecar_path(self.file_path)
        has_sidecar = sidecar_path.exists()
        sidecar_indicator = "[cyan]●[/]" if has_sidecar else " "

        yield Label(
            f"{sidecar_indicator} [bold]{self.file_path.name}[/bold]\n"
            f"  [dim]{size_kb:.1f} KB  •  {modified}[/dim]"
        )


class FilePickerScreen(Screen):
    """Screen for selecting a markdown file to edit"""

    BINDINGS = [
        Binding("enter", "select_file", "Select"),
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
    ]

    def __init__(self, config: MeoConfig):
        super().__init__()
        self.config = config
        self.selected_file: Optional[Path] = None

    def compose(self) -> ComposeResult:
        yield Static(
            f"[bold]MEO - Select File[/bold]\n"
            f"[dim]Folder: {self.config.folder}[/dim]",
            id="header",
        )
        yield Static(
            "[dim]↑/↓[/] navigate  [dim]Enter[/] select  [dim]q[/] quit  "
            "[cyan]●[/] = has existing edits",
            id="help",
        )
        yield ListView(id="file-list")
        yield Footer()

    def on_mount(self) -> None:
        """Load files on mount"""
        self._refresh_file_list()
        # Focus the list
        file_list = self.query_one("#file-list", ListView)
        file_list.focus()

    def _refresh_file_list(self) -> None:
        """Refresh the file list"""
        file_list = self.query_one("#file-list", ListView)
        file_list.clear()

        files = self.config.get_markdown_files()

        if not files:
            file_list.mount(
                ListItem(Label("[yellow]No .md files found in folder[/yellow]"))
            )
            return

        for file_path in files:
            file_list.append(FileListItem(file_path))

    def action_refresh(self) -> None:
        """Refresh the file list"""
        self._refresh_file_list()
        self.notify("Refreshed file list")

    def action_select_file(self) -> None:
        """Select the highlighted file"""
        file_list = self.query_one("#file-list", ListView)
        if file_list.highlighted_child is None:
            return

        item = file_list.highlighted_child
        if isinstance(item, FileListItem):
            self.selected_file = item.file_path
            self.app.exit(result=self.selected_file)

    def action_quit(self) -> None:
        """Quit without selecting"""
        self.app.exit(result=None)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle double-click / enter on list item"""
        if isinstance(event.item, FileListItem):
            self.selected_file = event.item.file_path
            self.app.exit(result=self.selected_file)
