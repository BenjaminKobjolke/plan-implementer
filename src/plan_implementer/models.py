"""Typed values passed between the modules of this application."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from plan_implementer.constants import DEFAULT_IDLE_TIMEOUT_SECONDS, DEFAULT_MAX_REPEATED_LINES


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
class TokenUsage:
    """Token counts of one Claude session, as its `result` event reported them."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0

    @property
    def total(self) -> int:
        """Every token the session touched, cache included."""
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_creation_tokens
        )

    def __add__(self, other: TokenUsage) -> TokenUsage:
        """Sum two sessions, so run totals are `sum(usages, TokenUsage())`."""
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            cache_creation_tokens=self.cache_creation_tokens + other.cache_creation_tokens,
        )


@dataclass(frozen=True)
class ClaudeLimits:
    """What makes a headless Claude process count as hung. `0` disables either limit."""

    idle_timeout_seconds: int = DEFAULT_IDLE_TIMEOUT_SECONDS
    max_repeated_lines: int = DEFAULT_MAX_REPEATED_LINES

    @property
    def idle_timeout(self) -> float | None:
        """The wait a reader may block for, or `None` when the timeout is disabled."""
        return self.idle_timeout_seconds or None

    def repeats_exhausted(self, hidden: int) -> bool:
        """Whether this many suppressed repeats mean Claude is looping rather than working."""
        return bool(self.max_repeated_lines) and hidden > self.max_repeated_lines


# A frozen singleton, so callers that do not care about the limits need not build one.
DEFAULT_CLAUDE_LIMITS = ClaudeLimits()


@dataclass(frozen=True)
class ClaudeResult:
    """The outcome of one headless Claude Code process."""

    success: bool
    result_message: str | None = None
    duration_ms: int | None = None
    cost_usd: float | None = None
    usage: TokenUsage = TokenUsage()


@dataclass(frozen=True)
class SessionRecord:
    """One headless Claude process a run started, and what it reported."""

    label: str
    result: ClaudeResult


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
    started_at: datetime
    ended_at: datetime
    archived_to: Path | None = None
    phases: tuple[PhaseResult, ...] = ()
