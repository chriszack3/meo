"""Git operations for session management"""

import subprocess
from pathlib import Path
from typing import Optional


def run_git(session_path: Path, *args: str) -> subprocess.CompletedProcess:
    """Run a git command in the session directory"""
    return subprocess.run(
        ["git", *args],
        cwd=session_path,
        capture_output=True,
        text=True,
        check=True,
    )


def init_session_repo(session_path: Path, source_file: Path) -> None:
    """Initialize git repo, copy source file, and make initial commit.

    Args:
        session_path: Path to session directory (will be created if needed)
        source_file: Path to the source markdown file
    """
    # Create session directory
    session_path.mkdir(parents=True, exist_ok=True)
    chunks_dir = session_path / "chunks"
    chunks_dir.mkdir(exist_ok=True)

    # Initialize git repo
    run_git(session_path, "init")

    # Configure git for this repo (avoid needing global config)
    run_git(session_path, "config", "user.email", "meo@local")
    run_git(session_path, "config", "user.name", "MEO")

    # Copy source file
    content = source_file.read_text()
    (session_path / "original.md").write_text(content)
    (session_path / "working.md").write_text(content)

    # Initial commit
    run_git(session_path, "add", ".")
    run_git(session_path, "commit", "-m", "Session start")


def commit_chunk_response(session_path: Path, chunk_id: str, message: Optional[str] = None) -> None:
    """Stage working.md and commit with chunk ID.

    Args:
        session_path: Path to session directory
        chunk_id: ID of the chunk being applied
        message: Optional custom commit message
    """
    commit_msg = message or f"Applied {chunk_id}"
    run_git(session_path, "add", "working.md")
    run_git(session_path, "commit", "-m", commit_msg)


def get_chunk_diff(session_path: Path) -> str:
    """Get the diff for the last commit.

    Returns:
        Unified diff string
    """
    result = run_git(session_path, "diff", "HEAD~1", "HEAD", "--", "working.md")
    return result.stdout


def get_working_diff(session_path: Path) -> str:
    """Get diff between original and current working file.

    Returns:
        Unified diff string
    """
    result = run_git(session_path, "diff", "HEAD~1", "--", "working.md")
    return result.stdout


def rollback_chunk(session_path: Path) -> None:
    """Rollback the last commit (undo last chunk application)."""
    run_git(session_path, "checkout", "HEAD~1", "--", "working.md")
    run_git(session_path, "commit", "-m", "Rollback last chunk")


def get_commit_count(session_path: Path) -> int:
    """Get the number of commits in the session repo."""
    result = run_git(session_path, "rev-list", "--count", "HEAD")
    return int(result.stdout.strip())


def has_uncommitted_changes(session_path: Path) -> bool:
    """Check if there are uncommitted changes in working.md"""
    try:
        result = run_git(session_path, "status", "--porcelain", "working.md")
        return bool(result.stdout.strip())
    except subprocess.CalledProcessError:
        return False


def get_original_vs_working_diff(session_path: Path) -> str:
    """Get diff between original.md and working.md"""
    result = subprocess.run(
        ["diff", "-u", "original.md", "working.md"],
        cwd=session_path,
        capture_output=True,
        text=True,
    )
    return result.stdout
