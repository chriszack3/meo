"""CLI interface for MEO using Typer"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from meo import __version__
from meo.core.sidecar import load_sidecar, save_sidecar, create_new_project, get_sidecar_path
from meo.core.output_generator import generate_output, save_output
from meo.presets import BUILTIN_PRESETS

app = typer.Typer(
    name="meo",
    help="Markdown Edit Orchestrator - TUI tool for structured markdown editing",
    no_args_is_help=True,
)
console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"meo version {__version__}")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: bool = typer.Option(
        False, "--version", "-v", callback=version_callback, help="Show version"
    ),
):
    """MEO - Markdown Edit Orchestrator"""
    pass


@app.command()
def edit(
    file: Path = typer.Argument(..., help="Markdown file to edit", exists=True),
    resume: bool = typer.Option(False, "--continue", "-c", help="Resume from existing sidecar"),
):
    """Open markdown file in the TUI editor"""
    from meo.tui.app import MeoApp

    # Load or create project state
    if resume:
        state = load_sidecar(file)
        if state is None:
            console.print("[yellow]No existing sidecar found, starting fresh[/yellow]")
            state = create_new_project(file)
    else:
        existing = load_sidecar(file)
        if existing and existing.chunks:
            if not typer.confirm(
                f"Found existing sidecar with {len(existing.chunks)} chunks. Overwrite?"
            ):
                state = existing
            else:
                state = create_new_project(file)
        else:
            state = create_new_project(file)

    # Launch TUI
    tui_app = MeoApp(file, state)
    tui_app.run()


@app.command()
def generate(
    file: Path = typer.Argument(..., help="Markdown file with existing sidecar", exists=True),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Generate output file from existing sidecar (no TUI)"""
    state = load_sidecar(file)
    if state is None:
        console.print("[red]No sidecar file found. Run 'meo edit' first.[/red]")
        raise typer.Exit(1)

    if not state.chunks:
        console.print("[yellow]No chunks defined in sidecar.[/yellow]")
        raise typer.Exit(1)

    actionable = state.get_chunks_needing_direction()
    if not actionable:
        console.print("[yellow]No chunks needing directions.[/yellow]")
        raise typer.Exit(1)

    output_path = save_output(state, file, output)
    save_sidecar(file, state)

    console.print(f"[green]Generated:[/green] {output_path}")
    console.print(f"Tasks: {len(actionable)}")


# Sidecar subcommands
sidecar_app = typer.Typer(help="Manage sidecar files")
app.add_typer(sidecar_app, name="sidecar")


@sidecar_app.command("show")
def sidecar_show(
    file: Path = typer.Argument(..., help="Markdown file", exists=True),
):
    """Display sidecar contents"""
    state = load_sidecar(file)
    if state is None:
        console.print("[yellow]No sidecar file found.[/yellow]")
        raise typer.Exit(1)

    console.print(f"[bold]Source:[/bold] {state.source_file}")
    console.print(f"[bold]Created:[/bold] {state.created_at}")
    console.print(f"[bold]Modified:[/bold] {state.modified_at}")
    console.print(f"[bold]Chunks:[/bold] {len(state.chunks)}")
    console.print()

    if state.chunks:
        table = Table(title="Chunks")
        table.add_column("ID", style="cyan")
        table.add_column("Category", style="green")
        table.add_column("Direction")
        table.add_column("Preview")

        for chunk in state.chunks:
            preview = chunk.original_text[:40].replace("\n", " ")
            if len(chunk.original_text) > 40:
                preview += "..."
            table.add_row(
                chunk.id,
                chunk.category.value,
                chunk.direction_preset or "-",
                preview,
            )

        console.print(table)


@sidecar_app.command("clear")
def sidecar_clear(
    file: Path = typer.Argument(..., help="Markdown file", exists=True),
):
    """Remove sidecar file"""
    sidecar_path = get_sidecar_path(file)
    if sidecar_path.exists():
        sidecar_path.unlink()
        console.print(f"[green]Removed:[/green] {sidecar_path}")
    else:
        console.print("[yellow]No sidecar file found.[/yellow]")


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
    app()


if __name__ == "__main__":
    main()
