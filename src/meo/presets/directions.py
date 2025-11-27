"""Built-in direction presets for editing - split by action type"""

from typing import Optional
from meo.models.direction import DirectionPreset


# Replace directions: outcome-focused ("what should this become?")
REPLACE_PRESETS = [
    DirectionPreset(
        id="richer",
        name="Richer",
        description="More depth and substance",
        prompt_template="Rewrite with more depth, detail, and substance. Expand on ideas and add nuance.",
    ),
    DirectionPreset(
        id="tighter",
        name="Tighter",
        description="More concise and direct",
        prompt_template="Rewrite to be more concise and direct. Remove fluff, tighten prose.",
    ),
    DirectionPreset(
        id="livelier",
        name="Livelier",
        description="More energy and engagement",
        prompt_template="Rewrite with more energy and engagement. Make it dynamic and compelling.",
    ),
    DirectionPreset(
        id="calmer",
        name="Calmer",
        description="More measured pace",
        prompt_template="Rewrite with a more measured, steady pace. Tone down intensity.",
    ),
    DirectionPreset(
        id="elevated",
        name="Elevated",
        description="More formal language",
        prompt_template="Rewrite with more formal, sophisticated language. Raise the register.",
    ),
    DirectionPreset(
        id="grounded",
        name="Grounded",
        description="More accessible language",
        prompt_template="Rewrite with more accessible, down-to-earth language. Lower the register.",
    ),
    DirectionPreset(
        id="custom",
        name="Custom",
        description="Provide your own instruction",
        prompt_template="",
    ),
]


# Tweak directions: issue-focused ("what's wrong?")
TWEAK_PRESETS = [
    DirectionPreset(
        id="flow",
        name="Flow",
        description="Fix rhythm and transitions",
        prompt_template="Improve the rhythm and transitions. Smooth out awkward phrasing without changing meaning.",
    ),
    DirectionPreset(
        id="precision",
        name="Precision",
        description="Sharpen vague wording",
        prompt_template="Sharpen vague or imprecise wording. Make language more exact without changing tone.",
    ),
    DirectionPreset(
        id="tone",
        name="Tone",
        description="Adjust voice subtly",
        prompt_template="Adjust the voice/register subtly. Preserve content but refine how it sounds.",
    ),
    DirectionPreset(
        id="custom",
        name="Custom",
        description="Provide your own instruction",
        prompt_template="",
    ),
]


# Combined list for backward compatibility
BUILTIN_PRESETS = REPLACE_PRESETS + TWEAK_PRESETS


def get_preset_by_id(preset_id: str) -> Optional[DirectionPreset]:
    """Get a preset by its ID (searches both lists)"""
    for preset in REPLACE_PRESETS:
        if preset.id == preset_id:
            return preset
    for preset in TWEAK_PRESETS:
        if preset.id == preset_id:
            return preset
    return None
