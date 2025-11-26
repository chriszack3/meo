"""Main Textual application for MEO"""

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding

from meo.models.project import ProjectState
from meo.core.sidecar import save_sidecar
from meo.core.output_generator import save_output
from meo.tui.screens.selection import SelectionScreen
from meo.tui.screens.directions import DirectionsScreen


class MeoApp(App):
    """Main MEO TUI application"""

    TITLE = "MEO - Markdown Edit Orchestrator"
    CSS = """
    Screen {
        background: $surface;
    }

    .title {
        text-style: bold;
        color: $primary;
        padding: 1 2;
    }

    .help-text {
        color: $text-muted;
        padding: 0 2;
    }

    #chunk-list {
        width: 30;
        border: solid $primary;
        padding: 1;
    }

    #editor-container {
        border: solid $secondary;
        padding: 1;
    }

    .chunk-edit {
        background: $success 20%;
    }

    .chunk-change {
        background: $warning 20%;
    }

    .chunk-tweak {
        background: $primary 20%;
    }

    .chunk-leave {
        background: $surface-darken-1;
    }

    .selected-chunk {
        border: double $accent;
    }

    Footer {
        background: $surface-darken-1;
    }

    Button {
        margin: 1;
    }

    .direction-option {
        padding: 1 2;
        margin: 0 1;
    }

    .direction-selected {
        background: $primary;
        color: $text;
    }

    /* Hidden elements */
    .hidden {
        display: none;
    }

    /* Sidebar styling */
    #sidebar {
        width: 30;
        border: solid $primary;
        padding: 1;
    }

    /* Category selector */
    #category-header {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #category-list {
        height: auto;
        max-height: 10;
        border: solid $accent;
        margin-bottom: 1;
    }

    #category-list > ListItem {
        padding: 0 1;
    }

    #category-list > ListItem:hover {
        background: $primary 30%;
    }

    #category-list:focus > ListItem.-highlight {
        background: $accent;
    }

    /* Chunks header */
    #chunks-header {
        text-style: bold;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+s", "save", "Save"),
    ]

    def __init__(self, source_file: Path, state: ProjectState):
        super().__init__()
        self.source_file = source_file
        self.state = state
        self.source_content = source_file.read_text()

    def on_mount(self) -> None:
        """Start with selection screen"""
        self.push_screen(SelectionScreen(self.source_file, self.source_content, self.state))

    def action_save(self) -> None:
        """Save current state to sidecar"""
        save_sidecar(self.source_file, self.state)
        self.notify("Saved to sidecar file")

    def action_quit(self) -> None:
        """Quit the application"""
        self.exit()

    def go_to_directions(self) -> None:
        """Switch to directions screen"""
        self.pop_screen()
        self.push_screen(DirectionsScreen(self.source_file, self.state))

    def go_to_selection(self) -> None:
        """Switch back to selection screen"""
        self.pop_screen()
        self.push_screen(SelectionScreen(self.source_file, self.source_content, self.state))

    def generate_and_exit(self) -> None:
        """Generate output and exit"""
        output_path = save_output(self.state, self.source_file)
        save_sidecar(self.source_file, self.state)
        self.exit(message=f"Generated: {output_path}")

    def generate_edit_and_review(self) -> None:
        """Generate chunks, run AI edit with progress, and show review screen."""
        from meo.core.session import create_session, get_session_path
        from meo.tui.screens.processing import ProcessingScreen

        # 1. Generate session + chunks
        self.notify("Generating session...")
        session = create_session(self.source_file, self.state)
        session_path = get_session_path(session.id)

        # 2. Save sidecar
        save_sidecar(self.source_file, self.state)

        # 3. Push processing screen (handles AI edit and transitions to review)
        self.pop_screen()
        self.push_screen(ProcessingScreen(session, session_path))
