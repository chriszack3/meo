"""Chunk model - represents a marked section of text for editing"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ChunkCategory(str, Enum):
    """Categories determining how a chunk should be processed"""
    EDIT = "edit"
    CHANGE_ENTIRELY = "change_entirely"
    TWEAK = "tweak_as_necessary"
    LEAVE_ALONE = "leave_alone"


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

    # Execution ordering
    execution_order: Optional[int] = None

    @property
    def needs_direction(self) -> bool:
        """Whether this chunk requires a direction assignment"""
        return self.category != ChunkCategory.LEAVE_ALONE

    @property
    def display_name(self) -> str:
        """Short display name for UI"""
        preview = self.original_text[:30].replace("\n", " ")
        if len(self.original_text) > 30:
            preview += "..."
        return f"{self.id}: {preview}"
