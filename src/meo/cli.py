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


def main():
    """Entry point for CLI"""
    app()


if __name__ == "__main__":
    main()
