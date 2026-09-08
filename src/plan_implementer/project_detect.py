"""Detect a repository's stack and resolve the checks a phase must leave green."""

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from plan_implementer.constants import TOOL_BAT_ROLES, UNKNOWN_PROJECT_TYPE
from plan_implementer.errors import ConfigurationError
from plan_implementer.models import ProjectType, VerifyCommand


class Marker(BaseModel):
    """One filesystem marker that identifies a stack."""

    model_config = ConfigDict(extra="forbid")

    path: str | None = None
    glob: str | None = None
    contains: str | None = None


class CommandPrefix(BaseModel):
    """A prefix applied to a stack's commands when a version manager is present."""

    model_config = ConfigDict(extra="forbid")

    value: str
    when_any_exists: list[str]


class VerifyEntry(BaseModel):
    """A stack's default command for one role."""

    model_config = ConfigDict(extra="forbid")

    role: str
    command: str


class TypeDefinition(BaseModel):
    """Everything known about one stack."""

    model_config = ConfigDict(extra="forbid")

    priority: int
    markers: list[Marker]
    verify: list[VerifyEntry]
    command_prefix: CommandPrefix | None = None


class ProjectTypesFile(BaseModel):
    """The `config/project_types.json` document."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int
    types: dict[str, TypeDefinition]


def load_config(path: Path) -> dict[str, TypeDefinition]:
    """Read and validate the project-type definitions."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ConfigurationError(f"Cannot read project types config: {path}") from error
    except json.JSONDecodeError as error:
        raise ConfigurationError(f"Invalid JSON in project types config: {path}") from error

    try:
        return ProjectTypesFile.model_validate(raw).types
    except ValidationError as error:
        raise ConfigurationError(f"Invalid project types config {path}: {error}") from error


def detect(repo_root: Path, config: dict[str, TypeDefinition]) -> ProjectType:
    """Identify the stack of `repo_root` and resolve its verify commands."""
    for name, definition in sorted(config.items(), key=lambda item: item[1].priority):
        if _matches(repo_root, definition):
            return ProjectType(name=name, verify=_resolve_verify(repo_root, definition))

    return ProjectType(name=UNKNOWN_PROJECT_TYPE, verify=_bat_overrides(repo_root))


def _matches(repo_root: Path, definition: TypeDefinition) -> bool:
    return any(_marker_matches(repo_root, marker) for marker in definition.markers)


def _marker_matches(repo_root: Path, marker: Marker) -> bool:
    candidates = (
        [repo_root / marker.path] if marker.path else sorted(repo_root.glob(marker.glob or ""))
    )
    for candidate in candidates:
        if not candidate.is_file():
            continue
        if marker.contains is None:
            return True
        if marker.contains in candidate.read_text(encoding="utf-8", errors="replace"):
            return True
    return False


def _resolve_verify(repo_root: Path, definition: TypeDefinition) -> tuple[VerifyCommand, ...]:
    """Existing project bats win; a stack default only fills a role no bat covers."""
    overrides = _bat_overrides(repo_root)
    covered = {entry.role for entry in overrides}
    prefix = _command_prefix(repo_root, definition)

    defaults = tuple(
        VerifyCommand(role=entry.role, command=f"{prefix}{entry.command}")
        for entry in definition.verify
        if entry.role not in covered
    )
    return overrides + defaults


def _bat_overrides(repo_root: Path) -> tuple[VerifyCommand, ...]:
    return tuple(
        VerifyCommand(role=role, command=relative.replace("/", "\\"))
        for relative, role in TOOL_BAT_ROLES.items()
        if (repo_root / relative).is_file()
    )


def _command_prefix(repo_root: Path, definition: TypeDefinition) -> str:
    prefix = definition.command_prefix
    if prefix and any((repo_root / marker).exists() for marker in prefix.when_any_exists):
        return prefix.value
    return ""
