"""Centralized runtime settings: a JSON file with environment overrides."""

import json
import os
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from plan_implementer.constants import (
    DEFAULT_PERMISSION_MODE,
    DEFAULT_PROJECT_TYPES_CONFIG,
    DEFAULT_SETTINGS_FILE,
    ENV_COMMIT,
    ENV_PERMISSION_MODE,
    ENV_PROJECT_TYPES,
    ENV_SETTINGS,
)
from plan_implementer.errors import ConfigurationError


class SettingsFile(BaseModel):
    """The `settings.json` document — validated at the process boundary."""

    model_config = ConfigDict(extra="forbid")

    commit: str = ""
    permission_mode: str = DEFAULT_PERMISSION_MODE
    project_types_config: str | None = None


@dataclass(frozen=True)
class Settings:
    """Application settings resolved once, at startup."""

    commit: str
    permission_mode: str
    project_types_config: Path

    @classmethod
    def load(cls, settings_path: Path | None = None) -> Settings:
        """Read settings.json (when present), then apply environment overrides."""
        path = settings_path or Path(os.getenv(ENV_SETTINGS, str(DEFAULT_SETTINGS_FILE)))
        file_settings = _read(path)

        configured_types = file_settings.project_types_config
        types_default = Path(configured_types) if configured_types else DEFAULT_PROJECT_TYPES_CONFIG

        return cls(
            commit=os.getenv(ENV_COMMIT, file_settings.commit),
            permission_mode=os.getenv(ENV_PERMISSION_MODE, file_settings.permission_mode),
            project_types_config=Path(os.getenv(ENV_PROJECT_TYPES, str(types_default))),
        )


def _read(path: Path) -> SettingsFile:
    if not path.is_file():
        return SettingsFile()

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ConfigurationError(f"Cannot read settings file: {path}") from error
    except json.JSONDecodeError as error:
        raise ConfigurationError(f"Invalid JSON in settings file: {path}") from error

    try:
        return SettingsFile.model_validate(raw)
    except ValidationError as error:
        raise ConfigurationError(f"Invalid settings file {path}: {error}") from error
