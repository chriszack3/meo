"""Text replacement utilities for applying AI responses to working files"""

from pathlib import Path
from typing import Tuple


def apply_chunk_to_working(
    session_path: Path,
    original_text: str,
    replacement_text: str
) -> bool:
    """Replace original_text with replacement_text in working.md.

    Uses string replacement (not coordinates) since we have the exact
    original text captured when chunk was marked. This avoids range
    drift issues when multiple chunks are applied in sequence.

    Args:
        session_path: Path to session directory
        original_text: The original text to find and replace
        replacement_text: The AI response to insert

    Returns:
        True if replacement successful, False if original text not found
    """
    working_file = session_path / "working.md"

    if not working_file.exists():
        return False

    content = working_file.read_text()
    new_content, success = find_and_replace_text(content, original_text, replacement_text)

    if success:
        working_file.write_text(new_content)

    return success


def find_and_replace_text(
    content: str,
    original: str,
    replacement: str
) -> Tuple[str, bool]:
    """Find original text and replace with new text.

    Replaces the first occurrence of original text. Handles edge cases
    like empty strings and whitespace differences.

    Args:
        content: The full document content
        original: The text to find
        replacement: The text to replace with

    Returns:
        Tuple of (new_content, success). Success is False if original not found.
    """
    if not original:
        return content, False

    # Normalize line endings for comparison
    normalized_content = content.replace('\r\n', '\n')
    normalized_original = original.replace('\r\n', '\n')

    if normalized_original not in normalized_content:
        # Try stripping whitespace as fallback
        stripped_original = normalized_original.strip()
        if stripped_original and stripped_original in normalized_content:
            # Find and replace the stripped version
            new_content = normalized_content.replace(stripped_original, replacement.strip(), 1)
            return new_content, True
        return content, False

    # Replace first occurrence
    new_content = normalized_content.replace(normalized_original, replacement, 1)
    return new_content, True


def apply_chunk_to_file(
    file_path: Path,
    original_text: str,
    replacement_text: str
) -> bool:
    """Replace original_text with replacement_text in any file.

    Generic version of apply_chunk_to_working() that works with any file path.

    Args:
        file_path: Path to the file to modify
        original_text: The original text to find and replace
        replacement_text: The text to insert

    Returns:
        True if replacement successful, False if file doesn't exist or text not found
    """
    if not file_path.exists():
        return False

    content = file_path.read_text()
    new_content, success = find_and_replace_text(content, original_text, replacement_text)

    if success:
        file_path.write_text(new_content)

    return success


def validate_text_exists(content: str, expected_text: str) -> bool:
    """Check if expected text exists in content.

    Args:
        content: The document content
        expected_text: The text to look for

    Returns:
        True if text found, False otherwise
    """
    if not expected_text:
        return False

    normalized_content = content.replace('\r\n', '\n')
    normalized_expected = expected_text.replace('\r\n', '\n')

    return normalized_expected in normalized_content
