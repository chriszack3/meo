"""Streaming AI Edit - call Claude CLI with real-time output"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from meo.core.session import get_session_path


@dataclass
class StreamProgress:
    """Progress update during AI generation"""
    chunk_index: int
    total_chunks: int
    chunk_id: str
    status: str  # "starting", "streaming", "complete", "error"
    text: str  # Current streamed text


def has_response(content: str) -> bool:
    """Check if chunk file already has a response after ---"""
    if "---" not in content:
        return False
    after_marker = content.split("---", 1)[1]
    return bool(after_marker.strip())


async def stream_ai_edit_on_chunk(
    chunk_path: Path,
    on_output: Callable[[str], None]
) -> bool:
    """Run Claude CLI on a single chunk file with streaming output.

    Args:
        chunk_path: Path to the chunk markdown file
        on_output: Callback for each chunk of streamed output

    Returns:
        True if successful, False otherwise
    """
    content = chunk_path.read_text()

    # Skip if already has response
    if has_response(content):
        return True

    # Create async subprocess
    process = await asyncio.create_subprocess_exec(
        "claude", "--print",
        "Follow the instructions in this document exactly. "
        "Output ONLY the edited text, nothing else.",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Write input and close stdin
    process.stdin.write(content.encode())
    await process.stdin.drain()
    process.stdin.close()

    # Stream output
    full_output = []
    while True:
        chunk = await process.stdout.read(100)
        if not chunk:
            break
        text = chunk.decode('utf-8', errors='replace')
        full_output.append(text)
        on_output(text)

    await process.wait()

    if process.returncode == 0:
        result_text = ''.join(full_output).strip()
        if result_text:
            # Append response after ---
            with open(chunk_path, "a") as f:
                f.write("\n" + result_text + "\n")
            return True

    return False


async def stream_ai_edit_on_session(
    session_id: str,
    progress_callback: Callable[[StreamProgress], None]
) -> None:
    """Run Claude CLI on all chunks in a session with streaming progress.

    Args:
        session_id: Session ID
        progress_callback: Called with progress updates
    """
    session_path = get_session_path(session_id)
    chunks_dir = session_path / "chunks"
    chunk_files = sorted(chunks_dir.glob("*.md"))
    total = len(chunk_files)

    for i, chunk_file in enumerate(chunk_files):
        chunk_id = chunk_file.stem
        current_text = ""

        def on_output(text: str) -> None:
            nonlocal current_text
            current_text += text
            progress_callback(StreamProgress(
                chunk_index=i,
                total_chunks=total,
                chunk_id=chunk_id,
                status="streaming",
                text=current_text,
            ))

        # Notify starting
        progress_callback(StreamProgress(
            chunk_index=i,
            total_chunks=total,
            chunk_id=chunk_id,
            status="starting",
            text="",
        ))

        success = await stream_ai_edit_on_chunk(chunk_file, on_output)

        # Notify complete
        progress_callback(StreamProgress(
            chunk_index=i,
            total_chunks=total,
            chunk_id=chunk_id,
            status="complete" if success else "error",
            text=current_text,
        ))
