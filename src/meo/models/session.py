"""Session model - represents an editing session with atomic files"""

from datetime import datetime
from typing import List, Literal, Optional
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

    def get_chunk_filename(self, chunk_id: str) -> str:
        """Get the filename for a chunk's atomic file"""
        return f"{chunk_id}.md"
