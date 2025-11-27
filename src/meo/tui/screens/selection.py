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
from meo.models.chunk import Chunk, ChunkCategory, LockType, TextRange, Location
from meo.presets import BUILTIN_PRESETS
from meo.tui.widgets import GenerateConfirmModal


class SelectionMode(Enum):
    """State machine for selection screen"""
    EDITING = "editing"
    SELECTING_ACTION = "selecting_action"
    SELECTING_DIRECTION = "selecting_direction"
    SELECTING_LOCK_TYPE = "selecting_lock_type"
    ENTERING_ANNOTATION = "entering_annotation"


class ActionListItem(ListItem):
    """A list item representing a chunk action (Replace/Tweak/Lock)"""

    def __init__(self, action: str, category: ChunkCategory, description: str):
        super().__init__()
        self.action = action
        self.category = category
        self.description = description

    def compose(self) -> ComposeResult:
        yield Label(f"[bold]{self.action}[/bold] - {self.description}")


class LockTypeListItem(ListItem):
    """A list item representing a lock type"""

    def __init__(self, lock_type: LockType, description: str):
        super().__init__()
        self.lock_type = lock_type
        self.description = description

    def compose(self) -> ComposeResult:
        yield Label(f"[bold]{self.lock_type.value.title()}[/bold] - {self.description}")


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
            ChunkCategory.REPLACE: "green",
            ChunkCategory.TWEAK: "cyan",
            ChunkCategory.LOCK: "dim",
        }
        color = category_colors.get(self.chunk.category, "white")
        preview = self.chunk.original_text[:20].replace("\n", " ")
        if len(self.chunk.original_text) > 20:
            preview += "..."
        # Show direction for replace/tweak, lock_type for locked chunks
        if self.chunk.category == ChunkCategory.LOCK:
            detail = self.chunk.lock_type.value if self.chunk.lock_type else "lock"
        else:
            detail = self.chunk.direction_preset or "none"
        yield Label(f"[{color}]{self.chunk.id}[/] [{detail}]\n{preview}")


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
        Binding("d", "delete_chunk", "Delete Chunk"),
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
            "[dim]Select[/] → Enter → Action → Direction/LockType → Annotation  |  [dim]g[/]=generate  [dim]d[/]=delete  [dim]q[/]=quit",
            classes="help-text",
        )

        with Horizontal():
            with Vertical(id="editor-container"):
                yield TextArea(self.content, id="editor", read_only=True)

            with Vertical(id="sidebar"):
                # Action selector (hidden by default)
                yield Static("[bold]Action[/bold]", id="action-header", classes="hidden")
                yield ListView(id="action-list", classes="hidden")

                # Direction selector (hidden by default)
                yield Static("[bold]Direction[/bold]", id="direction-header", classes="hidden")
                yield ListView(id="direction-list", classes="hidden")

                # Lock type selector (hidden by default)
                yield Static("[bold]Lock Type[/bold]", id="lock-type-header", classes="hidden")
                yield ListView(id="lock-type-list", classes="hidden")

                # Annotation input (hidden by default)
                yield Static("[bold]Annotation[/bold] (Enter to skip)", id="annotation-header", classes="hidden")
                yield Input(placeholder="Optional note...", id="annotation-input", classes="hidden")

                # Chunk list (visible by default)
                yield Static("[bold]Chunks[/bold]", id="chunks-header")
                yield ListView(id="chunks-listview")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the editor and lists"""
        # Populate action list
        action_list = self.query_one("#action-list", ListView)
        action_list.append(ActionListItem("Replace", ChunkCategory.REPLACE, "Edit or rewrite this text"))
        action_list.append(ActionListItem("Tweak", ChunkCategory.TWEAK, "Minor adjustments only"))
        action_list.append(ActionListItem("Lock", ChunkCategory.LOCK, "Use as context for other chunks"))

        # Populate direction list
        direction_list = self.query_one("#direction-list", ListView)
        for preset in BUILTIN_PRESETS:
            direction_list.append(DirectionListItem(preset.id, preset.name, preset.description))

        # Populate lock type list
        lock_type_list = self.query_one("#lock-type-list", ListView)
        lock_type_list.append(LockTypeListItem(LockType.EXAMPLE, "Match this style/format"))
        lock_type_list.append(LockTypeListItem(LockType.REFERENCE, "Use this information"))
        lock_type_list.append(LockTypeListItem(LockType.CONTEXT, "Background awareness only"))

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
        for widget_id in ["action-header", "action-list", "direction-header",
                          "direction-list", "lock-type-header", "lock-type-list",
                          "annotation-header", "annotation-input",
                          "chunks-header", "chunks-listview"]:
            self.query_one(f"#{widget_id}").add_class("hidden")

    def _show_chunks_panel(self) -> None:
        """Show the chunks panel"""
        self._hide_all_sidebar_panels()
        self.query_one("#chunks-header").remove_class("hidden")
        self.query_one("#chunks-listview").remove_class("hidden")

    def _show_action_panel(self) -> None:
        """Show action selector (Replace/Tweak/Lock)"""
        self._hide_all_sidebar_panels()
        self.query_one("#action-header").remove_class("hidden")
        action_list = self.query_one("#action-list", ListView)
        action_list.remove_class("hidden")
        action_list.index = 0
        action_list.focus()

    def _show_direction_panel(self) -> None:
        """Show direction selector"""
        self._hide_all_sidebar_panels()
        self.query_one("#direction-header").remove_class("hidden")
        direction_list = self.query_one("#direction-list", ListView)
        direction_list.remove_class("hidden")
        direction_list.index = 0
        direction_list.focus()

    def _show_lock_type_panel(self) -> None:
        """Show lock type selector"""
        self._hide_all_sidebar_panels()
        self.query_one("#lock-type-header").remove_class("hidden")
        lock_type_list = self.query_one("#lock-type-list", ListView)
        lock_type_list.remove_class("hidden")
        lock_type_list.index = 0
        lock_type_list.focus()

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
        elif self.mode == SelectionMode.SELECTING_ACTION:
            self._confirm_action()
        elif self.mode == SelectionMode.SELECTING_DIRECTION:
            self._confirm_direction()
        elif self.mode == SelectionMode.SELECTING_LOCK_TYPE:
            self._confirm_lock_type()
        elif self.mode == SelectionMode.ENTERING_ANNOTATION:
            self._confirm_annotation()

    def _start_chunk_creation(self) -> None:
        """Create pending chunk and switch to action selection mode"""
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
            category=ChunkCategory.REPLACE,
            original_text=selected_text,
        )

        self.mode = SelectionMode.SELECTING_ACTION
        self._show_action_panel()

    def _confirm_action(self) -> None:
        """Confirm action and move to direction selection or lock type selection"""
        action_list = self.query_one("#action-list", ListView)
        selected_index = action_list.index or 0

        # Get the selected action item
        action_item = action_list.children[selected_index]
        if isinstance(action_item, ActionListItem):
            self.pending_chunk.category = action_item.category

        # Branch based on action type
        if self.pending_chunk.category == ChunkCategory.LOCK:
            # Lock goes to lock type selection
            self.mode = SelectionMode.SELECTING_LOCK_TYPE
            self._show_lock_type_panel()
        else:
            # Replace/Tweak go to direction selection
            self.mode = SelectionMode.SELECTING_DIRECTION
            self._show_direction_panel()

    def _confirm_lock_type(self) -> None:
        """Confirm lock type and move to annotation"""
        lock_type_list = self.query_one("#lock-type-list", ListView)
        selected_index = lock_type_list.index or 0

        # Get the selected lock type item
        lock_type_item = lock_type_list.children[selected_index]
        if isinstance(lock_type_item, LockTypeListItem):
            self.pending_chunk.lock_type = lock_type_item.lock_type

        # Move to annotation
        self.mode = SelectionMode.ENTERING_ANNOTATION
        self._show_annotation_panel()

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
        if self.mode == SelectionMode.SELECTING_ACTION:
            self._cancel_chunk_creation()
        elif self.mode == SelectionMode.SELECTING_DIRECTION:
            # Go back to action
            self.mode = SelectionMode.SELECTING_ACTION
            self._show_action_panel()
        elif self.mode == SelectionMode.SELECTING_LOCK_TYPE:
            # Go back to action
            self.mode = SelectionMode.SELECTING_ACTION
            self._show_action_panel()
        elif self.mode == SelectionMode.ENTERING_ANNOTATION:
            # Go back to direction or lock type depending on category
            if self.pending_chunk.category == ChunkCategory.LOCK:
                self.mode = SelectionMode.SELECTING_LOCK_TYPE
                self._show_lock_type_panel()
            else:
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

        # Check for at least one non-locked chunk
        non_locked = [c for c in self.state.chunks if c.category != ChunkCategory.LOCK]
        if not non_locked:
            self.notify("Need at least one non-locked chunk", severity="warning")
            return

        # Show confirmation modal with only non-locked chunk IDs
        chunk_ids = [c.id for c in non_locked]

        def handle_confirm(confirmed: bool) -> None:
            if confirmed:
                self.app.generate_edit_and_review()

        self.app.push_screen(GenerateConfirmModal(chunk_ids), handle_confirm)

    # ========== Delete Chunk ==========

    def action_delete_chunk(self) -> None:
        """Delete the selected chunk from the list"""
        if self.mode != SelectionMode.EDITING:
            self.notify("Finish current chunk first", severity="warning")
            return

        if not self.state.chunks:
            self.notify("No chunks to delete", severity="warning")
            return

        listview = self.query_one("#chunks-listview", ListView)
        if listview.index is None:
            self.notify("Select a chunk first", severity="warning")
            return

        selected_index = listview.index
        if 0 <= selected_index < len(self.state.chunks):
            chunk = self.state.chunks[selected_index]
            chunk_id = chunk.id
            self.state.chunks.pop(selected_index)
            self._refresh_chunk_list()
            self.notify(f"Deleted {chunk_id}")

    # ========== Chunk List Interaction ==========

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle chunk selection in list - jump to that location"""
        if self.mode == SelectionMode.EDITING and isinstance(event.item, ChunkListItem):
            chunk = event.item.chunk
            editor = self.query_one("#editor", TextArea)
            editor.cursor_location = (chunk.range.start.row, chunk.range.start.col)
            editor.focus()
