"""Selection screen - Mark chunks with inline direction assignment"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, List, Literal

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Static, TextArea, Footer, ListView, ListItem, Label, Input, ProgressBar
from textual import work

from meo.models.project import ProjectState
from meo.models.session import Session
from meo.models.chunk import Chunk, ChunkCategory, LockType, TextRange, Location
from meo.presets import REPLACE_PRESETS, TWEAK_PRESETS
from meo.tui.widgets import GenerateConfirmModal
from meo.core.session import create_session, get_session_path, save_session
from meo.core.chunk_parser import parse_chunk_file, ChunkData
from meo.core.text_replacer import apply_chunk_to_working, apply_chunk_to_file
from meo.core.git_ops import commit_chunk_response
from meo.core.ai_edit_streaming import stream_ai_edit_on_session, StreamProgress
from meo.core.sidecar import load_sidecar, save_sidecar


class SelectionMode(Enum):
    """State machine for selection screen"""
    # Chunk creation modes
    EDITING = "editing"
    SELECTING_ACTION = "selecting_action"
    SELECTING_DIRECTION = "selecting_direction"
    SELECTING_LOCK_TYPE = "selecting_lock_type"
    ENTERING_ANNOTATION = "entering_annotation"
    # Processing and review modes
    PROCESSING = "processing"
    REVIEWING = "reviewing"
    REVIEW_EDITING = "review_editing"


class ReviewChoice(Enum):
    """Current selection state during review"""
    APPROVE = "approve"
    DENY = "deny"


@dataclass
class ReviewChunk:
    """Data for a chunk being reviewed"""
    chunk_id: str
    chunk_data: Optional[ChunkData]
    error: Optional[str] = None
    decision: Literal["pending", "approved", "denied"] = "pending"


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

        # Processing state
        self.session: Optional[Session] = None
        self.session_path: Optional[Path] = None
        self._processing_cancelled = False

        # Review state
        self.review_chunks: List[ReviewChunk] = []
        self.review_index: int = 0
        self.review_choice: ReviewChoice = ReviewChoice.APPROVE
        self.working_content: str = ""

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

                # Processing panel (hidden by default)
                yield Static("[bold]Processing[/bold]", id="processing-header", classes="hidden")
                yield ProgressBar(total=100, show_eta=True, id="processing-progress", classes="hidden")
                yield Static("Starting...", id="processing-status", classes="hidden")
                yield TextArea(id="processing-stream", read_only=True, classes="hidden")

                # Review panel (hidden by default)
                yield Static("[bold]Review[/bold]", id="review-header", classes="hidden")
                yield Static("", id="review-chunk-info", classes="hidden")
                yield Static("", id="review-choice-display", classes="hidden")
                yield TextArea(id="review-sidebar-text", read_only=True, classes="hidden")
                yield Static("[dim]<-/-> Approve/Deny | Enter confirm | e edit | Up/Down nav[/dim]", id="review-help", classes="hidden")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the editor and lists"""
        # Populate action list
        action_list = self.query_one("#action-list", ListView)
        action_list.append(ActionListItem("Replace", ChunkCategory.REPLACE, "Rewrite this text"))
        action_list.append(ActionListItem("Tweak", ChunkCategory.TWEAK, "Minor adjustments"))
        action_list.append(ActionListItem("Lock", ChunkCategory.LOCK, "Context for other chunks"))

        # Direction list is populated dynamically based on action (Replace vs Tweak)

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

    def _populate_direction_list(self, category: ChunkCategory) -> None:
        """Populate direction list based on chunk category"""
        direction_list = self.query_one("#direction-list", ListView)
        direction_list.clear()

        presets = REPLACE_PRESETS if category == ChunkCategory.REPLACE else TWEAK_PRESETS
        for preset in presets:
            direction_list.append(DirectionListItem(preset.id, preset.name, preset.description))

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
        for widget_id in [
            # Chunk creation panels
            "action-header", "action-list",
            "direction-header", "direction-list",
            "lock-type-header", "lock-type-list",
            "annotation-header", "annotation-input",
            "chunks-header", "chunks-listview",
            # Processing panel
            "processing-header", "processing-progress", "processing-status", "processing-stream",
            # Review panel
            "review-header", "review-chunk-info", "review-choice-display",
            "review-sidebar-text", "review-help",
        ]:
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

    def _show_processing_panel(self) -> None:
        """Show the processing panel"""
        self._hide_all_sidebar_panels()
        for widget_id in ["processing-header", "processing-progress",
                          "processing-status", "processing-stream"]:
            self.query_one(f"#{widget_id}").remove_class("hidden")

    def _show_review_panel(self) -> None:
        """Show the review panel"""
        self._hide_all_sidebar_panels()
        for widget_id in ["review-header", "review-chunk-info", "review-choice-display",
                          "review-sidebar-text", "review-help"]:
            self.query_one(f"#{widget_id}").remove_class("hidden")

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
        elif self.mode == SelectionMode.REVIEWING:
            self._confirm_review_choice()
        elif self.mode == SelectionMode.REVIEW_EDITING:
            self._save_review_edit()

    def _confirm_review_choice(self) -> None:
        """Confirm current review choice (approve or deny)"""
        if self.review_choice == ReviewChoice.APPROVE:
            self._approve_current_chunk()
        else:
            self._deny_current_chunk()

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
            # Replace/Tweak go to direction selection with category-specific presets
            self._populate_direction_list(self.pending_chunk.category)
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

        # Get preset from category-specific list
        presets = REPLACE_PRESETS if self.pending_chunk.category == ChunkCategory.REPLACE else TWEAK_PRESETS
        if selected_index < len(presets):
            self.pending_chunk.direction_preset = presets[selected_index].id

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
        elif self.mode == SelectionMode.PROCESSING:
            self._cancel_processing()
        elif self.mode == SelectionMode.REVIEWING:
            # Block escape - must complete all chunks
            pending = sum(1 for c in self.review_chunks if c.decision == "pending")
            self.notify(f"Must complete review ({pending} pending)", severity="warning")
        elif self.mode == SelectionMode.REVIEW_EDITING:
            self._cancel_review_edit()

    def key_left(self) -> None:
        """Handle Left arrow key"""
        if self.mode == SelectionMode.REVIEWING:
            chunk = self._get_current_review_chunk()
            if chunk and chunk.decision == "pending":
                self.review_choice = ReviewChoice.APPROVE
                self._update_review_display()

    def key_right(self) -> None:
        """Handle Right arrow key"""
        if self.mode == SelectionMode.REVIEWING:
            chunk = self._get_current_review_chunk()
            if chunk and chunk.decision == "pending":
                self.review_choice = ReviewChoice.DENY
                self._update_review_display()

    def key_up(self) -> None:
        """Handle Up arrow key"""
        if self.mode == SelectionMode.REVIEWING:
            self._navigate_review_prev()

    def key_down(self) -> None:
        """Handle Down arrow key"""
        if self.mode == SelectionMode.REVIEWING:
            self._navigate_review_next()

    def key_e(self) -> None:
        """Handle 'e' key for edit toggle"""
        if self.mode in (SelectionMode.REVIEWING, SelectionMode.REVIEW_EDITING):
            self._toggle_review_edit()

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
                self._start_processing()

        self.app.push_screen(GenerateConfirmModal(chunk_ids), handle_confirm)

    def _start_processing(self) -> None:
        """Begin AI processing phase inline"""
        # Create session
        self.session = create_session(self.source_file, self.state)
        self.session_path = get_session_path(self.session.id)
        save_sidecar(self.source_file, self.state)

        # Reset processing state
        self._processing_cancelled = False

        # Switch to processing mode
        self.mode = SelectionMode.PROCESSING
        self._show_processing_panel()

        # Initialize progress bar
        total_chunks = len(self.session.chunks)
        progress_bar = self.query_one("#processing-progress", ProgressBar)
        progress_bar.total = total_chunks
        progress_bar.progress = 0

        # Update status
        status = self.query_one("#processing-status", Static)
        status.update(f"Processing {total_chunks} chunk(s)...")

        # Start background worker
        self._run_processing()

    @work(thread=True)
    def _run_processing(self) -> None:
        """Run AI edit in background thread with async event loop"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(
                stream_ai_edit_on_session(
                    self.session.id,
                    self._on_processing_progress
                )
            )
        finally:
            loop.close()

        # Signal completion on main thread
        if not self._processing_cancelled:
            self.app.call_from_thread(self._processing_complete)

    def _on_processing_progress(self, progress: StreamProgress) -> None:
        """Handle progress updates from streaming worker (called from worker thread)"""
        if self._processing_cancelled:
            return
        self.app.call_from_thread(self._update_processing_ui, progress)

    def _update_processing_ui(self, progress: StreamProgress) -> None:
        """Update processing UI elements (called on main thread)"""
        if self.mode != SelectionMode.PROCESSING:
            return

        # Update progress bar
        progress_bar = self.query_one("#processing-progress", ProgressBar)
        if progress.status == "complete":
            progress_bar.progress = progress.chunk_index + 1
        elif progress.status == "streaming":
            progress_bar.progress = progress.chunk_index + 0.5
        else:
            progress_bar.progress = progress.chunk_index

        # Update status text
        status = self.query_one("#processing-status", Static)
        status_text = f"Chunk {progress.chunk_index + 1}/{progress.total_chunks}: {progress.chunk_id}"
        if progress.status == "starting":
            status_text += " [dim](starting...)[/dim]"
        elif progress.status == "streaming":
            status_text += " [cyan](receiving...)[/cyan]"
        elif progress.status == "complete":
            status_text += " [green](complete)[/green]"
        elif progress.status == "error":
            status_text += " [red](error)[/red]"
        status.update(status_text)

        # Update stream output
        stream_output = self.query_one("#processing-stream", TextArea)
        if progress.status == "starting":
            stream_output.text = f"--- Processing {progress.chunk_id} ---\n"
        elif progress.status == "streaming":
            stream_output.text = f"--- {progress.chunk_id} ---\n{progress.text}"
            stream_output.scroll_end(animate=False)

    def _processing_complete(self) -> None:
        """Transition from processing to review mode"""
        self._load_review_data()

        if not self.review_chunks:
            self.notify("No chunks to review")
            self.mode = SelectionMode.EDITING
            self._show_chunks_panel()
            return

        # Disable editor focus so arrow keys go to screen bindings
        editor = self.query_one("#editor", TextArea)
        editor.can_focus = False

        # Switch to review mode
        self.mode = SelectionMode.REVIEWING
        self.review_index = 0
        self.review_choice = ReviewChoice.APPROVE
        self._show_review_panel()
        self._update_review_display()

    def _cancel_processing(self) -> None:
        """Cancel the processing operation"""
        self._processing_cancelled = True
        self.notify("Processing cancelled", severity="warning")
        self.mode = SelectionMode.EDITING
        self._show_chunks_panel()
        self.query_one("#editor", TextArea).focus()

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

    # ========== Review Phase ==========

    def _load_review_data(self) -> None:
        """Load all pending chunks for review"""
        self.review_chunks = []
        pending_ids = self.session.get_pending_chunks()

        for chunk_id in pending_ids:
            chunk_path = self.session_path / "chunks" / f"{chunk_id}.md"
            try:
                if chunk_path.exists():
                    chunk_data = parse_chunk_file(chunk_path)
                    self.review_chunks.append(ReviewChunk(chunk_id, chunk_data))
                else:
                    self.review_chunks.append(
                        ReviewChunk(chunk_id, None, f"File not found: {chunk_path}")
                    )
            except Exception as e:
                self.review_chunks.append(ReviewChunk(chunk_id, None, str(e)))

        # Load working content for document context
        working_file = self.session_path / "working.md"
        if working_file.exists():
            self.working_content = working_file.read_text()

    def _get_current_review_chunk(self) -> Optional[ReviewChunk]:
        """Get the current chunk being reviewed"""
        if 0 <= self.review_index < len(self.review_chunks):
            return self.review_chunks[self.review_index]
        return None

    def _build_document_with_highlight(
        self,
        original_text: str,
        replacement_text: str,
        show_replacement: bool
    ) -> str:
        """Build full document with highlighted section"""
        content = self.working_content
        display_text = replacement_text if show_replacement else original_text

        # Try exact match first
        if original_text in content:
            return content.replace(
                original_text,
                f">>> REVIEWING >>>\n{display_text}\n<<< REVIEWING <<<",
                1
            )

        # Try normalized match
        normalized_original = original_text.strip()
        normalized_content = content.replace('\r\n', '\n')
        if normalized_original and normalized_original in normalized_content:
            return normalized_content.replace(
                normalized_original,
                f">>> REVIEWING >>>\n{display_text}\n<<< REVIEWING <<<",
                1
            )

        # Fallback
        return f">>> REVIEWING >>> (location changed)\n{display_text}\n<<< REVIEWING <<<\n\n---\n\n{content}"

    def _scroll_editor_to_marker(self) -> None:
        """Scroll editor to show the review marker at top of viewport"""
        def do_scroll():
            editor = self.query_one("#editor", TextArea)
            lines = editor.text.split('\n')
            for i, line in enumerate(lines):
                if '>>> REVIEWING >>>' in line:
                    editor.scroll_to(0, i, animate=False)
                    return
        # Use set_timer to ensure scroll happens after text rendering
        self.set_timer(0.05, do_scroll)

    def _update_review_display(self) -> None:
        """Update the main editor and sidebar for current review chunk"""
        chunk = self._get_current_review_chunk()

        # Update chunk info
        info = self.query_one("#review-chunk-info", Static)
        if chunk:
            total = len(self.review_chunks)
            current = self.review_index + 1
            category = chunk.chunk_data.category if chunk.chunk_data else "Unknown"
            decided = sum(1 for c in self.review_chunks if c.decision != "pending")
            info.update(f"Chunk {current}/{total}: {chunk.chunk_id} [{category}]  |  Decided: {decided}/{total}")
        else:
            info.update("No chunks to review")

        # Update choice display
        choice_display = self.query_one("#review-choice-display", Static)
        if chunk and chunk.decision != "pending":
            # Already decided - show decision
            if chunk.decision == "approved":
                choice_display.update("[green bold]APPROVED[/]")
            else:
                choice_display.update("[red bold]DENIED[/]")
        elif self.review_choice == ReviewChoice.APPROVE:
            choice_display.update("[reverse bold green] APPROVE [/]    [dim] DENY [/dim]")
        else:
            choice_display.update("[dim] APPROVE [/dim]    [reverse bold red] DENY [/]")

        # Update main editor and sidebar
        editor = self.query_one("#editor", TextArea)
        sidebar_text = self.query_one("#review-sidebar-text", TextArea)

        if chunk and chunk.chunk_data:
            original = chunk.chunk_data.original_text
            ai_response = chunk.chunk_data.ai_response or "[No AI response]"

            if self.review_choice == ReviewChoice.APPROVE:
                # Main shows AI change in markers, sidebar shows original
                editor.text = self._build_document_with_highlight(original, ai_response, show_replacement=True)
                sidebar_text.text = original
            else:
                # Main shows original in markers, sidebar shows AI response
                editor.text = self._build_document_with_highlight(original, ai_response, show_replacement=False)
                sidebar_text.text = ai_response
        elif chunk and chunk.error:
            editor.text = f"Error loading chunk: {chunk.error}"
            sidebar_text.text = ""
        else:
            editor.text = "No chunk data"
            sidebar_text.text = ""

        # Scroll to review marker
        self._scroll_editor_to_marker()

    def _approve_current_chunk(self) -> None:
        """Approve and apply the current chunk"""
        chunk = self._get_current_review_chunk()
        if not chunk:
            return

        if chunk.decision != "pending":
            self.notify("Already decided", severity="warning")
            return

        if not chunk.chunk_data or not chunk.chunk_data.has_response:
            self.notify("Cannot approve: no AI response", severity="warning")
            return

        # Apply to working.md
        success = apply_chunk_to_working(
            self.session_path,
            chunk.chunk_data.original_text,
            chunk.chunk_data.ai_response or ""
        )

        if not success:
            self.notify("Failed to apply: text not found", severity="error")
            return

        # Apply to source file
        apply_chunk_to_file(
            self.source_file,
            chunk.chunk_data.original_text,
            chunk.chunk_data.ai_response or ""
        )

        # Git commit
        try:
            commit_chunk_response(self.session_path, chunk.chunk_id)
        except Exception as e:
            self.notify(f"Git commit failed: {e}", severity="error")
            return

        # Update session and chunk decision
        self.session.mark_chunk_applied(chunk.chunk_id)
        save_session(self.session, self.session_path)
        chunk.decision = "approved"

        # Reload working content and source content
        self.working_content = (self.session_path / "working.md").read_text()
        self.content = self.source_file.read_text()

        self.notify(f"Applied {chunk.chunk_id}")
        self._check_review_complete()

    def _deny_current_chunk(self) -> None:
        """Deny/skip the current chunk"""
        chunk = self._get_current_review_chunk()
        if not chunk:
            return

        if chunk.decision != "pending":
            self.notify("Already decided", severity="warning")
            return

        self.session.mark_chunk_skipped(chunk.chunk_id)
        save_session(self.session, self.session_path)
        chunk.decision = "denied"

        self.notify(f"Skipped {chunk.chunk_id}")
        self._check_review_complete()

    def _check_review_complete(self) -> None:
        """Check if all chunks are decided and complete if so"""
        pending = sum(1 for c in self.review_chunks if c.decision == "pending")
        if pending == 0:
            self._complete_review()
        else:
            # Move to next undecided chunk if possible
            self._advance_to_next_pending()
            self._update_review_display()

    def _advance_to_next_pending(self) -> None:
        """Advance to the next pending chunk"""
        # Try forward first
        for i in range(self.review_index + 1, len(self.review_chunks)):
            if self.review_chunks[i].decision == "pending":
                self.review_index = i
                self.review_choice = ReviewChoice.APPROVE
                return
        # Then wrap around
        for i in range(0, self.review_index):
            if self.review_chunks[i].decision == "pending":
                self.review_index = i
                self.review_choice = ReviewChoice.APPROVE
                return

    def _complete_review(self) -> None:
        """Complete review and return to editing mode"""
        applied = len(self.session.applied_chunks)
        skipped = len(self.session.skipped_chunks)

        self.session.status = "complete"
        save_session(self.session, self.session_path)

        # Reload source content
        self.content = self.source_file.read_text()

        # Clear chunks from sidecar
        state = load_sidecar(self.source_file)
        if state:
            state.chunks = []
            save_sidecar(self.source_file, state)
            self.state = state

        # Update editor with new content and re-enable focus
        editor = self.query_one("#editor", TextArea)
        editor.text = self.content
        editor.can_focus = True

        self.notify(f"Review complete! Applied: {applied}, Skipped: {skipped}")

        # Return to editing mode
        self.mode = SelectionMode.EDITING
        self._show_chunks_panel()
        self._refresh_chunk_list()
        editor.focus()

    def _navigate_review_prev(self) -> None:
        """Navigate to previous chunk in review"""
        if self.review_index > 0:
            self.review_index -= 1
            self.review_choice = ReviewChoice.APPROVE
            self._update_review_display()

    def _navigate_review_next(self) -> None:
        """Navigate to next chunk in review"""
        if self.review_index < len(self.review_chunks) - 1:
            self.review_index += 1
            self.review_choice = ReviewChoice.APPROVE
            self._update_review_display()

    # ========== Review Editing ==========

    def _toggle_review_edit(self) -> None:
        """Toggle edit mode for review sidebar"""
        if self.mode == SelectionMode.REVIEW_EDITING:
            self._cancel_review_edit()
            return

        if self.mode != SelectionMode.REVIEWING:
            return

        chunk = self._get_current_review_chunk()
        if not chunk or chunk.decision != "pending":
            self.notify("Cannot edit: chunk already decided", severity="warning")
            return

        self.mode = SelectionMode.REVIEW_EDITING

        sidebar_text = self.query_one("#review-sidebar-text", TextArea)
        sidebar_text.read_only = False
        sidebar_text.can_focus = True
        sidebar_text.focus()

        sidebar_text.add_class("editing-mode")

    def _save_review_edit(self) -> None:
        """Save the edited sidebar content"""
        sidebar_text = self.query_one("#review-sidebar-text", TextArea)
        edited_content = sidebar_text.text

        chunk = self._get_current_review_chunk()
        if chunk and chunk.chunk_data:
            if self.review_choice == ReviewChoice.APPROVE:
                # Sidebar shows original when Approve selected
                chunk.chunk_data.original_text = edited_content
            else:
                # Sidebar shows AI response when Deny selected
                chunk.chunk_data.ai_response = edited_content

        sidebar_text.read_only = True
        sidebar_text.can_focus = False
        sidebar_text.remove_class("editing-mode")

        self.mode = SelectionMode.REVIEWING
        self._update_review_display()
        self.notify("Edit saved")

    def _cancel_review_edit(self) -> None:
        """Cancel edit without saving"""
        sidebar_text = self.query_one("#review-sidebar-text", TextArea)
        sidebar_text.read_only = True
        sidebar_text.can_focus = False
        sidebar_text.remove_class("editing-mode")

        self.mode = SelectionMode.REVIEWING
        self._update_review_display()
        self.notify("Edit cancelled")
