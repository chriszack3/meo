"""Processing screen - shows progress during AI generation"""

import asyncio
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Static, ProgressBar, TextArea, Footer
from textual import work

from meo.models.session import Session
from meo.core.ai_edit_streaming import stream_ai_edit_on_session, StreamProgress


class ProcessingScreen(Screen):
    """Screen showing AI processing progress with streaming output."""

    CSS = """
    #progress-header {
        text-style: bold;
        padding: 1 2;
        background: $primary;
        color: $text;
    }

    #progress-bar-container {
        padding: 1 2;
        height: 3;
    }

    #chunk-status {
        padding: 0 2;
        color: $text-muted;
        height: 1;
    }

    #stream-container {
        height: 1fr;
        margin: 1 2;
        border: solid $secondary;
    }

    #stream-header {
        background: $surface-darken-1;
        padding: 0 1;
        text-style: bold;
    }

    #stream-output {
        height: 1fr;
        border: none;
    }

    #cancel-hint {
        padding: 0 2;
        color: $text-muted;
        text-align: center;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(self, session: Session, session_path: Path):
        super().__init__()
        self.session = session
        self.session_path = session_path
        self.total_chunks = len(session.chunks)
        self._cancelled = False

    def compose(self) -> ComposeResult:
        yield Static("[bold]Processing with Claude AI[/bold]", id="progress-header")

        with Vertical(id="progress-bar-container"):
            yield ProgressBar(total=self.total_chunks, show_eta=True, id="progress-bar")

        yield Static("Starting...", id="chunk-status")

        with Vertical(id="stream-container"):
            yield Static("[bold]Claude Output[/bold]", id="stream-header")
            yield TextArea(id="stream-output", read_only=True)

        yield Static("[dim]Press Escape to cancel[/dim]", id="cancel-hint")
        yield Footer()

    def on_mount(self) -> None:
        """Start the async processing worker"""
        self.run_processing()

    @work(thread=True)
    def run_processing(self) -> None:
        """Run AI edit in background thread with async event loop"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(
                stream_ai_edit_on_session(
                    self.session.id,
                    self._on_progress
                )
            )
        finally:
            loop.close()

        # Signal completion
        if not self._cancelled:
            self.app.call_from_thread(self._processing_complete)

    def _on_progress(self, progress: StreamProgress) -> None:
        """Handle progress updates from the streaming worker"""
        if self._cancelled:
            return
        self.app.call_from_thread(self._update_ui, progress)

    def _update_ui(self, progress: StreamProgress) -> None:
        """Update UI elements with progress (called on main thread)"""
        # Update progress bar
        progress_bar = self.query_one("#progress-bar", ProgressBar)
        if progress.status == "complete":
            progress_bar.progress = progress.chunk_index + 1
        elif progress.status == "streaming":
            # Show partial progress within current chunk
            progress_bar.progress = progress.chunk_index + 0.5
        else:
            progress_bar.progress = progress.chunk_index

        # Update status text
        status = self.query_one("#chunk-status", Static)
        status_text = f"Chunk {progress.chunk_index + 1} of {progress.total_chunks}: {progress.chunk_id}"
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
        stream_output = self.query_one("#stream-output", TextArea)
        if progress.status == "starting":
            stream_output.text = f"--- Processing {progress.chunk_id} ---\n"
        elif progress.status == "streaming":
            stream_output.text = f"--- {progress.chunk_id} ---\n{progress.text}"
            # Auto-scroll to bottom
            stream_output.scroll_end(animate=False)

    def _processing_complete(self) -> None:
        """Handle processing completion - transition to review screen"""
        from meo.tui.screens.review_v2 import ReviewScreenV2

        self.app.pop_screen()
        self.app.push_screen(ReviewScreenV2(self.session, self.session_path))

    def action_cancel(self) -> None:
        """Cancel processing"""
        self._cancelled = True
        self.notify("Processing cancelled", severity="warning")
        self.app.pop_screen()
