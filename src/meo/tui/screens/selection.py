"""Selection screen - Step 1: Mark chunks and assign categories"""

from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Container
from textual.screen import Screen
from textual.widgets import Static, Button, TextArea, Footer, ListView, ListItem, Label
from textual.message import Message

from meo.models.project import ProjectState
from meo.models.chunk import Chunk, ChunkCategory, TextRange, Location


class ChunkListItem(ListItem):
    """A list item representing a chunk"""

    def __init__(self, chunk: Chunk):
        super().__init__()
        self.chunk = chunk

    def compose(self) -> ComposeResult:
        category_colors = {
            ChunkCategory.EDIT: "green",
            ChunkCategory.CHANGE_ENTIRELY: "yellow",
            ChunkCategory.TWEAK: "cyan",
            ChunkCategory.LEAVE_ALONE: "dim",
        }
        color = category_colors.get(self.chunk.category, "white")
        preview = self.chunk.original_text[:25].replace("\n", " ")
        if len(self.chunk.original_text) > 25:
            preview += "..."
        yield Label(f"[{color}]{self.chunk.id}[/] [{self.chunk.category.value}]\n{preview}")


class SelectionScreen(Screen):
    """Screen for selecting and marking chunks"""

    BINDINGS = [
        Binding("m", "mark_chunk", "Mark Selection"),
        Binding("1", "set_category('edit')", "Set: Edit"),
        Binding("2", "set_category('change_entirely')", "Set: Change"),
        Binding("3", "set_category('tweak_as_necessary')", "Set: Tweak"),
        Binding("4", "set_category('leave_alone')", "Set: Leave"),
        Binding("d", "delete_chunk", "Delete Chunk"),
        Binding("n", "next_step", "Next Step"),
        Binding("tab", "focus_next", "Focus Next", show=False),
    ]

    def __init__(self, source_file: Path, content: str, state: ProjectState):
        super().__init__()
        self.source_file = source_file
        self.content = content
        self.state = state
        self.selected_chunk_id: Optional[str] = None

    def compose(self) -> ComposeResult:
        yield Static(f"[bold]MEO - Selection[/bold]  |  {self.source_file.name}", classes="title")
        yield Static(
            "[dim]m[/]=mark  [dim]1-4[/]=category  [dim]d[/]=delete  [dim]n[/]=next step[/dim]",
            classes="help-text",
        )

        with Horizontal():
            with Vertical(id="editor-container"):
                yield TextArea(self.content, id="editor", read_only=False)

            with Vertical(id="chunk-list"):
                yield Static("[bold]Chunks[/bold]")
                yield ListView(id="chunks-listview")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the editor and chunk list"""
        self._refresh_chunk_list()
        editor = self.query_one("#editor", TextArea)
        editor.focus()

    def _refresh_chunk_list(self) -> None:
        """Refresh the chunk list view"""
        listview = self.query_one("#chunks-listview", ListView)
        listview.clear()
        for chunk in self.state.chunks:
            listview.append(ChunkListItem(chunk))

    def _get_selection_range(self) -> Optional[TextRange]:
        """Get the current selection as a TextRange"""
        editor = self.query_one("#editor", TextArea)
        selection = editor.selection

        if selection.start == selection.end:
            return None

        # Normalize selection (start before end)
        start = min(selection.start, selection.end)
        end = max(selection.start, selection.end)

        return TextRange(
            start=Location(row=start[0], col=start[1]),
            end=Location(row=end[0], col=end[1]),
        )

    def _get_selected_text(self) -> str:
        """Get the currently selected text"""
        editor = self.query_one("#editor", TextArea)
        return editor.selected_text

    def action_mark_chunk(self) -> None:
        """Mark the current selection as a new chunk"""
        text_range = self._get_selection_range()
        if text_range is None:
            self.notify("No text selected", severity="warning")
            return

        selected_text = self._get_selected_text()
        if not selected_text.strip():
            self.notify("Selection is empty", severity="warning")
            return

        # Check for overlaps
        for existing in self.state.chunks:
            if text_range.overlaps(existing.range):
                self.notify(f"Selection overlaps with {existing.id}", severity="error")
                return

        # Create new chunk
        chunk = Chunk(
            id=self.state.next_chunk_id(),
            range=text_range,
            category=ChunkCategory.EDIT,
            original_text=selected_text,
        )

        self.state.chunks.append(chunk)
        self._refresh_chunk_list()
        self.notify(f"Created {chunk.id}")

    def action_set_category(self, category: str) -> None:
        """Set category for the chunk under cursor or selected in list"""
        chunk = self._get_chunk_at_cursor()
        if chunk is None:
            self.notify("No chunk at cursor position", severity="warning")
            return

        try:
            chunk.category = ChunkCategory(category)
            self._refresh_chunk_list()
            self.notify(f"Set {chunk.id} to {category}")
        except ValueError:
            self.notify(f"Invalid category: {category}", severity="error")

    def action_delete_chunk(self) -> None:
        """Delete the chunk under cursor"""
        chunk = self._get_chunk_at_cursor()
        if chunk is None:
            self.notify("No chunk at cursor position", severity="warning")
            return

        self.state.remove_chunk(chunk.id)
        self._refresh_chunk_list()
        self.notify(f"Deleted {chunk.id}")

    def _get_chunk_at_cursor(self) -> Optional[Chunk]:
        """Get the chunk at the current cursor position"""
        editor = self.query_one("#editor", TextArea)
        cursor = editor.cursor_location

        for chunk in self.state.chunks:
            if chunk.range.contains(cursor[0], cursor[1]):
                return chunk
        return None

    def action_next_step(self) -> None:
        """Move to directions screen"""
        chunks_needing_direction = self.state.get_chunks_needing_direction()
        if not chunks_needing_direction:
            self.notify("No chunks marked for editing", severity="warning")
            return

        # Assign execution order
        for i, chunk in enumerate(chunks_needing_direction, 1):
            chunk.execution_order = i

        self.app.go_to_directions()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle chunk selection in list"""
        if isinstance(event.item, ChunkListItem):
            chunk = event.item.chunk
            editor = self.query_one("#editor", TextArea)
            # Move cursor to chunk start
            editor.cursor_location = (chunk.range.start.row, chunk.range.start.col)
            editor.focus()
