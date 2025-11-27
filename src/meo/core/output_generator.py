"""Output generator - creates AI-consumable markdown from project state"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from meo.models.project import ProjectState
from meo.models.chunk import Chunk, ChunkCategory
from meo.presets import get_preset_by_id


def generate_output(state: ProjectState, source_file: Optional[Path] = None) -> str:
    """Generate the AI-consumable markdown output"""
    lines = []

    # Header
    lines.append("# Markdown Edit Instructions")
    lines.append("")
    lines.append(f"**Source Document:** {state.source_file}")
    lines.append(f"**Generated:** {datetime.now().isoformat()}")

    actionable_chunks = state.get_chunks_in_execution_order()
    lines.append(f"**Total Tasks:** {len(actionable_chunks)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Instructions for AI
    lines.append("## Instructions for AI")
    lines.append("")
    lines.append("You will be given a series of editing tasks. Each task:")
    lines.append("1. Specifies text to edit")
    lines.append("2. Provides the category of edit")
    lines.append("3. Gives specific editing instructions")
    lines.append("")
    lines.append("Complete each task in order. For each task, output ONLY the replacement text.")
    lines.append("")
    lines.append("Use this format for your response:")
    lines.append("")
    lines.append("```")
    lines.append("### Response: [task_id]")
    lines.append("[your edited text here]")
    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Generate each task
    for i, chunk in enumerate(actionable_chunks, 1):
        lines.extend(_generate_task(chunk, i))
        lines.append("")
        lines.append("---")
        lines.append("")

    # Response template
    lines.append("## Response Template")
    lines.append("")
    lines.append("Copy and fill in this template:")
    lines.append("")
    lines.append("```markdown")
    for chunk in actionable_chunks:
        lines.append(f"### Response: {chunk.id}")
        lines.append("[edited text here]")
        lines.append("")
    lines.append("```")

    return "\n".join(lines)


def _generate_task(chunk: Chunk, task_num: int) -> list[str]:
    """Generate the markdown for a single task"""
    lines = []

    lines.append(f"## Task {task_num}: {chunk.id}")
    lines.append("")

    # Category
    category_display = {
        ChunkCategory.REPLACE: "Replace",
        ChunkCategory.TWEAK: "Tweak",
    }
    lines.append(f"**Category:** {category_display.get(chunk.category, chunk.category.value)}")

    # Direction
    if chunk.direction_preset:
        preset = get_preset_by_id(chunk.direction_preset)
        if preset:
            lines.append(f"**Direction:** {preset.name}")
    lines.append("")

    # Context visibility (MVP: always isolated)
    lines.append("### Context Visibility")
    lines.append("You CANNOT see the rest of the document. Work only with the provided text.")
    lines.append("")

    # Text to edit
    text_label = "Text to Replace" if chunk.category == ChunkCategory.REPLACE else "Text to Tweak"

    lines.append(f"### {text_label}")
    lines.append("```")
    lines.append(chunk.original_text)
    lines.append("```")
    lines.append("")

    # Instructions
    lines.append("### Instructions")
    if chunk.direction_preset:
        preset = get_preset_by_id(chunk.direction_preset)
        if preset:
            lines.append(preset.render(chunk.annotation))
        elif chunk.annotation:
            lines.append(chunk.annotation)
    elif chunk.annotation:
        lines.append(chunk.annotation)
    else:
        # Default instructions by category
        if chunk.category == ChunkCategory.REPLACE:
            lines.append("Edit or rewrite this text as appropriate.")
        elif chunk.category == ChunkCategory.TWEAK:
            lines.append("Make minor adjustments to improve this text.")

    return lines


def save_output(state: ProjectState, source_file: Path, output_path: Optional[Path] = None) -> Path:
    """Generate and save output to file"""
    if output_path is None:
        output_path = source_file.with_suffix(".meo-output.md")

    content = generate_output(state, source_file)
    output_path.write_text(content)

    state.output_file = output_path.name
    state.last_generated_at = datetime.now()

    return output_path
