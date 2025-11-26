"""Session management - create and manage editing sessions"""

from datetime import datetime
from pathlib import Path
from typing import List, Optional

import yaml

from meo.models.session import Session
from meo.models.project import ProjectState
from meo.models.chunk import Chunk, ChunkCategory
from meo.core.git_ops import init_session_repo
from meo.presets import get_preset_by_id


def get_sessions_dir() -> Path:
    """Get the .meo/sessions directory path"""
    return Path.cwd() / ".meo" / "sessions"


def get_session_path(session_id: str) -> Path:
    """Get the path for a specific session"""
    return get_sessions_dir() / session_id


def generate_session_id(source_file: Path) -> str:
    """Generate a session ID based on source file and timestamp"""
    stem = source_file.stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{stem}_{timestamp}"


def create_session(source_file: Path, state: ProjectState) -> Session:
    """Create a new editing session with atomic chunk files.

    Args:
        source_file: Path to the source markdown file
        state: ProjectState with chunk definitions

    Returns:
        Session object with paths to generated files
    """
    # Generate session ID and path
    session_id = generate_session_id(source_file)
    session_path = get_session_path(session_id)

    # Get chunks in execution order (all chunks, not just actionable)
    all_chunks = state.chunks
    chunk_ids = [c.id for c in all_chunks]

    # Create session object
    session = Session(
        id=session_id,
        source_file=str(source_file.absolute()),
        chunks=chunk_ids,
        status="generating",
    )

    # Initialize git repo with source file
    init_session_repo(session_path, source_file)

    # Generate atomic files for each chunk
    for chunk in all_chunks:
        generate_atomic_file(chunk, session_path, state)

    # Save session metadata
    save_session(session, session_path)

    # Update status
    session.status = "editing"
    save_session(session, session_path)

    return session


def generate_atomic_file(chunk: Chunk, session_path: Path, state: ProjectState) -> Path:
    """Generate a single atomic file for a chunk.

    Args:
        chunk: The chunk to generate a file for
        session_path: Path to the session directory
        state: Full project state (for context chunks)

    Returns:
        Path to the generated file
    """
    chunks_dir = session_path / "chunks"
    chunks_dir.mkdir(exist_ok=True)

    file_path = chunks_dir / f"{chunk.id}.md"

    # Build the atomic file content
    lines = []

    # Header
    lines.append(f"# Edit Task: {chunk.id}")
    lines.append("")

    # Category
    category_display = {
        ChunkCategory.EDIT: "Edit",
        ChunkCategory.CHANGE_ENTIRELY: "Change Entirely",
        ChunkCategory.TWEAK: "Tweak as Necessary",
        ChunkCategory.LEAVE_ALONE: "Context Only (Leave Alone)",
    }
    lines.append(f"**Category:** {category_display.get(chunk.category, chunk.category.value)}")
    lines.append("")

    # Instructions
    lines.append("## Instructions")
    lines.append("")

    if chunk.direction_preset:
        preset = get_preset_by_id(chunk.direction_preset)
        if preset:
            lines.append(f"**Direction:** {preset.name}")
            lines.append("")
            lines.append(preset.render(chunk.annotation))
        elif chunk.annotation:
            lines.append(chunk.annotation)
    elif chunk.annotation:
        lines.append(chunk.annotation)
    else:
        # Default instructions by category
        if chunk.category == ChunkCategory.EDIT:
            lines.append("Edit this text as appropriate.")
        elif chunk.category == ChunkCategory.CHANGE_ENTIRELY:
            lines.append("Completely rewrite this text.")
        elif chunk.category == ChunkCategory.TWEAK:
            lines.append("Make minor adjustments to improve this text.")
        elif chunk.category == ChunkCategory.LEAVE_ALONE:
            lines.append("This chunk is for context only. Do not modify.")

    lines.append("")

    # Context section (for future use - currently empty)
    # TODO: Add surrounding leave_alone chunks as context

    # Text to edit
    lines.append("## Text to Edit")
    lines.append("")
    lines.append("```")
    lines.append(chunk.original_text)
    lines.append("```")
    lines.append("")

    # Response section
    if chunk.category != ChunkCategory.LEAVE_ALONE:
        lines.append("## Your Response")
        lines.append("")
        lines.append("Write ONLY the edited text below. Do not include explanations or the original text.")
        lines.append("")
        lines.append("---")
        lines.append("")

    content = "\n".join(lines)
    file_path.write_text(content)

    return file_path


def save_session(session: Session, session_path: Path) -> None:
    """Save session metadata to YAML file"""
    session_file = session_path / "session.yaml"
    data = session.model_dump(mode="json")
    with open(session_file, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def load_session(session_id: str) -> Optional[Session]:
    """Load a session from its ID"""
    session_path = get_session_path(session_id)
    session_file = session_path / "session.yaml"

    if not session_file.exists():
        return None

    with open(session_file, "r") as f:
        data = yaml.safe_load(f)

    return Session.model_validate(data)


def list_sessions() -> List[str]:
    """List all session IDs"""
    sessions_dir = get_sessions_dir()
    if not sessions_dir.exists():
        return []

    return [d.name for d in sessions_dir.iterdir() if d.is_dir() and (d / "session.yaml").exists()]


def update_session_status(session_id: str, status: str) -> None:
    """Update a session's status"""
    session = load_session(session_id)
    if session:
        session.status = status
        session_path = get_session_path(session_id)
        save_session(session, session_path)


def get_chunk_file_path(session_id: str, chunk_id: str) -> Path:
    """Get the path to a chunk's atomic file"""
    session_path = get_session_path(session_id)
    return session_path / "chunks" / f"{chunk_id}.md"
