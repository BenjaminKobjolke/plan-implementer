"""Typed values passed between the modules of this application."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Phase:
    """One `NN-<kebab>.md` phase file of a multi-step plan."""

    number: int
    path: Path

    @property
    def name(self) -> str:
        """The phase file name, e.g. `03-api-client.md`."""
        return self.path.name

    @property
    def label(self) -> str:
        """The zero-padded phase number as it appears in the file name."""
        return f"{self.number:02d}"


@dataclass(frozen=True)
class PlanFolder:
    """A resolved `plan/<feature>/` folder and the repository that owns it."""

    path: Path
    repo_root: Path
    context_path: Path

    @property
    def feature_name(self) -> str:
        """The plan folder name, used for the archive folder name."""
        return self.path.name


@dataclass(frozen=True)
class VerifyCommand:
    """One check a phase must leave green, tagged by the role it fills."""

    role: str
    command: str


@dataclass(frozen=True)
class ProjectType:
    """The detected stack of a repository and the checks that prove it healthy."""

    name: str
    verify: tuple[VerifyCommand, ...]


@dataclass(frozen=True)
class ClaudeResult:
    """The outcome of one headless Claude Code process."""

    success: bool
    result_message: str | None = None
    duration_ms: int | None = None
    cost_usd: float | None = None


@dataclass(frozen=True)
class PhaseResult:
    """The outcome of implementing one phase, including its commit."""

    phase: Phase
    success: bool
    elapsed_seconds: float
    message: str | None = None
    cost_usd: float | None = None


@dataclass(frozen=True)
class RunSummary:
    """What a whole run did, rendered by the CLI and mapped to the exit code."""

    completed: int
    failed: int
    total: int
    archived_to: Path | None = None
