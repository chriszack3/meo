"""CLI interface for MEO using Typer"""

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from meo import __version__
from meo.core.config import (
    load_config,
    create_config,
    config_exists,
    get_config_path,
    ConfigNotFoundError,
    ConfigInvalidError,
)
from meo.presets import BUILTIN_PRESETS

app = typer.Typer(
    name="meo",
    help="Markdown Edit Orchestrator - TUI tool for structured markdown editing",
    invoke_without_command=True,
)
console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"meo version {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-v", callback=version_callback, help="Show version"
    ),
):
    """MEO - Markdown Edit Orchestrator

    Run without arguments to launch the file picker TUI.
    """
    # If a subcommand was invoked, don't run the default behavior
    if ctx.invoked_subcommand is not None:
        return

    # Default behavior: launch file picker
    _run_file_picker()


def _run_file_picker():
    """Load config and launch file picker TUI"""
    from textual.app import App
    from meo.tui.screens.file_picker import FilePickerScreen

    # Load config
    try:
        config = load_config()
    except ConfigNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except ConfigInvalidError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Validate folder exists
    if not config.folder_path.exists():
        console.print(f"[red]Error:[/red] Folder does not exist: {config.folder}")
        console.print("Update the folder path in .meo/config.yaml")
        raise typer.Exit(1)

    # Check for markdown files
    files = config.get_markdown_files()
    if not files:
        console.print(f"[yellow]No .md files found in:[/yellow] {config.folder}")
        raise typer.Exit(1)

    # Create and run a minimal app with file picker
    class FilePickerApp(App):
        CSS = """
        Screen {
            background: $surface;
        }
        #header {
            padding: 1 2;
        }
        #help {
            padding: 0 2;
            color: $text-muted;
        }
        #file-list {
            margin: 1 2;
            height: 1fr;
        }
        """

        def on_mount(self):
            self.push_screen(FilePickerScreen(config))

    app_instance = FilePickerApp()
    selected_file = app_instance.run()

    if selected_file:
        # Launch the main MEO app with the selected file
        _run_meo_app(Path(selected_file))
    else:
        console.print("[dim]No file selected[/dim]")


def _run_meo_app(source_file: Path):
    """Launch the main MEO TUI app for editing"""
    from meo.tui.app import MeoApp
    from meo.models.project import ProjectState
    from meo.core.sidecar import load_sidecar
    import hashlib

    # Load or create project state
    state = load_sidecar(source_file)
    if state is None:
        # Create new state
        content = source_file.read_text()
        state = ProjectState(
            source_file=str(source_file),
            source_hash=hashlib.md5(content.encode()).hexdigest(),
        )

    # Run the app
    app = MeoApp(source_file, state)
    result = app.run()

    if result:
        console.print(f"[green]{result}[/green]")


@app.command()
def init():
    """Create .meo/config.yaml configuration file"""
    if config_exists():
        if not typer.confirm("Config file already exists. Overwrite?"):
            raise typer.Exit(0)

    console.print("[bold]MEO Configuration Setup[/bold]\n")

    # Get folder path
    folder = typer.prompt(
        "Enter absolute path to folder containing markdown files",
        default=str(Path.cwd()),
    )

    # Validate it's absolute
    folder_path = Path(folder)
    if not folder_path.is_absolute():
        console.print("[red]Error:[/red] Path must be absolute")
        raise typer.Exit(1)

    # Validate folder exists
    if not folder_path.exists():
        console.print(f"[red]Error:[/red] Folder does not exist: {folder}")
        raise typer.Exit(1)

    if not folder_path.is_dir():
        console.print(f"[red]Error:[/red] Path is not a directory: {folder}")
        raise typer.Exit(1)

    # Create config
    try:
        config = create_config(folder)
        console.print(f"\n[green]Created:[/green] {get_config_path()}")
        console.print(f"[dim]Folder:[/dim] {config.folder}")

        # Show how many files found
        files = config.get_markdown_files()
        console.print(f"[dim]Found {len(files)} .md file(s)[/dim]")

        console.print("\nRun [bold]meo[/bold] to start editing.")

    except Exception as e:
        console.print(f"[red]Error creating config:[/red] {e}")
        raise typer.Exit(1)


# Presets subcommands
presets_app = typer.Typer(help="Manage direction presets")
app.add_typer(presets_app, name="presets")


@presets_app.command("list")
def presets_list():
    """List available direction presets"""
    table = Table(title="Direction Presets")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Description")

    for preset in BUILTIN_PRESETS:
        table.add_row(preset.id, preset.name, preset.description)

    console.print(table)


@app.command("sessions")
def sessions_list():
    """List all editing sessions"""
    from meo.core.session import list_sessions, load_session

    sessions = list_sessions()
    if not sessions:
        console.print("[yellow]No sessions found[/yellow]")
        return

    table = Table(title="Editing Sessions")
    table.add_column("ID", style="cyan")
    table.add_column("Source File")
    table.add_column("Status")
    table.add_column("Progress")

    for sid in sessions:
        session = load_session(sid)
        if session:
            total = len(session.chunks)
            applied = len(session.applied_chunks)
            skipped = len(session.skipped_chunks)
            progress = f"{applied + skipped}/{total} ({applied} applied, {skipped} skipped)"
            source_name = Path(session.source_file).name
            table.add_row(sid, source_name, session.status, progress)

    console.print(table)


@app.command()
def review(
    session_id: str = typer.Argument(..., help="Session ID to review"),
):
    """Review AI responses and apply approved changes.

    Launch the review TUI to step through each chunk's AI response,
    compare with original text, and approve or reject changes.
    """
    from meo.core.session import load_session, get_session_path, list_sessions

    # Load session
    session = load_session(session_id)
    if session is None:
        console.print(f"[red]Error:[/red] Session not found: {session_id}")
        available = list_sessions()
        if available:
            console.print("\nAvailable sessions:")
            for sid in available:
                console.print(f"  - {sid}")
        raise typer.Exit(1)

    session_path = get_session_path(session_id)

    # Validate session state
    if session.status not in ("editing", "reviewing"):
        console.print(f"[yellow]Warning:[/yellow] Session status is '{session.status}'")

    # Check for pending chunks
    pending = session.get_pending_chunks()
    if not pending:
        console.print("[green]All chunks have been reviewed![/green]")
        console.print(f"Applied: {len(session.applied_chunks)}, Skipped: {len(session.skipped_chunks)}")
        raise typer.Exit(0)

    console.print(f"[dim]Session: {session_id}[/dim]")
    console.print(f"[dim]Pending chunks: {len(pending)}[/dim]")

    # Launch review TUI
    _run_review_app(session, session_path)


def _run_review_app(session, session_path: Path):
    """Launch the review TUI app"""
    from meo.tui.screens.review import ReviewApp

    app_instance = ReviewApp(session, session_path)
    result = app_instance.run()

    if result:
        console.print(f"[green]{result}[/green]")


def main():
    """Entry point for CLI"""
    app()


if __name__ == "__main__":
    main()
