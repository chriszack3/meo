"""Direction model - editing instruction presets"""

from typing import Optional
from pydantic import BaseModel


class DirectionPreset(BaseModel):
    """A reusable editing instruction template"""
    id: str
    name: str
    description: str
    prompt_template: str

    def render(self, annotation: Optional[str] = None) -> str:
        """Render the full instruction with optional annotation"""
        result = self.prompt_template
        if annotation:
            result += f"\n\nAdditional guidance: {annotation}"
        return result


class Direction(BaseModel):
    """Applied direction for a specific chunk"""
    preset_id: str
    custom_annotation: Optional[str] = None
