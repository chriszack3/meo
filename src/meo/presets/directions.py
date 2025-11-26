"""Built-in direction presets for editing"""

from typing import Optional
from meo.models.direction import DirectionPreset


BUILTIN_PRESETS = [
    DirectionPreset(
        id="expand",
        name="Expand",
        description="Add more detail and elaboration",
        prompt_template="Expand this text with more detail, examples, or explanation while preserving the core message.",
    ),
    DirectionPreset(
        id="condense",
        name="Condense",
        description="Make more concise",
        prompt_template="Condense this text to be more concise while preserving all key information.",
    ),
    DirectionPreset(
        id="clarify",
        name="Clarify",
        description="Improve clarity and readability",
        prompt_template="Rewrite this text for improved clarity. Remove ambiguity and ensure the meaning is immediately clear.",
    ),
    DirectionPreset(
        id="restructure",
        name="Restructure",
        description="Reorganize the structure",
        prompt_template="Restructure this text for better logical flow. Consider reordering points, adding transitions, or changing the organizational pattern.",
    ),
    DirectionPreset(
        id="simplify",
        name="Simplify",
        description="Use simpler language",
        prompt_template="Simplify this text using plainer language. Reduce complexity while maintaining accuracy.",
    ),
    DirectionPreset(
        id="formalize",
        name="Formalize",
        description="Make more formal/professional",
        prompt_template="Rewrite this text in a more formal, professional tone.",
    ),
    DirectionPreset(
        id="casualize",
        name="Casualize",
        description="Make more conversational",
        prompt_template="Rewrite this text in a more casual, conversational tone.",
    ),
    DirectionPreset(
        id="custom",
        name="Custom",
        description="Provide your own instruction",
        prompt_template="",
    ),
]


def get_preset_by_id(preset_id: str) -> Optional[DirectionPreset]:
    """Get a preset by its ID"""
    for preset in BUILTIN_PRESETS:
        if preset.id == preset_id:
            return preset
    return None
