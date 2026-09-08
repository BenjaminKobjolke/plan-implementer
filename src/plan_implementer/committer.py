"""Commit a finished phase, either through Claude or through a shell command."""

import subprocess
from pathlib import Path

from plan_implementer.app_logger import AppLogger
from plan_implementer.claude_runner import ClaudeRun
from plan_implementer.constants import CLAUDE_PROMPT_PREFIX


class Committer:
    """One commit spec, dispatched to the backend its prefix selects."""

    def __init__(self, spec: str | None, claude: ClaudeRun, logger: AppLogger) -> None:
        self._spec = (spec or "").strip()
        self._claude = claude
        self._logger = logger

    @property
    def enabled(self) -> bool:
        """Whether a commit will actually be attempted."""
        return bool(self._spec)

    def commit(self, repo_root: Path) -> bool:
        """Commit the working tree of `repo_root`; True when nothing went wrong."""
        if not self.enabled:
            self._logger.info("Commit disabled - leaving the changes uncommitted.")
            return True

        if self._spec.startswith(CLAUDE_PROMPT_PREFIX):
            self._logger.info(f"Committing via Claude: {self._spec}")
            return self._claude.run(self._spec, repo_root).success

        self._logger.info(f"Committing via command: {self._spec}")
        completed = subprocess.run(self._spec, shell=True, cwd=repo_root, check=False)
        return completed.returncode == 0
