"""Selection screen - Mark chunks with inline direction assignment"""

from enum import Enum
from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Static, TextArea, Footer, ListView, ListItem, Label, Input

from meo.models.project import ProjectState
from meo.models.chunk import Chunk, ChunkCategory, TextRange, Location
from meo.presets import BUILTIN_PRESETS


class SelectionMode(Enum):
    """State machine for selection screen"""
    EDITING = "editing"
    SELECTING_CATEGORY = "selecting_category"
    SELECTING_DIRECTION = "selecting_direction"
    ENTERING_ANNOTATION = "entering_annotation"


class CategoryListItem(ListItem):
    """A list item representing a chunk category"""

    def __init__(self, category: ChunkCategory):
        super().__init__()
        self.category = category

    def compose(self) -> ComposeResult:
        display_name = self.category.value.replace("_", " ").title()
        yield Label(display_name)


class DirectionListItem(ListItem):
    """A list item representing a direction preset"""

    def __init__(self, preset_id: str, preset_name: str, preset_desc: str):
        super().__init__()
        self.preset_id = preset_id
        self.preset_name = preset_name
        self.preset_desc = preset_desc

    def compose(self) -> ComposeResult:
        yield Label(f"[bold]{self.preset_name}[/bold] - {self.preset_desc}")


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
        preview = self.chunk.original_text[:20].replace("\n", " ")
        if len(self.chunk.original_text) > 20:
            preview += "..."
        direction = self.chunk.direction_preset or "none"
        yield Label(f"[{color}]{self.chunk.id}[/] [{direction}]\n{preview}")


