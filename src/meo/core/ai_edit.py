"""AI Edit - call Claude CLI on chunk files"""

import subprocess
from pathlib import Path
from meo.core.session import get_session_path


def run_ai_edit_on_session(session_id: str) -> None:
    """Run Claude CLI on all chunks in a session."""
    session_path = get_session_path(session_id)
    chunks_dir = session_path / "chunks"

    for chunk_file in sorted(chunks_dir.glob("*.md")):
        run_ai_edit_on_chunk(chunk_file)


def run_ai_edit_on_chunk(chunk_path: Path) -> bool:
    """Run Claude CLI on a single chunk file."""
    content = chunk_path.read_text()

    # Skip if already has response
    if has_response(content):
        return True

    # Call Claude CLI
    result = subprocess.run(
        ["claude", "--print",
         "Follow the instructions in this document exactly. "
         "Output ONLY the edited text, nothing else."],
        input=content,
        capture_output=True,
        text=True
    )

    if result.returncode == 0 and result.stdout.strip():
        # Append response after ---
        with open(chunk_path, "a") as f:
            f.write("\n" + result.stdout.strip() + "\n")
        return True

    return False


def has_response(content: str) -> bool:
    """Check if chunk file already has a response after ---"""
    if "---" not in content:
        return False

    after_marker = content.split("---", 1)[1]
    return bool(after_marker.strip())
