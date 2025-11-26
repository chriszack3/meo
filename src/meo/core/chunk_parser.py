"""Chunk file parser - extract AI responses and metadata from chunk files"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ChunkData:
    """Parsed data from a chunk file"""
    chunk_id: str
    category: str
    direction: Optional[str]
    original_text: str
    ai_response: Optional[str]
    has_response: bool


def parse_chunk_file(chunk_path: Path) -> ChunkData:
    """Parse a chunk file and extract all components.

    Args:
        chunk_path: Path to the chunk markdown file

    Returns:
        ChunkData with extracted components

    Raises:
        FileNotFoundError: If chunk file doesn't exist
        ValueError: If chunk file is malformed
    """
    content = chunk_path.read_text()
    chunk_id = chunk_path.stem  # e.g., "chunk_001" from "chunk_001.md"

    # Extract category
    category = extract_category(content)

    # Extract direction
    direction = extract_direction(content)

    # Extract original text
    original_text = extract_original_text(content)

    # Extract AI response
    ai_response = extract_ai_response(content)

    return ChunkData(
        chunk_id=chunk_id,
        category=category,
        direction=direction,
        original_text=original_text,
        ai_response=ai_response,
        has_response=ai_response is not None and ai_response.strip() != "",
    )


def extract_category(content: str) -> str:
    """Extract the category from chunk content.

    Looks for: **Category:** <category>

    Returns:
        Category string, or "Unknown" if not found
    """
    match = re.search(r"\*\*Category:\*\*\s*(.+?)(?:\n|$)", content)
    if match:
        return match.group(1).strip()
    return "Unknown"


def extract_direction(content: str) -> Optional[str]:
    """Extract the direction preset name from chunk content.

    Looks for: **Direction:** <direction>

    Returns:
        Direction name, or None if not found
    """
    match = re.search(r"\*\*Direction:\*\*\s*(.+?)(?:\n|$)", content)
    if match:
        return match.group(1).strip()
    return None


def extract_original_text(content: str) -> str:
    """Extract the original text from the '## Text to Edit' section.

    The text is inside a code block after the section header.

    Returns:
        Original text, or empty string if not found
    """
    # Find the "## Text to Edit" section
    section_match = re.search(
        r"## Text to Edit\s*\n\s*```\s*\n(.*?)```",
        content,
        re.DOTALL
    )
    if section_match:
        return section_match.group(1).strip()
    return ""


def extract_ai_response(content: str) -> Optional[str]:
    """Extract the AI response from chunk file content.

    The response is everything after the '---' marker in the
    "## Your Response" section.

    Returns:
        The AI response text (trimmed), or None if no response found
    """
    # Find the "## Your Response" section and the --- marker
    section_match = re.search(
        r"## Your Response.*?---\s*\n(.*)",
        content,
        re.DOTALL
    )
    if section_match:
        response = section_match.group(1).strip()
        if response:
            return response
    return None
