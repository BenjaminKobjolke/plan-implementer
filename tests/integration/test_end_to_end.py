"""End-to-end run against a fake `claude` executable emitting canned stream-json."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from plan_implementer import cli
from plan_implementer.constants import ENV_CLAUDE_EXECUTABLE, ENV_COMMIT
from tests.conftest import make_plan_repo

# The fake `claude` is a batch stub, so nothing in this module can run off Windows.
pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="batch stub is Windows-only")

FAKE_CLAUDE_PY = """
import json
import sys

start = {"type": "content_block_start", "content_block": {"type": "text"}}
print(json.dumps({"type": "stream_event", "event": start}), flush=True)
usage = {"input_tokens": 100, "output_tokens": 20, "cache_read_input_tokens": 900,
         "cache_creation_input_tokens": 5}
print(json.dumps({"type": "result", "is_error": False, "result": "implemented",
                  "duration_ms": 10, "total_cost_usd": 0.01, "usage": usage}), flush=True)
sys.exit(0)
"""


@pytest.fixture
def fake_claude(tmp_path: Path) -> Path:
    """A batch stub that behaves like `claude -p ... --output-format stream-json`."""
    script = tmp_path / "fake_claude.py"
    script.write_text(FAKE_CLAUDE_PY, encoding="utf-8")
    launcher = tmp_path / "fake_claude.bat"
    launcher.write_text(f'@echo off\r\n"{sys.executable}" "{script}"\r\n', encoding="utf-8")
    return launcher


def run_cli(*args: str) -> int:
    return cli.main(list(args))


def test_full_run_moves_phases_commits_and_archives(
    tmp_path: Path, fake_claude: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    plan = make_plan_repo(repo, phase_count=2)
    (repo / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    commit_dir = tmp_path / "commits"
    commit_dir.mkdir()
    monkeypatch.setenv(ENV_CLAUDE_EXECUTABLE, str(fake_claude))
    # Each commit drops one uniquely named marker file, so counting them proves both ran.
    monkeypatch.setenv(
        ENV_COMMIT,
        f"python -c \"import tempfile; tempfile.mkstemp(dir=r'{commit_dir}')\"",
    )

    exit_code = run_cli(str(plan))

    assert exit_code == 0
    archived = repo / "plan" / "done" / "demo"
    assert sorted(p.name for p in archived.iterdir()) == [
        "00-context.md",
        "01-step-1.md",
        "02-step-2.md",
        "REPORT.md",
    ]
    assert not plan.exists()
    assert len(list(commit_dir.iterdir())) == 2
    report = (archived / "REPORT.md").read_text(encoding="utf-8")
    # Two phases, each implemented by one session; the commit spec here is a shell command.
    assert "| Claude sessions | 2 |" in report
    assert "| 01-step-1.md | done |" in report
    assert "**$0.02**" in report


def test_dry_run_changes_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = tmp_path / "repo"
    plan = make_plan_repo(repo)
    (repo / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

    exit_code = run_cli(str(plan), "--dry-run")

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "python" in output
    assert (plan / "01-step-1.md").exists()
    assert not (repo / "plan" / "done").exists()


def test_failing_claude_stops_before_moving_or_committing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    plan = make_plan_repo(repo, phase_count=2)
    script = tmp_path / "failing_claude.py"
    script.write_text(
        "import json,sys\n"
        f"print(json.dumps({json.dumps({'type': 'result', 'is_error': True, 'result': 'nope'})}))\n"
        "sys.exit(1)\n",
        encoding="utf-8",
    )
    launcher = tmp_path / "failing_claude.bat"
    launcher.write_text(f'@echo off\r\n"{sys.executable}" "{script}"\r\n', encoding="utf-8")
    monkeypatch.setenv(ENV_CLAUDE_EXECUTABLE, str(launcher))
    monkeypatch.setenv(ENV_COMMIT, "")

    exit_code = run_cli(str(plan))

    assert exit_code == 1
    assert (plan / "01-step-1.md").exists()
    assert "01-step-1.md" in (plan / "ERROR.md").read_text(encoding="utf-8")
    report = (repo / "plan" / "done" / "demo" / "REPORT.md").read_text(encoding="utf-8")
    assert "| Phases | 0 completed, 1 failed of 2 |" in report


def test_console_script_is_installed() -> None:
    result = subprocess.run(
        ["uv", "run", "plan-implementer", "--help"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.returncode == 0
    assert "--dry-run" in result.stdout
