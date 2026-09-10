"""Centralized runtime settings: a JSON file with environment overrides."""

import json
import os
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from plan_implementer.constants import (
    DEFAULT_IDLE_TIMEOUT_SECONDS,
    DEFAULT_MAX_REPEATED_LINES,
    DEFAULT_PERMISSION_MODE,
    DEFAULT_PROJECT_TYPES_CONFIG,
    DEFAULT_SETTINGS_FILE,
    ENV_COMMIT,
    ENV_IDLE_TIMEOUT,
    ENV_MAX_REPEATED_LINES,
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
    idle_timeout_seconds: int = DEFAULT_IDLE_TIMEOUT_SECONDS
    max_repeated_lines: int = DEFAULT_MAX_REPEATED_LINES


@dataclass(frozen=True)
class Settings:
    """Application settings resolved once, at startup."""

    commit: str
    permission_mode: str
    project_types_config: Path
    idle_timeout_seconds: int
    max_repeated_lines: int

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
            idle_timeout_seconds=_int_override(
                ENV_IDLE_TIMEOUT, file_settings.idle_timeout_seconds
            ),
            max_repeated_lines=_int_override(
                ENV_MAX_REPEATED_LINES, file_settings.max_repeated_lines
            ),
        )


def _int_override(name: str, fallback: int) -> int:
    """Read an integer environment override, reporting a bad value like a bad settings file."""
    raw = os.getenv(name)
    if raw is None:
        return fallback

    try:
        return int(raw)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be a whole number, got {raw!r}") from error


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
