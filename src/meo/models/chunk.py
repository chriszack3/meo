"""Chunk model - represents a marked section of text for editing"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ChunkCategory(str, Enum):
    """Categories determining how a chunk should be processed"""
    REPLACE = "replace"
    TWEAK = "tweak"
    LOCK = "lock"


class LockType(str, Enum):
    """Types for locked chunks - how AI should treat them"""
    EXAMPLE = "example"      # Match the style/format of this chunk
    REFERENCE = "reference"  # Use information with discretion on style
    CONTEXT = "context"      # Background awareness only


class Location(BaseModel):
    """Zero-indexed position in document"""
    row: int
    col: int


class TextRange(BaseModel):
    """A range of text in the document"""
    start: Location
    end: Location

    def contains(self, row: int, col: int) -> bool:
        """Check if a position is within this range"""
        if row < self.start.row or row > self.end.row:
            return False
        if row == self.start.row and col < self.start.col:
            return False
        if row == self.end.row and col > self.end.col:
            return False
        return True

    def overlaps(self, other: "TextRange") -> bool:
        """Check if this range overlaps with another"""
        if self.end.row < other.start.row:
            return False
        if self.start.row > other.end.row:
            return False
        if self.end.row == other.start.row and self.end.col < other.start.col:
            return False
        if self.start.row == other.end.row and self.start.col > other.end.col:
            return False
        return True


class Chunk(BaseModel):
    """A marked section of the document with edit instructions"""
    id: str = Field(..., description="Unique identifier (e.g., 'chunk_001')")
    range: TextRange
    category: ChunkCategory
    original_text: str = Field(..., description="Captured text at time of marking")

    # Populated in Step 2 (Directions)
    direction_preset: Optional[str] = None
    annotation: Optional[str] = None

    # For locked chunks only
    lock_type: Optional[LockType] = None

    # Execution ordering
    execution_order: Optional[int] = None

    @property
    def needs_direction(self) -> bool:
        """Whether this chunk requires a direction assignment"""
        return self.category != ChunkCategory.LOCK

    @property
    def display_name(self) -> str:
        """Short display name for UI"""
        preview = self.original_text[:30].replace("\n", " ")
        if len(self.original_text) > 30:
            preview += "..."
        return f"{self.id}: {preview}"
