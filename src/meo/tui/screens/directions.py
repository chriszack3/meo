"""Directions screen - Step 2: Assign direction presets and annotations"""

from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Container, VerticalScroll
from textual.screen import Screen
from textual.widgets import Static, Button, TextArea, Footer, RadioSet, RadioButton, Label
from textual.message import Message

from meo.models.project import ProjectState
from meo.models.chunk import Chunk
from meo.presets import BUILTIN_PRESETS


class DirectionsScreen(Screen):
    """Screen for assigning directions to chunks"""

    BINDINGS = [
        Binding("left", "prev_chunk", "Previous"),
        Binding("right", "next_chunk", "Next"),
        Binding("b", "back", "Back to Selection"),
        Binding("g", "generate", "Generate Output"),
        Binding("tab", "focus_next", "Focus Next", show=False),
    ]

    def __init__(self, source_file: Path, state: ProjectState):
        super().__init__()
        self.source_file = source_file
        self.state = state
        self.chunks = state.get_chunks_needing_direction()
        self.current_index = 0

    def compose(self) -> ComposeResult:
        yield Static("[bold]MEO - Directions[/bold]", classes="title")
        yield Static(
            "[dim]<-/->[/]=navigate  [dim]b[/]=back  [dim]g[/]=generate[/dim]",
            classes="help-text",
        )

        with Horizontal():
            with Vertical(id="chunk-display"):
                yield Static(id="chunk-header")
                yield Static(id="chunk-text", classes="chunk-preview")

            with Vertical(id="direction-panel"):
                yield Static("[bold]Select Direction[/bold]")
                yield RadioSet(id="direction-radio")
                yield Static("\n[bold]Annotation (optional)[/bold]")
                yield TextArea(id="annotation-input")

        with Horizontal(id="nav-buttons"):
            yield Button("< Previous", id="prev-btn", variant="default")
            yield Button("Next >", id="next-btn", variant="primary")
            yield Button("Generate Output", id="generate-btn", variant="success")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the screen"""
        self._setup_radio_buttons()
        self._display_current_chunk()

    def _setup_radio_buttons(self) -> None:
        """Set up the direction radio buttons"""
        radio_set = self.query_one("#direction-radio", RadioSet)

        for preset in BUILTIN_PRESETS:
            radio_set.mount(RadioButton(f"{preset.name} - {preset.description}", value=preset.id))

    def _display_current_chunk(self) -> None:
        """Display the current chunk"""
        if not self.chunks:
            return

        chunk = self.chunks[self.current_index]

        # Update header
        header = self.query_one("#chunk-header", Static)
        header.update(
            f"[bold]Chunk {self.current_index + 1} of {len(self.chunks)}:[/bold] "
            f"{chunk.id} [{chunk.category.value}]"
        )

        # Update text preview
        text_widget = self.query_one("#chunk-text", Static)
        preview = chunk.original_text
        if len(preview) > 500:
            preview = preview[:500] + "\n..."
        text_widget.update(f"```\n{preview}\n```")

        # Update direction selection
        radio_set = self.query_one("#direction-radio", RadioSet)
        if chunk.direction_preset:
            for i, btn in enumerate(radio_set.query(RadioButton)):
                if getattr(btn, "value", None) == chunk.direction_preset:
                    radio_set.index = i
                    break

        # Update annotation
        annotation_input = self.query_one("#annotation-input", TextArea)
        annotation_input.text = chunk.annotation or ""

        # Update navigation buttons
        prev_btn = self.query_one("#prev-btn", Button)
        next_btn = self.query_one("#next-btn", Button)
        prev_btn.disabled = self.current_index == 0
        next_btn.disabled = self.current_index == len(self.chunks) - 1

    def _save_current_chunk(self) -> None:
        """Save the current direction and annotation to the chunk"""
        if not self.chunks:
            return

        chunk = self.chunks[self.current_index]

        # Get selected direction
        radio_set = self.query_one("#direction-radio", RadioSet)
        if radio_set.pressed_index is not None:
            buttons = list(radio_set.query(RadioButton))
            if radio_set.pressed_index < len(buttons):
                selected_btn = buttons[radio_set.pressed_index]
                chunk.direction_preset = getattr(selected_btn, "value", None)

        # Get annotation
        annotation_input = self.query_one("#annotation-input", TextArea)
        annotation = annotation_input.text.strip()
        chunk.annotation = annotation if annotation else None

    def action_prev_chunk(self) -> None:
        """Go to previous chunk"""
        if self.current_index > 0:
            self._save_current_chunk()
            self.current_index -= 1
            self._display_current_chunk()

    def action_next_chunk(self) -> None:
        """Go to next chunk"""
        if self.current_index < len(self.chunks) - 1:
            self._save_current_chunk()
            self.current_index += 1
            self._display_current_chunk()

    def action_back(self) -> None:
        """Go back to selection screen"""
        self._save_current_chunk()
        self.app.go_to_selection()

    def action_generate(self) -> None:
        """Generate output and exit"""
        self._save_current_chunk()

        # Validate all chunks have directions
        missing = []
        for chunk in self.chunks:
            if not chunk.direction_preset and not chunk.annotation:
                missing.append(chunk.id)

        if missing:
            self.notify(
                f"Missing directions for: {', '.join(missing)}",
                severity="warning",
            )
            return

        self.app.generate_and_exit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "prev-btn":
            self.action_prev_chunk()
        elif event.button.id == "next-btn":
            self.action_next_chunk()
        elif event.button.id == "generate-btn":
            self.action_generate()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Handle direction selection change"""
        self._save_current_chunk()
