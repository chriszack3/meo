"""Session model - represents an editing session with atomic files"""

from datetime import datetime
from typing import List, Literal, Tuple
from pydantic import BaseModel, Field


class Session(BaseModel):
    """An editing session with atomic chunk files and git tracking"""

    id: str = Field(..., description="Session ID (e.g., 'sample_20241126_143022')")
    source_file: str = Field(..., description="Absolute path to original source file")
    created_at: datetime = Field(default_factory=datetime.now)

    # Chunk tracking
    chunks: List[str] = Field(default_factory=list, description="Chunk IDs in execution order")

    # Session state
    status: Literal["generating", "editing", "reviewing", "complete"] = "generating"

    # Paths (relative to session folder)
    original_file: str = "original.md"
    working_file: str = "working.md"
    chunks_dir: str = "chunks"

    # Tracking applied responses
    applied_chunks: List[str] = Field(default_factory=list, description="Chunk IDs that have been applied")

    # Tracking skipped/rejected chunks
    skipped_chunks: List[str] = Field(default_factory=list, description="Chunk IDs that were rejected during review")

    def get_chunk_filename(self, chunk_id: str) -> str:
        """Get the filename for a chunk's atomic file"""
        return f"{chunk_id}.md"

    def get_pending_chunks(self) -> List[str]:
        """Get chunks that haven't been applied or skipped"""
        return [
            c for c in self.chunks
            if c not in self.applied_chunks and c not in self.skipped_chunks
        ]

    def mark_chunk_applied(self, chunk_id: str) -> None:
        """Mark a chunk as applied"""
        if chunk_id not in self.applied_chunks:
            self.applied_chunks.append(chunk_id)

    def mark_chunk_skipped(self, chunk_id: str) -> None:
        """Mark a chunk as skipped/rejected"""
        if chunk_id not in self.skipped_chunks:
            self.skipped_chunks.append(chunk_id)

    def is_complete(self) -> bool:
        """Check if all chunks have been reviewed"""
        return len(self.get_pending_chunks()) == 0

    def get_review_progress(self) -> Tuple[int, int]:
        """Get (reviewed_count, total_count)"""
        reviewed = len(self.applied_chunks) + len(self.skipped_chunks)
        return (reviewed, len(self.chunks))
