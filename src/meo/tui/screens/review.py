"""Review screen - Review AI responses and approve/reject changes"""

from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Container
from textual.screen import Screen
from textual.widgets import Static, Button, Footer, TextArea

from meo.models.session import Session
from meo.core.session import save_session, get_session_path
from meo.core.chunk_parser import parse_chunk_file, ChunkData
from meo.core.text_replacer import apply_chunk_to_working
from meo.core.git_ops import commit_chunk_response


@dataclass
class ReviewChunk:
    """Data for a chunk being reviewed"""
    chunk_id: str
    chunk_data: Optional[ChunkData]
    error: Optional[str] = None


class ReviewScreen(Screen):
    """Screen for reviewing AI responses"""

    BINDINGS = [
        Binding("a", "approve", "Approve"),
        Binding("r", "reject", "Reject/Skip"),
        Binding("left", "prev_chunk", "Previous"),
        Binding("right", "next_chunk", "Next"),
        Binding("q", "quit_review", "Quit"),
    ]

    def __init__(self, session: Session, session_path: Path):
        super().__init__()
        self.session = session
        self.session_path = session_path
        self.pending_chunks: List[str] = session.get_pending_chunks()
        self.current_index = 0
        self.review_chunks: List[ReviewChunk] = []
        self._load_all_chunks()

    def _load_all_chunks(self) -> None:
        """Load all pending chunk data"""
        for chunk_id in self.pending_chunks:
            chunk_path = self.session_path / "chunks" / f"{chunk_id}.md"
            try:
                if chunk_path.exists():
                    chunk_data = parse_chunk_file(chunk_path)
                    self.review_chunks.append(ReviewChunk(chunk_id, chunk_data))
                else:
                    self.review_chunks.append(ReviewChunk(chunk_id, None, f"File not found: {chunk_path}"))
            except Exception as e:
                self.review_chunks.append(ReviewChunk(chunk_id, None, str(e)))

    def compose(self) -> ComposeResult:
        yield Static(id="header", classes="title")
        yield Static(id="chunk-info", classes="help-text")

        with Horizontal(id="diff-container"):
            with Vertical(id="original-panel"):
                yield Static("[bold]ORIGINAL[/bold]", classes="panel-title")
                yield TextArea(id="original-text", read_only=True)

            with Vertical(id="response-panel"):
                yield Static("[bold]AI RESPONSE[/bold]", classes="panel-title")
                yield TextArea(id="response-text", read_only=True)

        yield Static(id="status-bar", classes="status-bar")

        with Horizontal(id="action-bar"):
            yield Button("Approve [a]", id="approve-btn", variant="success")
            yield Button("Skip [r]", id="reject-btn", variant="warning")
            yield Button("< Prev", id="prev-btn", variant="default")
            yield Button("Next >", id="next-btn", variant="default")
            yield Button("Quit [q]", id="quit-btn", variant="error")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize display"""
        self._update_display()

    def _get_current_chunk(self) -> Optional[ReviewChunk]:
        """Get the current chunk being reviewed"""
        if 0 <= self.current_index < len(self.review_chunks):
            return self.review_chunks[self.current_index]
        return None

    def _update_display(self) -> None:
        """Update all display elements"""
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
            direction = chunk.chunk_data.direction if chunk.chunk_data else ""
            direction_str = f"  |  Direction: {direction}" if direction else ""
            info.update(f"Chunk {current} of {total}  |  {chunk.chunk_id} [{category}]{direction_str}")
        else:
            info.update("No chunks to review")

        # Update original text
        original_area = self.query_one("#original-text", TextArea)
        if chunk and chunk.chunk_data:
            original_area.text = chunk.chunk_data.original_text
        elif chunk and chunk.error:
            original_area.text = f"Error: {chunk.error}"
        else:
            original_area.text = ""

        # Update response text
        response_area = self.query_one("#response-text", TextArea)
        if chunk and chunk.chunk_data:
            if chunk.chunk_data.has_response:
                response_area.text = chunk.chunk_data.ai_response or ""
            else:
                response_area.text = "[No AI response found]\n\nThe AI has not yet written a response after the '---' marker in the chunk file."
        elif chunk and chunk.error:
            response_area.text = f"Error: {chunk.error}"
        else:
            response_area.text = ""

        # Update status bar
        status = self.query_one("#status-bar", Static)
        applied = len(self.session.applied_chunks)
        skipped = len(self.session.skipped_chunks)
        pending = len(self.session.get_pending_chunks())
        status.update(f"[dim]Applied: {applied}  |  Skipped: {skipped}  |  Pending: {pending}[/dim]")

        # Update button states
        prev_btn = self.query_one("#prev-btn", Button)
        next_btn = self.query_one("#next-btn", Button)
        approve_btn = self.query_one("#approve-btn", Button)

        prev_btn.disabled = self.current_index == 0
        next_btn.disabled = self.current_index >= len(self.review_chunks) - 1

        # Disable approve if no response
        if chunk and chunk.chunk_data and not chunk.chunk_data.has_response:
            approve_btn.disabled = True
        elif chunk and chunk.error:
            approve_btn.disabled = True
        else:
            approve_btn.disabled = False

    def action_approve(self) -> None:
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
            self.notify("Failed to apply: original text not found in working.md", severity="error")
            return

        # Commit the change
        try:
            commit_chunk_response(self.session_path, chunk.chunk_id)
        except Exception as e:
            self.notify(f"Git commit failed: {e}", severity="error")
            return

        # Update session
        self.session.mark_chunk_applied(chunk.chunk_id)
        save_session(self.session, self.session_path)

        self.notify(f"Applied {chunk.chunk_id}", severity="information")
        self._advance_or_complete()

    def action_reject(self) -> None:
        """Skip/reject the current chunk"""
        chunk = self._get_current_chunk()
        if not chunk:
            return

        # Update session
        self.session.mark_chunk_skipped(chunk.chunk_id)
        save_session(self.session, self.session_path)

        self.notify(f"Skipped {chunk.chunk_id}", severity="information")
        self._advance_or_complete()

    def _advance_or_complete(self) -> None:
        """Move to next chunk or show completion"""
        # Remove current chunk from review list and update pending
        if self.review_chunks:
            self.review_chunks.pop(self.current_index)

        # Adjust index if needed
        if self.current_index >= len(self.review_chunks):
            self.current_index = max(0, len(self.review_chunks) - 1)

        if not self.review_chunks:
            # All done
            self._show_completion()
        else:
            self._update_display()

    def _show_completion(self) -> None:
        """Show completion summary and exit"""
        applied = len(self.session.applied_chunks)
        skipped = len(self.session.skipped_chunks)

        # Update session status
        self.session.status = "complete"
        save_session(self.session, self.session_path)

        self.app.exit(message=f"Review complete! Applied: {applied}, Skipped: {skipped}")

    def action_prev_chunk(self) -> None:
        """Go to previous chunk"""
        if self.current_index > 0:
            self.current_index -= 1
            self._update_display()

    def action_next_chunk(self) -> None:
        """Go to next chunk"""
        if self.current_index < len(self.review_chunks) - 1:
            self.current_index += 1
            self._update_display()

    def action_quit_review(self) -> None:
        """Quit the review"""
        applied = len(self.session.applied_chunks)
        skipped = len(self.session.skipped_chunks)
        pending = len(self.session.get_pending_chunks())

        if pending > 0:
            self.session.status = "reviewing"
            save_session(self.session, self.session_path)

        self.app.exit(message=f"Review paused. Applied: {applied}, Skipped: {skipped}, Pending: {pending}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        button_id = event.button.id
        if button_id == "approve-btn":
            self.action_approve()
        elif button_id == "reject-btn":
            self.action_reject()
        elif button_id == "prev-btn":
            self.action_prev_chunk()
        elif button_id == "next-btn":
            self.action_next_chunk()
        elif button_id == "quit-btn":
            self.action_quit_review()


class ReviewApp(App):
    """Standalone app for review workflow"""

    TITLE = "MEO - Review"
    CSS = """
    Screen {
        background: $surface;
    }

    .title {
        text-style: bold;
        color: $primary;
        padding: 1 2;
        background: $surface-darken-1;
    }

    .help-text {
        color: $text-muted;
        padding: 0 2;
    }

    #diff-container {
        height: 1fr;
        margin: 1 2;
    }

    #original-panel {
        width: 50%;
        border: solid $secondary;
        margin-right: 1;
    }

    #response-panel {
        width: 50%;
        border: solid $success;
    }

    .panel-title {
        text-style: bold;
        background: $surface-darken-1;
        padding: 0 1;
        text-align: center;
    }

    #original-text, #response-text {
        height: 1fr;
        border: none;
    }

    .status-bar {
        padding: 0 2;
        background: $surface-darken-1;
    }

    #action-bar {
        height: auto;
        padding: 1 2;
        align: center middle;
    }

    #action-bar Button {
        margin: 0 1;
    }

    Footer {
        background: $surface-darken-2;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, session: Session, session_path: Path):
        super().__init__()
        self.session = session
        self.session_path = session_path

    def on_mount(self) -> None:
        """Start with review screen"""
        self.push_screen(ReviewScreen(self.session, self.session_path))
