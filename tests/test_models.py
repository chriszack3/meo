"""Tests for MEO models"""

import pytest
from meo.models.chunk import Chunk, ChunkCategory, Location, TextRange
from meo.models.project import ProjectState


def test_text_range_contains():
    """Test TextRange.contains()"""
    range_ = TextRange(
        start=Location(row=1, col=5),
        end=Location(row=3, col=10),
    )

    assert range_.contains(2, 0)  # Middle row
    assert range_.contains(1, 5)  # Start
    assert range_.contains(3, 10)  # End
    assert not range_.contains(0, 0)  # Before
    assert not range_.contains(4, 0)  # After
    assert not range_.contains(1, 4)  # Same row, before start col


def test_text_range_overlaps():
    """Test TextRange.overlaps()"""
    range1 = TextRange(
        start=Location(row=1, col=0),
        end=Location(row=3, col=10),
    )
    range2 = TextRange(
        start=Location(row=2, col=0),
        end=Location(row=4, col=10),
    )
    range3 = TextRange(
        start=Location(row=5, col=0),
        end=Location(row=6, col=10),
    )

    assert range1.overlaps(range2)  # Overlapping
    assert range2.overlaps(range1)  # Symmetric
    assert not range1.overlaps(range3)  # Non-overlapping


def test_chunk_needs_direction():
    """Test Chunk.needs_direction property"""
    chunk_replace = Chunk(
        id="test",
        range=TextRange(start=Location(row=0, col=0), end=Location(row=0, col=10)),
        category=ChunkCategory.REPLACE,
        original_text="test",
    )
    chunk_lock = Chunk(
        id="test2",
        range=TextRange(start=Location(row=1, col=0), end=Location(row=1, col=10)),
        category=ChunkCategory.LOCK,
        original_text="test",
    )

    assert chunk_replace.needs_direction
    assert not chunk_lock.needs_direction


def test_project_state_next_chunk_id():
    """Test ProjectState.next_chunk_id()"""
    state = ProjectState(source_file="test.md")

    assert state.next_chunk_id() == "chunk_001"

    state.chunks.append(
        Chunk(
            id="chunk_001",
            range=TextRange(start=Location(row=0, col=0), end=Location(row=0, col=10)),
            category=ChunkCategory.REPLACE,
            original_text="test",
        )
    )

    assert state.next_chunk_id() == "chunk_002"