class SelectionScreen(Screen):
    """Screen for selecting and marking chunks with inline directions.

    Flow: Select text → Enter → Category → Enter → Direction → Enter → Annotation → Enter

    Controls:
    - Arrow keys: Navigate cursor/lists
    - Shift+Arrow: Extend selection
    - Enter: Confirm current step
    - Escape: Cancel/go back
    - g: Generate atomic files
    - q: Quit
    """

    BINDINGS = [
        Binding("g", "generate", "Generate"),
    ]

    def __init__(self, source_file: Path, content: str, state: ProjectState):
        super().__init__()
        self.source_file = source_file
        self.content = content
        self.state = state
        self.mode = SelectionMode.EDITING
        self.pending_chunk: Optional[Chunk] = None

    def compose(self) -> ComposeResult:
        yield Static(f"[bold]MEO[/bold]  |  {self.source_file.name}", classes="title")
        yield Static(
            "[dim]Select[/] → Enter → Category → Direction → Annotation  |  [dim]g[/]=generate  [dim]q[/]=quit",
            classes="help-text",
        )

        with Horizontal():
            with Vertical(id="editor-container"):
                yield TextArea(self.content, id="editor", read_only=True)

            with Vertical(id="sidebar"):
                # Category selector (hidden by default)
                yield Static("[bold]Category[/bold]", id="category-header", classes="hidden")
                yield ListView(id="category-list", classes="hidden")

                # Direction selector (hidden by default)
                yield Static("[bold]Direction[/bold]", id="direction-header", classes="hidden")
                yield ListView(id="direction-list", classes="hidden")

                # Annotation input (hidden by default)
                yield Static("[bold]Annotation[/bold] (Enter to skip)", id="annotation-header", classes="hidden")
                yield Input(placeholder="Optional note...", id="annotation-input", classes="hidden")

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

        # Populate direction list
        direction_list = self.query_one("#direction-list", ListView)
        for preset in BUILTIN_PRESETS:
            direction_list.append(DirectionListItem(preset.id, preset.name, preset.description))

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

    # ========== Sidebar Visibility Helpers ==========

    def _hide_all_sidebar_panels(self) -> None:
        """Hide all sidebar panels"""
        for widget_id in ["category-header", "category-list", "direction-header",
                          "direction-list", "annotation-header", "annotation-input",
                          "chunks-header", "chunks-listview"]:
            self.query_one(f"#{widget_id}").add_class("hidden")

    def _show_chunks_panel(self) -> None:
        """Show the chunks panel"""
        self._hide_all_sidebar_panels()
        self.query_one("#chunks-header").remove_class("hidden")
        self.query_one("#chunks-listview").remove_class("hidden")

    def _show_category_panel(self) -> None:
        """Show category selector"""
        self._hide_all_sidebar_panels()
        self.query_one("#category-header").remove_class("hidden")
        category_list = self.query_one("#category-list", ListView)
        category_list.remove_class("hidden")
        category_list.index = 0
        category_list.focus()

    def _show_direction_panel(self) -> None:
        """Show direction selector"""
        self._hide_all_sidebar_panels()
        self.query_one("#direction-header").remove_class("hidden")
        direction_list = self.query_one("#direction-list", ListView)
        direction_list.remove_class("hidden")
        direction_list.index = 0
        direction_list.focus()

    def _show_annotation_panel(self) -> None:
        """Show annotation input"""
        self._hide_all_sidebar_panels()
        self.query_one("#annotation-header").remove_class("hidden")
        annotation_input = self.query_one("#annotation-input", Input)
        annotation_input.remove_class("hidden")
        annotation_input.value = ""
        annotation_input.focus()

    # ========== Enter Key Handling ==========

    def key_enter(self) -> None:
        """Handle Enter key based on current mode"""
        if self.mode == SelectionMode.EDITING:
            self._start_chunk_creation()
        elif self.mode == SelectionMode.SELECTING_CATEGORY:
            self._confirm_category()
        elif self.mode == SelectionMode.SELECTING_DIRECTION:
            self._confirm_direction()
        elif self.mode == SelectionMode.ENTERING_ANNOTATION:
            self._confirm_annotation()

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

        # Create pending chunk
        self.pending_chunk = Chunk(
            id=self.state.next_chunk_id(),
            range=text_range,
            category=ChunkCategory.EDIT,
            original_text=selected_text,
        )

        self.mode = SelectionMode.SELECTING_CATEGORY
        self._show_category_panel()

    def _confirm_category(self) -> None:
        """Confirm category and move to direction selection"""
        category_list = self.query_one("#category-list", ListView)
        selected_index = category_list.index or 0

        categories = list(ChunkCategory)
        self.pending_chunk.category = categories[selected_index]

        # Move to direction selection
        self.mode = SelectionMode.SELECTING_DIRECTION
        self._show_direction_panel()

    def _confirm_direction(self) -> None:
        """Confirm direction and move to annotation"""
        direction_list = self.query_one("#direction-list", ListView)
        selected_index = direction_list.index or 0

        if selected_index < len(BUILTIN_PRESETS):
            self.pending_chunk.direction_preset = BUILTIN_PRESETS[selected_index].id

        # Move to annotation
        self.mode = SelectionMode.ENTERING_ANNOTATION
        self._show_annotation_panel()

    def _confirm_annotation(self) -> None:
        """Confirm annotation and finalize chunk"""
        annotation_input = self.query_one("#annotation-input", Input)
        annotation = annotation_input.value.strip()

        if annotation:
            self.pending_chunk.annotation = annotation

        # Finalize chunk
        self.state.chunks.append(self.pending_chunk)
        chunk_id = self.pending_chunk.id
        self.pending_chunk = None

        # Return to editing
        self.mode = SelectionMode.EDITING
        self._show_chunks_panel()
        self._refresh_chunk_list()

        editor = self.query_one("#editor", TextArea)
        editor.focus()

        self.notify(f"Created {chunk_id}")

    # ========== Escape Key Handling ==========

    def key_escape(self) -> None:
        """Handle Escape key - go back one step or cancel"""
        if self.mode == SelectionMode.SELECTING_CATEGORY:
            self._cancel_chunk_creation()
        elif self.mode == SelectionMode.SELECTING_DIRECTION:
            # Go back to category
            self.mode = SelectionMode.SELECTING_CATEGORY
            self._show_category_panel()
        elif self.mode == SelectionMode.ENTERING_ANNOTATION:
            # Go back to direction
            self.mode = SelectionMode.SELECTING_DIRECTION
            self._show_direction_panel()

    def _cancel_chunk_creation(self) -> None:
        """Cancel pending chunk and return to editing"""
        self.pending_chunk = None
        self.mode = SelectionMode.EDITING
        self._show_chunks_panel()

        editor = self.query_one("#editor", TextArea)
        editor.focus()

        self.notify("Cancelled")

    # ========== Generate Action ==========

    def action_generate(self) -> None:
        """Generate atomic files for all chunks"""
        if self.mode != SelectionMode.EDITING:
            self.notify("Finish current chunk first", severity="warning")
            return

        if not self.state.chunks:
            self.notify("No chunks defined", severity="warning")
            return

        # Import here to avoid circular imports
        from meo.core.session import create_session

        try:
            session = create_session(self.source_file, self.state)
            self.app.exit(message=f"Session created: .meo/sessions/{session.id}")
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")

    # ========== Chunk List Interaction ==========

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle chunk selection in list - jump to that location"""
        if self.mode == SelectionMode.EDITING and isinstance(event.item, ChunkListItem):
            chunk = event.item.chunk
            editor = self.query_one("#editor", TextArea)
            editor.cursor_location = (chunk.range.start.row, chunk.range.start.col)
            editor.focus()
