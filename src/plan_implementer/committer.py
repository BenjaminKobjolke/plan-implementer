"""Commit a finished phase, either through Claude or through a shell command."""

import subprocess
from pathlib import Path

from plan_implementer.app_logger import AppLogger
from plan_implementer.claude_runner import ClaudeRun
from plan_implementer.constants import CLAUDE_PROMPT_PREFIX, COMMIT_SESSION_LABEL


def _git(repo_root: Path, *args: str) -> str | None:
    """Stdout of a git command in `repo_root`, or None when it could not run."""
    try:
        completed = subprocess.run(
            ["git", *args], cwd=repo_root, capture_output=True, text=True, check=False
        )
    except OSError:
        return None
    return completed.stdout.strip() if completed.returncode == 0 else None


def dirty_paths(repo_root: Path) -> frozenset[str]:
    """Paths git reports as changed or untracked, empty when git could not run.

    `--untracked-files=all` lists every file inside an untracked directory instead of the
    directory alone, so a file a phase adds to an already-untracked folder is still visible.
    """
    status = _git(repo_root, "status", "--porcelain", "--untracked-files=all")
    if not status:
        return frozenset()
    # Porcelain v1 lines are two status columns, a space, then the path; a rename adds "old -> new".
    return frozenset(line[3:].split(" -> ")[-1] for line in status.splitlines())


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

    def commit(self, repo_root: Path, dirty_before: frozenset[str] = frozenset()) -> bool:
        """Commit the working tree of `repo_root`; True when nothing went wrong.

        `dirty_before` is the `dirty_paths` baseline taken before the phase ran, so leftover
        work can be told apart from dirt that was already lying around.
        """
        if not self.enabled:
            self._logger.info("Commit disabled - leaving the changes uncommitted.")
            return True

        head_before = _git(repo_root, "rev-parse", "HEAD")
        if self._dispatch(repo_root):
            return True

        return self._commit_landed(repo_root, head_before, dirty_before)

    def _dispatch(self, repo_root: Path) -> bool:
        """Run the configured backend; True when the backend reports success."""
        if self._spec.startswith(CLAUDE_PROMPT_PREFIX):
            self._logger.info(f"Committing via Claude: {self._spec}")
            return self._claude.run(self._spec, repo_root, label=COMMIT_SESSION_LABEL).success

        self._logger.info(f"Committing via command: {self._spec}")
        return subprocess.run(self._spec, shell=True, cwd=repo_root, check=False).returncode == 0

    def _commit_landed(
        self, repo_root: Path, head_before: str | None, dirty_before: frozenset[str]
    ) -> bool:
        """Whether the repository shows a commit the backend failed to report.

        A wrapper CLI can fail its own self-check long after git already committed —
        reasonix aborts on a "final-answer readiness" gate — so the repository, not the
        exit code, has the final say. Requiring HEAD to have moved keeps a genuine
        failure in a repository with nothing to commit from passing as success, and the
        leftovers are measured against the baseline: a file that was already dirty before
        the phase started is somebody else's business, only work the phase itself left
        uncommitted fails it.
        """
        # ponytail: a moved HEAD plus no new leftovers proves the commit, not the push;
        # compare against the upstream ref here if a failed push must fail the phase.
        head_after = _git(repo_root, "rev-parse", "HEAD")
        if head_before is None or head_after is None or head_after == head_before:
            return False

        leftover = dirty_paths(repo_root) - dirty_before
        if leftover:
            self._logger.error(
                f"The commit command failed and left {', '.join(sorted(leftover))} uncommitted."
            )
            return False

        self._logger.warning(
            f"The commit command failed, but {head_after[:7]} was created and the phase left "
            "nothing uncommitted - counting the commit as successful."
        )
        return True
