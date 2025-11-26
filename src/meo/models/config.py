"""Config model for MEO"""

from pathlib import Path
from pydantic import BaseModel, field_validator


class MeoConfig(BaseModel):
    """Configuration for MEO - stored in .meo/config.yaml"""

    folder: str

    @field_validator("folder")
    @classmethod
    def validate_folder(cls, v: str) -> str:
        """Ensure folder is an absolute path"""
        path = Path(v)
        if not path.is_absolute():
            raise ValueError(f"folder must be an absolute path, got: {v}")
        return v

    @property
    def folder_path(self) -> Path:
        """Get folder as Path object"""
        return Path(self.folder)

    def get_markdown_files(self) -> list[Path]:
        """Get all .md files in the configured folder (non-recursive)"""
        folder = self.folder_path
        if not folder.exists():
            return []
        return sorted(folder.glob("*.md"))
