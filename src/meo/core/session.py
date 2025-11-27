"""Session management - create and manage editing sessions"""

from datetime import datetime
from pathlib import Path
from typing import List, Optional

import yaml

from meo.models.session import Session
from meo.models.project import ProjectState
from meo.models.chunk import Chunk, ChunkCategory, LockType
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

    # Only non-locked chunks get processed - locked chunks are bundled as context
    actionable_chunks = [c for c in state.chunks if c.category != ChunkCategory.LOCK]
    chunk_ids = [c.id for c in actionable_chunks]

    # Create session object with only actionable chunk IDs
    session = Session(
        id=session_id,
        source_file=str(source_file.absolute()),
        chunks=chunk_ids,
        status="generating",
    )

    # Initialize git repo with source file
    init_session_repo(session_path, source_file)

    # Generate atomic files ONLY for non-locked chunks
    # Locked chunks are bundled as context into these files
    for chunk in actionable_chunks:
        generate_atomic_file(chunk, session_path, state)

    # Save session metadata
    save_session(session, session_path)

    # Update status
    session.status = "editing"
    save_session(session, session_path)

    return session


def generate_atomic_file(chunk: Chunk, session_path: Path, state: ProjectState) -> Path:
    """Generate a single atomic file for a non-locked chunk.

    Note: This function is only called for REPLACE/TWEAK chunks.
    Locked chunks are bundled as context into these files.

    Args:
        chunk: The chunk to generate a file for (must be non-locked)
        session_path: Path to the session directory
        state: Full project state (for gathering locked chunks as context)

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
        ChunkCategory.REPLACE: "Replace",
        ChunkCategory.TWEAK: "Tweak",
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
            lines.append(f"**User's guidance:** {chunk.annotation}")
    elif chunk.annotation:
        lines.append(f"**User's guidance:** {chunk.annotation}")
    else:
        # Default instructions by category
        if chunk.category == ChunkCategory.REPLACE:
            lines.append("Edit or rewrite this text as appropriate.")
        elif chunk.category == ChunkCategory.TWEAK:
            lines.append("Make minor adjustments to improve this text.")

    lines.append("")

    # Context section - bundle locked chunks showing document structure
    locked_chunks = [c for c in state.chunks if c.category == ChunkCategory.LOCK]
    locked_chunks.sort(key=lambda c: (c.range.start.row, c.range.start.col))

    if locked_chunks:
        # Split into before/after relative to target chunk
        target_row = chunk.range.start.row
        before_chunks = [lc for lc in locked_chunks if lc.range.end.row < target_row]
        after_chunks = [lc for lc in locked_chunks if lc.range.start.row > target_row]

        lines.append("## Document Structure")
        lines.append("")
        lines.append("Locked chunks shown in document order. Your text appears where marked.")
        lines.append("")
        lines.append("- **Example**: Match the style, tone, and format of this text")
        lines.append("- **Reference**: Use the information/facts from this text")
        lines.append("- **Context**: Surrounding content for awareness only")
        lines.append("")

        lock_type_label = {
            LockType.EXAMPLE: "Example",
            LockType.REFERENCE: "Reference",
            LockType.CONTEXT: "Context",
        }

        # Chunks BEFORE target
        for lc in before_chunks:
            label = lock_type_label.get(lc.lock_type, "Context") if lc.lock_type else "Context"
            lines.append(f"### {lc.id} [{label}]")
            if lc.annotation:
                lines.append(f"**User's guidance:** {lc.annotation}")
            lines.append("```")
            lines.append(lc.original_text)
            lines.append("```")
            lines.append("")

        # Marker for target position
        lines.append("═" * 50)
        lines.append("**⬇ YOUR TEXT TO EDIT APPEARS BELOW ⬇**")
        lines.append("═" * 50)
        lines.append("")

        # Chunks AFTER target
        for lc in after_chunks:
            label = lock_type_label.get(lc.lock_type, "Context") if lc.lock_type else "Context"
            lines.append(f"### {lc.id} [{label}]")
            if lc.annotation:
                lines.append(f"**User's guidance:** {lc.annotation}")
            lines.append("```")
            lines.append(lc.original_text)
            lines.append("```")
            lines.append("")

    # Text to edit
    lines.append("## Text to Edit")
    lines.append("")
    lines.append("```")
    lines.append(chunk.original_text)
    lines.append("```")
    lines.append("")

    # Response section
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
