"""Config loading and saving for MEO"""

from pathlib import Path

import yaml
from pydantic import ValidationError

from meo.models.config import MeoConfig


# Config lives in .meo/config.yaml in current working directory
CONFIG_DIR = Path(".meo")
CONFIG_FILE = CONFIG_DIR / "config.yaml"


class ConfigNotFoundError(Exception):
    """Raised when config file doesn't exist"""

    pass


class ConfigInvalidError(Exception):
    """Raised when config file is invalid"""

    pass


def get_config_path() -> Path:
    """Get the config file path (relative to cwd)"""
    return CONFIG_FILE


def config_exists() -> bool:
    """Check if config file exists"""
    return CONFIG_FILE.exists()


def load_config() -> MeoConfig:
    """Load config from .meo/config.yaml

    Raises:
        ConfigNotFoundError: If config file doesn't exist
        ConfigInvalidError: If config file is invalid
    """
    if not CONFIG_FILE.exists():
        raise ConfigNotFoundError(
            f"Config file not found at {CONFIG_FILE}\n"
            f"Run 'meo init' to create one."
        )

    try:
        with open(CONFIG_FILE, "r") as f:
            data = yaml.safe_load(f)

        if data is None:
            raise ConfigInvalidError(f"Config file is empty: {CONFIG_FILE}")

        return MeoConfig.model_validate(data)

    except yaml.YAMLError as e:
        raise ConfigInvalidError(f"Invalid YAML in config file: {e}")
    except ValidationError as e:
        raise ConfigInvalidError(f"Invalid config: {e}")


def save_config(config: MeoConfig) -> Path:
    """Save config to .meo/config.yaml"""
    CONFIG_DIR.mkdir(exist_ok=True)

    data = config.model_dump()

    with open(CONFIG_FILE, "w") as f:
        yaml.dump(data, f, default_flow_style=False)

    return CONFIG_FILE


def create_config(folder: str) -> MeoConfig:
    """Create and save a new config"""
    config = MeoConfig(folder=folder)
    save_config(config)
    return config
