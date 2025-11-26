"""Refactored Review Screen - Document context with highlighted changes"""

from enum import Enum
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Static, TextArea, Footer

from meo.models.session import Session
from meo.core.session import save_session
from meo.core.chunk_parser import parse_chunk_file, ChunkData
from meo.core.text_replacer import apply_chunk_to_working, apply_chunk_to_file
from meo.core.git_ops import commit_chunk_response


class ReviewChoice(Enum):
    """Current hover/selection state"""
    APPROVE = "approve"
    DENY = "deny"


class EditTarget(Enum):
    """Which panel is being edited"""
    NONE = "none"
    SIDEBAR = "sidebar"


@dataclass
class ReviewChunk:
    """Data for a chunk being reviewed"""
    chunk_id: str
    chunk_data: Optional[ChunkData]
    error: Optional[str] = None


class ReviewScreenV2(Screen):
    """Refactored review screen with document context view.

    - Main panel: Full document with changed section highlighted
    - Sidebar: Alternate version of the chunk
    - Arrow keys: Select Approve/Deny
    - Enter: Confirm selection
    - 'e': Edit sidebar content
    """

    CSS = """
    #header {
        text-style: bold;
        padding: 1 2;
        background: $primary;
        color: $text;
    }

    #chunk-info {
        padding: 0 2;
        color: $text-muted;
    }

    #main-container {
        height: 1fr;
        margin: 1;
    }

    #main-panel {
        width: 70%;
        border: solid $secondary;
    }

    #sidebar-panel {
        width: 30%;
        border: solid $accent;
        margin-left: 1;
    }

    .panel-title {
        background: $surface-darken-1;
        padding: 0 1;
        text-align: center;
        text-style: bold;
    }

    #main-text, #sidebar-text {
        height: 1fr;
        border: none;
    }

    #choice-bar {
        height: 3;
        align: center middle;
        padding: 0 2;
    }

    #status-bar {
        padding: 0 2;
        background: $surface-darken-1;
    }

    .editing-mode {
        border: double $warning !important;
    }

    #help-bar {
        padding: 0 2;
        color: $text-muted;
        text-align: center;
    }
    """

    BINDINGS = [
        Binding("left", "select_approve", "Approve", show=False),
        Binding("right", "select_deny", "Deny", show=False),
        Binding("enter", "confirm_choice", "Confirm"),
        Binding("e", "toggle_edit", "Edit"),
        Binding("escape", "cancel_edit_or_quit", "Cancel/Quit"),
        Binding("up", "prev_chunk", "Previous", show=False),
        Binding("down", "next_chunk", "Next", show=False),
    ]

    def __init__(self, session: Session, session_path: Path):
        super().__init__()
        self.session = session
        self.session_path = session_path
        self.pending_chunks: List[str] = session.get_pending_chunks()
        self.current_index = 0
        self.review_chunks: List[ReviewChunk] = []
        self.choice = ReviewChoice.APPROVE
        self.edit_target = EditTarget.NONE
        self.working_content = ""
        self._load_all_chunks()
        self._load_working_content()

    def _load_all_chunks(self) -> None:
        """Load all pending chunk data"""
        for chunk_id in self.pending_chunks:
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

    def _load_working_content(self) -> None:
        """Load the full working document"""
        working_file = self.session_path / "working.md"
        if working_file.exists():
            self.working_content = working_file.read_text()

    def compose(self) -> ComposeResult:
        yield Static(id="header")
        yield Static(id="chunk-info")

        with Horizontal(id="main-container"):
            with Vertical(id="main-panel"):
                yield Static("[bold]DOCUMENT[/bold]", id="main-title", classes="panel-title")
                # Disable focus so arrow keys go to screen bindings
                main_text = TextArea(id="main-text", read_only=True)
                main_text.can_focus = False
                yield main_text

            with Vertical(id="sidebar-panel"):
                yield Static("[bold]ALTERNATE[/bold]", id="sidebar-title", classes="panel-title")
                # Disable focus so arrow keys go to screen bindings
                sidebar_text = TextArea(id="sidebar-text", read_only=True)
                sidebar_text.can_focus = False
                yield sidebar_text

        with Horizontal(id="choice-bar"):
            yield Static(id="choice-display")

        yield Static(id="status-bar")
        yield Static("[dim]<-/-> select  |  Enter confirm  |  e edit  |  Up/Down navigate  |  Esc quit[/dim]", id="help-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize display"""
        self._update_display()

    def _get_current_chunk(self) -> Optional[ReviewChunk]:
        """Get the current chunk being reviewed"""
        if 0 <= self.current_index < len(self.review_chunks):
            return self.review_chunks[self.current_index]
        return None

    def _build_document_with_highlight(
        self,
        original_text: str,
        replacement_text: str,
        show_replacement: bool
    ) -> str:
        """Build full document with highlighted section.

        Args:
            original_text: The original chunk text to find
            replacement_text: The AI response text
            show_replacement: If True, show AI text; if False, show original
        """
        content = self.working_content
        display_text = replacement_text if show_replacement else original_text

        if original_text in content:
            marked_content = content.replace(
                original_text,
                f">>> REVIEWING >>>\n{display_text}\n<<< REVIEWING <<<"
            )
            return marked_content

        return content

    def _update_display(self) -> None:
        """Update all display elements based on current state"""
        chunk = self._get_current_chunk()

        # Update header
        header = self.query_one("#header", Static)
        header.update(f"[bold]MEO Review[/bold]  |  Session: {self.session.id}")

        # Update chunk info
        info = self.query_one("#chunk-info", Static)
        if chunk:
            total = len(self.review_chunks)
            current = self.current_index + 1
            category = chunk.chunk_data.category if chunk.chunk_data else "Unknown"
            info.update(f"Chunk {current} of {total}  |  {chunk.chunk_id} [{category}]")
        else:
            info.update("No chunks to review")

        # Update choice selection visual
        choice_display = self.query_one("#choice-display", Static)
        if self.choice == ReviewChoice.APPROVE:
            choice_display.update("[reverse bold green] APPROVE [/]    [dim] DENY [/dim]")
        else:
            choice_display.update("[dim] APPROVE [/dim]    [reverse bold red] DENY [/]")

        # Update main and sidebar based on choice
        main_text = self.query_one("#main-text", TextArea)
        sidebar_text = self.query_one("#sidebar-text", TextArea)
        main_title = self.query_one("#main-title", Static)
        sidebar_title = self.query_one("#sidebar-title", Static)

        if chunk and chunk.chunk_data:
            original = chunk.chunk_data.original_text
            ai_response = chunk.chunk_data.ai_response or "[No AI response]"

            if self.choice == ReviewChoice.APPROVE:
                # Main shows AI change in document context
                # Sidebar shows original (the alternate)
                main_text.text = self._build_document_with_highlight(
                    original, ai_response, show_replacement=True
                )
                sidebar_text.text = original
                main_title.update("[bold]DOCUMENT (with AI change)[/bold]")
                sidebar_title.update("[bold]ORIGINAL[/bold]")
            else:  # DENY
                # Main shows original in document context
                # Sidebar shows AI response (the alternate)
                main_text.text = self._build_document_with_highlight(
                    original, ai_response, show_replacement=False
                )
                sidebar_text.text = ai_response
                main_title.update("[bold]DOCUMENT (original)[/bold]")
                sidebar_title.update("[bold]AI RESPONSE[/bold]")
        elif chunk and chunk.error:
            main_text.text = f"Error: {chunk.error}"
            sidebar_text.text = ""
        else:
            main_text.text = "No chunk data"
            sidebar_text.text = ""

        # Update status bar
        status = self.query_one("#status-bar", Static)
        applied = len(self.session.applied_chunks)
        skipped = len(self.session.skipped_chunks)
        pending = len(self.review_chunks)

        edit_indicator = ""
        if self.edit_target != EditTarget.NONE:
            edit_indicator = "  |  [yellow bold]EDITING - Enter to save, Escape to cancel[/]"

        status.update(
            f"[dim]Applied: {applied}  |  Skipped: {skipped}  |  Pending: {pending}{edit_indicator}[/dim]"
        )

    # ========== Arrow Key Navigation ==========

    def action_select_approve(self) -> None:
        """Select Approve option"""
        if self.edit_target != EditTarget.NONE:
            return
        self.choice = ReviewChoice.APPROVE
        self._update_display()

    def action_select_deny(self) -> None:
        """Select Deny option"""
        if self.edit_target != EditTarget.NONE:
            return
        self.choice = ReviewChoice.DENY
        self._update_display()

    # ========== Confirm Choice ==========

    def action_confirm_choice(self) -> None:
        """Confirm the current choice (approve or deny)"""
        if self.edit_target != EditTarget.NONE:
            self._save_edit()
            return

        if self.choice == ReviewChoice.APPROVE:
            self._approve_chunk()
        else:
            self._deny_chunk()

    def _approve_chunk(self) -> None:
        """Approve and apply the current chunk"""
        chunk = self._get_current_chunk()
        if not chunk or not chunk.chunk_data or not chunk.chunk_data.has_response:
            self.notify("Cannot approve: no AI response", severity="warning")
            return

        # Apply the change to working.md
        success = apply_chunk_to_working(
            self.session_path,
            chunk.chunk_data.original_text,
            chunk.chunk_data.ai_response or ""
        )

        if not success:
            self.notify("Failed to apply: original text not found", severity="error")
            return

        # Also apply to original source file
        source_path = Path(self.session.source_file)
        apply_chunk_to_file(
            source_path,
            chunk.chunk_data.original_text,
            chunk.chunk_data.ai_response or ""
        )

        # Commit the change
        try:
            commit_chunk_response(self.session_path, chunk.chunk_id)
        except Exception as e:
            self.notify(f"Git commit failed: {e}", severity="error")
            return

        # Update session
        self.session.mark_chunk_applied(chunk.chunk_id)
        save_session(self.session, self.session_path)

        # Reload working content
        self._load_working_content()

        self.notify(f"Applied {chunk.chunk_id}")
        self._advance_or_complete()

    def _deny_chunk(self) -> None:
        """Deny/skip the current chunk"""
        chunk = self._get_current_chunk()
        if not chunk:
            return

        self.session.mark_chunk_skipped(chunk.chunk_id)
        save_session(self.session, self.session_path)

        self.notify(f"Skipped {chunk.chunk_id}")
        self._advance_or_complete()

    def _advance_or_complete(self) -> None:
        """Move to next chunk or show completion"""
        if self.review_chunks:
            self.review_chunks.pop(self.current_index)

        if self.current_index >= len(self.review_chunks):
            self.current_index = max(0, len(self.review_chunks) - 1)

        if not self.review_chunks:
            self._show_completion()
        else:
            self.choice = ReviewChoice.APPROVE
            self._update_display()

    def _show_completion(self) -> None:
        """Show completion summary and return to SelectionScreen"""
        from meo.tui.screens.selection import SelectionScreen
        from meo.core.sidecar import load_sidecar, save_sidecar

        applied = len(self.session.applied_chunks)
        skipped = len(self.session.skipped_chunks)

        self.session.status = "complete"
        save_session(self.session, self.session_path)

        # Get source file path and reload updated content
        source_path = Path(self.session.source_file)
        updated_content = source_path.read_text()

        # Reload ProjectState from sidecar and clear reviewed chunks
        state = load_sidecar(source_path)
        if state:
            state.chunks = []
            save_sidecar(source_path, state)

        # Notify user of results
        self.notify(f"Review complete! Applied: {applied}, Skipped: {skipped}")

        # Return to SelectionScreen with updated content
        self.app.pop_screen()
        self.app.push_screen(SelectionScreen(source_path, updated_content, state))

    # ========== Inline Editing ==========

    def action_toggle_edit(self) -> None:
        """Toggle edit mode for the sidebar"""
        if self.edit_target != EditTarget.NONE:
            self._cancel_edit()
            return

        self.edit_target = EditTarget.SIDEBAR

        sidebar_text = self.query_one("#sidebar-text", TextArea)
        sidebar_text.can_focus = True  # Enable focus for editing
        sidebar_text.read_only = False
        sidebar_text.focus()

        sidebar_panel = self.query_one("#sidebar-panel")
        sidebar_panel.add_class("editing-mode")

        self._update_display()

    def _save_edit(self) -> None:
        """Save the current edit"""
        if self.edit_target == EditTarget.SIDEBAR:
            sidebar_text = self.query_one("#sidebar-text", TextArea)
            edited_content = sidebar_text.text

            chunk = self._get_current_chunk()
            if chunk and chunk.chunk_data:
                if self.choice == ReviewChoice.APPROVE:
                    # Sidebar shows original when Approve is selected
                    chunk.chunk_data.original_text = edited_content
                else:
                    # Sidebar shows AI response when Deny is selected
                    chunk.chunk_data.ai_response = edited_content

            sidebar_text.read_only = True
            sidebar_text.can_focus = False  # Disable focus after editing
            self.query_one("#sidebar-panel").remove_class("editing-mode")

        self.edit_target = EditTarget.NONE
        self._update_display()
        self.notify("Edit saved")

    def _cancel_edit(self) -> None:
        """Cancel the current edit without saving"""
        if self.edit_target == EditTarget.SIDEBAR:
            sidebar_text = self.query_one("#sidebar-text", TextArea)
            sidebar_text.read_only = True
            sidebar_text.can_focus = False  # Disable focus after editing
            self.query_one("#sidebar-panel").remove_class("editing-mode")

        self.edit_target = EditTarget.NONE
        self._update_display()
        self.notify("Edit cancelled")

    def action_cancel_edit_or_quit(self) -> None:
        """Cancel edit if editing, otherwise quit"""
        if self.edit_target != EditTarget.NONE:
            self._cancel_edit()
        else:
            self._quit_review()

    def _quit_review(self) -> None:
        """Quit the review"""
        applied = len(self.session.applied_chunks)
        skipped = len(self.session.skipped_chunks)
        pending = len(self.review_chunks)

        if pending > 0:
            self.session.status = "reviewing"
            save_session(self.session, self.session_path)

        self.app.exit(
            message=f"Review paused. Applied: {applied}, Skipped: {skipped}, Pending: {pending}"
        )

    # ========== Chunk Navigation ==========

    def action_prev_chunk(self) -> None:
        """Go to previous chunk"""
        if self.edit_target != EditTarget.NONE:
            return
        if self.current_index > 0:
            self.current_index -= 1
            self.choice = ReviewChoice.APPROVE
            self._update_display()

    def action_next_chunk(self) -> None:
        """Go to next chunk"""
        if self.edit_target != EditTarget.NONE:
            return
        if self.current_index < len(self.review_chunks) - 1:
            self.current_index += 1
            self.choice = ReviewChoice.APPROVE
            self._update_display()
