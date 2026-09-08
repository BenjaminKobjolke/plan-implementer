"""Unit tests for the commit strategies."""

from pathlib import Path
from unittest.mock import MagicMock

from plan_implementer.app_logger import AppLogger
from plan_implementer.claude_runner import ClaudeRunner
from plan_implementer.committer import Committer
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
    runner.run.assert_called_once_with("/git:commit", tmp_path)


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
