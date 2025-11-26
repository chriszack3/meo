"""Sidecar file I/O - YAML storage for project state"""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
from pydantic import ValidationError

from meo.models.project import ProjectState


def get_sidecar_path(source_file: Path) -> Path:
    """Get the sidecar file path for a source file"""
    return source_file.with_suffix(source_file.suffix + ".meo.yaml")


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of file contents"""
    return hashlib.sha256(file_path.read_bytes()).hexdigest()[:16]


def load_sidecar(source_file: Path) -> Optional[ProjectState]:
    """Load project state from sidecar file, or None if doesn't exist"""
    sidecar_path = get_sidecar_path(source_file)
    if not sidecar_path.exists():
        return None

    try:
        with open(sidecar_path, "r") as f:
            data = yaml.safe_load(f)
        return ProjectState.model_validate(data)
    except (yaml.YAMLError, ValidationError) as e:
        raise ValueError(f"Invalid sidecar file: {e}")


def save_sidecar(source_file: Path, state: ProjectState) -> Path:
    """Save project state to sidecar file"""
    sidecar_path = get_sidecar_path(source_file)
    state.modified_at = datetime.now()

    # Convert to dict with datetime serialization
    data = state.model_dump(mode="json")

    with open(sidecar_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    return sidecar_path


def create_new_project(source_file: Path) -> ProjectState:
    """Create a new project state for a source file"""
    return ProjectState(
        source_file=source_file.name,
        source_hash=compute_file_hash(source_file),
        created_at=datetime.now(),
        modified_at=datetime.now(),
    )


def check_source_changed(source_file: Path, state: ProjectState) -> bool:
    """Check if source file has changed since sidecar was created"""
    current_hash = compute_file_hash(source_file)
    return current_hash != state.source_hash
