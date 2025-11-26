"""Project state model - stored in sidecar YAML file"""

from datetime import datetime
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field

from meo.models.chunk import Chunk


class ProjectState(BaseModel):
    """Complete state stored in sidecar file"""
    version: str = "1.0"
    source_file: str
    source_hash: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
    modified_at: datetime = Field(default_factory=datetime.now)

    chunks: List[Chunk] = []

    # Output tracking
    output_file: Optional[str] = None
    last_generated_at: Optional[datetime] = None

    def get_chunks_needing_direction(self) -> List[Chunk]:
        """Get chunks that need direction assignment"""
        return [c for c in self.chunks if c.needs_direction]

    def get_chunks_in_execution_order(self) -> List[Chunk]:
        """Get chunks sorted by execution order"""
        actionable = [c for c in self.chunks if c.needs_direction]
        return sorted(actionable, key=lambda c: c.execution_order or 999)

    def next_chunk_id(self) -> str:
        """Generate next chunk ID"""
        existing_nums = []
        for chunk in self.chunks:
            if chunk.id.startswith("chunk_"):
                try:
                    num = int(chunk.id.split("_")[1])
                    existing_nums.append(num)
                except (IndexError, ValueError):
                    pass
        next_num = max(existing_nums, default=0) + 1
        return f"chunk_{next_num:03d}"

    def add_chunk(self, chunk: Chunk) -> None:
        """Add a chunk, checking for overlaps"""
        for existing in self.chunks:
            if chunk.range.overlaps(existing.range):
                raise ValueError(f"Chunk overlaps with {existing.id}")
        self.chunks.append(chunk)
        self.modified_at = datetime.now()

    def remove_chunk(self, chunk_id: str) -> bool:
        """Remove a chunk by ID"""
        for i, chunk in enumerate(self.chunks):
            if chunk.id == chunk_id:
                self.chunks.pop(i)
                self.modified_at = datetime.now()
                return True
        return False

    def get_sidecar_path(self, source_path: Path) -> Path:
        """Get the sidecar file path for a source file"""
        return source_path.with_suffix(source_path.suffix + ".meo.yaml")
