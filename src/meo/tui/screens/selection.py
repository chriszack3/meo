"""Selection screen - Step 1: Mark chunks using minimal keyboard interface"""

from enum import Enum
from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Static, TextArea, Footer, ListView, ListItem, Label

from meo.models.project import ProjectState
from meo.models.chunk import Chunk, ChunkCategory, TextRange, Location


class SelectionMode(Enum):
    """State machine for selection screen"""
    EDITING = "editing"  # Focus on TextArea, normal navigation
    SELECTING_CATEGORY = "selecting_category"  # Focus on sidebar category list


class CategoryListItem(ListItem):
    """A list item representing a chunk category"""

    def __init__(self, category: ChunkCategory):
        super().__init__()
        self.category = category

    def compose(self) -> ComposeResult:
        display_name = self.category.value.replace("_", " ").title()
        yield Label(display_name)


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
    """Screen for selecting and marking chunks with minimal keyboard interface.

    Controls:
    - Arrow keys: Navigate cursor in text
    - Shift+Arrow: Extend selection
    - Enter: Mark chunk (with selection) or confirm category
    - Escape: Cancel pending chunk creation
    - n: Move to next step (directions)
    """

    BINDINGS = [
        Binding("n", "next_step", "Next Step"),
    ]

    def __init__(self, source_file: Path, content: str, state: ProjectState):
        super().__init__()
        self.source_file = source_file
        self.content = content
        self.state = state
        self.mode = SelectionMode.EDITING
        self.pending_chunk: Optional[Chunk] = None

    def compose(self) -> ComposeResult:
        yield Static(f"[bold]MEO - Selection[/bold]  |  {self.source_file.name}", classes="title")
        yield Static(
            "[dim]Select text[/] → [dim]Enter[/] → [dim]Pick category[/] → [dim]Enter[/]  |  [dim]n[/]=next step",
            classes="help-text",
        )

        with Horizontal():
            with Vertical(id="editor-container"):
                yield TextArea(self.content, id="editor", read_only=True)

            with Vertical(id="sidebar"):
                # Category selector (hidden by default)
                yield Static("[bold]Select Category[/bold]", id="category-header", classes="hidden")
                yield ListView(id="category-list", classes="hidden")
                # Chunk list (visible by default)
                yield Static("[bold]Chunks[/bold]", id="chunks-header")
                yield ListView(id="chunks-listview")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the editor and lists"""
        # Populate category list
        category_list = self.query_one("#category-list", ListView)
        for cat in ChunkCategory:
            category_list.append(CategoryListItem(cat))

        # Refresh chunk list
        self._refresh_chunk_list()

        # Focus editor
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

    # ========== Enter Key Handling ==========

    def key_enter(self) -> None:
        """Handle Enter key based on current mode"""
        if self.mode == SelectionMode.EDITING:
            self._start_chunk_creation()
        elif self.mode == SelectionMode.SELECTING_CATEGORY:
            self._confirm_category()

    def _start_chunk_creation(self) -> None:
        """Create pending chunk and switch to category selection mode"""
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
                self.notify(f"Overlaps with {existing.id}", severity="error")
                return

        # Create pending chunk (not yet added to state)
        self.pending_chunk = Chunk(
            id=self.state.next_chunk_id(),
            range=text_range,
            category=ChunkCategory.EDIT,  # default, will be changed
            original_text=selected_text,
        )

        # Switch to category selection mode
        self.mode = SelectionMode.SELECTING_CATEGORY
        self._show_category_selector()

    def _show_category_selector(self) -> None:
        """Show category list and focus it"""
        category_header = self.query_one("#category-header", Static)
        category_list = self.query_one("#category-list", ListView)
        chunks_header = self.query_one("#chunks-header", Static)
        chunks_listview = self.query_one("#chunks-listview", ListView)

        # Show category selector
        category_header.remove_class("hidden")
        category_list.remove_class("hidden")

        # Hide chunk list
        chunks_header.add_class("hidden")
        chunks_listview.add_class("hidden")

        # Focus category list and select first item
        category_list.index = 0
        category_list.focus()

    def _confirm_category(self) -> None:
        """Confirm selected category and finalize chunk"""
        category_list = self.query_one("#category-list", ListView)
        selected_index = category_list.index

        if selected_index is None:
            selected_index = 0

        categories = list(ChunkCategory)
        self.pending_chunk.category = categories[selected_index]

        # Add to state
        self.state.chunks.append(self.pending_chunk)
        chunk_id = self.pending_chunk.id
        self.pending_chunk = None

        # Switch back to editing mode
        self.mode = SelectionMode.EDITING
        self._hide_category_selector()
        self._refresh_chunk_list()
        self.notify(f"Created {chunk_id}")

    def _hide_category_selector(self) -> None:
        """Hide category selector and return to chunk list"""
        category_header = self.query_one("#category-header", Static)
        category_list = self.query_one("#category-list", ListView)
        chunks_header = self.query_one("#chunks-header", Static)
        chunks_listview = self.query_one("#chunks-listview", ListView)

        # Hide category selector
        category_header.add_class("hidden")
        category_list.add_class("hidden")

        # Show chunk list
        chunks_header.remove_class("hidden")
        chunks_listview.remove_class("hidden")

        # Return focus to editor
        editor = self.query_one("#editor", TextArea)
        editor.focus()

    # ========== Escape Key Handling ==========

    def key_escape(self) -> None:
        """Handle Escape key - cancel pending chunk or quit"""
        if self.mode == SelectionMode.SELECTING_CATEGORY:
            self._cancel_chunk_creation()
        # In editing mode, escape does nothing (use 'q' to quit via app)

    def _cancel_chunk_creation(self) -> None:
        """Cancel pending chunk and return to editing"""
        self.pending_chunk = None
        self.mode = SelectionMode.EDITING
        self._hide_category_selector()
        self.notify("Cancelled")

    # ========== Navigation Actions ==========

    def action_next_step(self) -> None:
        """Move to directions screen"""
        if self.mode == SelectionMode.SELECTING_CATEGORY:
            self.notify("Finish selecting category first", severity="warning")
            return

        chunks_needing_direction = self.state.get_chunks_needing_direction()
        if not chunks_needing_direction:
            self.notify("No chunks marked for editing", severity="warning")
            return

        # Assign execution order
        for i, chunk in enumerate(chunks_needing_direction, 1):
            chunk.execution_order = i

        self.app.go_to_directions()

    # ========== Chunk List Interaction ==========

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle chunk selection in list - jump to that location"""
        if self.mode == SelectionMode.EDITING and isinstance(event.item, ChunkListItem):
            chunk = event.item.chunk
            editor = self.query_one("#editor", TextArea)
            # Move cursor to chunk start
            editor.cursor_location = (chunk.range.start.row, chunk.range.start.col)
            editor.focus()
