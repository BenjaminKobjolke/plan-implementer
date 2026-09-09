"""Unit tests for the commit strategies."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

from plan_implementer.app_logger import AppLogger
from plan_implementer.claude_runner import ClaudeRunner
from plan_implementer.committer import Committer, dirty_paths
from plan_implementer.constants import COMMIT_SESSION_LABEL
from plan_implementer.models import ClaudeResult

SUCCESS = ClaudeResult(success=True, result_message="ok", duration_ms=1, cost_usd=None)


def make_runner() -> MagicMock:
    runner = MagicMock(spec=ClaudeRunner)
    runner.run.return_value = SUCCESS
    return runner


def test_empty_spec_skips_committing(tmp_path: Path) -> None:
    runner = make_runner()

    assert Committer("", runner, AppLogger(enabled=False)).commit(tmp_path) is True
    runner.run.assert_not_called()


def test_slash_spec_runs_a_claude_prompt(tmp_path: Path) -> None:
    runner = make_runner()

    assert Committer("/git:commit", runner, AppLogger(enabled=False)).commit(tmp_path) is True
    runner.run.assert_called_once_with("/git:commit", tmp_path, label=COMMIT_SESSION_LABEL)


def test_shell_spec_runs_a_shell_command(tmp_path: Path) -> None:
    runner = make_runner()
    marker = tmp_path / "committed.txt"

    committer = Committer(
        f"python -c \"open(r'{marker}', 'w').close()\"", runner, AppLogger(enabled=False)
    )

    assert committer.commit(tmp_path) is True
    assert marker.exists()
    runner.run.assert_not_called()


def test_failing_shell_spec_reports_failure(tmp_path: Path) -> None:
    committer = Committer(
        'python -c "raise SystemExit(3)"', make_runner(), AppLogger(enabled=False)
    )

    assert committer.commit(tmp_path) is False


def make_repo(path: Path) -> None:
    """Initialize a git repository with one commit so HEAD can move."""
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    (path / "seed.txt").write_text("seed", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=path, check=True)


def test_shell_failure_is_ignored_when_the_commit_landed(tmp_path: Path) -> None:
    make_repo(tmp_path)
    (tmp_path / "feature.txt").write_text("work", encoding="utf-8")

    committer = Committer(
        'git add -A && git commit -qm "phase" && python -c "raise SystemExit(3)"',
        make_runner(),
        AppLogger(enabled=False),
    )

    assert committer.commit(tmp_path) is True


def test_shell_failure_stands_when_nothing_was_committed(tmp_path: Path) -> None:
    make_repo(tmp_path)
    (tmp_path / "feature.txt").write_text("work", encoding="utf-8")

    committer = Committer(
        'python -c "raise SystemExit(3)"', make_runner(), AppLogger(enabled=False)
    )

    assert committer.commit(tmp_path) is False


def test_dirt_that_predates_the_phase_does_not_fail_the_commit(tmp_path: Path) -> None:
    make_repo(tmp_path)
    (tmp_path / "unrelated.txt").write_text("dirty before the phase", encoding="utf-8")
    dirty_before = dirty_paths(tmp_path)
    (tmp_path / "feature.txt").write_text("work", encoding="utf-8")

    committer = Committer(
        'git add feature.txt && git commit -qm "phase" && python -c "raise SystemExit(3)"',
        make_runner(),
        AppLogger(enabled=False),
    )

    assert committer.commit(tmp_path, dirty_before) is True


def test_dirt_the_phase_created_still_fails_the_commit(tmp_path: Path) -> None:
    make_repo(tmp_path)
    dirty_before = dirty_paths(tmp_path)
    (tmp_path / "feature.txt").write_text("work", encoding="utf-8")
    (tmp_path / "forgotten.txt").write_text("never staged", encoding="utf-8")

    committer = Committer(
        'git add feature.txt && git commit -qm "phase" && python -c "raise SystemExit(3)"',
        make_runner(),
        AppLogger(enabled=False),
    )

    assert committer.commit(tmp_path, dirty_before) is False
