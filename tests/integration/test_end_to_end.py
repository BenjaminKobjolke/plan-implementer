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


def _stub_launcher(tmp_path: Path, name: str, body: str) -> Path:
    """A `.bat` running `body` as a Python script, standing in for the `claude` executable."""
    script = tmp_path / f"{name}.py"
    script.write_text(body, encoding="utf-8")
    launcher = tmp_path / f"{name}.bat"
    launcher.write_text(f'@echo off\r\n"{sys.executable}" "{script}"\r\n', encoding="utf-8")
    return launcher


@pytest.fixture
def fake_claude(tmp_path: Path) -> Path:
    """A batch stub that behaves like `claude -p ... --output-format stream-json`."""
    return _stub_launcher(tmp_path, "fake_claude", FAKE_CLAUDE_PY)


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
    assert not (repo / "plan" / "implementing").exists()


def test_failing_claude_stops_before_moving_or_committing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    plan = make_plan_repo(repo, phase_count=2)
    body = (
        "import json,sys\n"
        f"print(json.dumps({json.dumps({'type': 'result', 'is_error': True, 'result': 'nope'})}))\n"
        "sys.exit(1)\n"
    )
    monkeypatch.setenv(ENV_CLAUDE_EXECUTABLE, str(_stub_launcher(tmp_path, "failing_claude", body)))
    monkeypatch.setenv(ENV_COMMIT, "")

    exit_code = run_cli(str(plan))

    parked = repo / "plan" / "errors" / "demo"

    assert exit_code == 1
    assert (parked / "01-step-1.md").exists()
    assert "01-step-1.md" in (parked / "ERROR.md").read_text(encoding="utf-8")
    assert not plan.exists()
    assert not (repo / "plan" / "implementing").exists()
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


def test_plan_parent_folder_implements_every_subfolder(
    tmp_path: Path, fake_claude: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    make_plan_repo(repo, feature="20260908_second", phase_count=1)
    make_plan_repo(repo, feature="20260101_first", phase_count=1)
    (repo / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    monkeypatch.setenv(ENV_CLAUDE_EXECUTABLE, str(fake_claude))
    monkeypatch.setenv(ENV_COMMIT, "")

    exit_code = run_cli(str(repo / "plan"))

    assert exit_code == 0
    done = repo / "plan" / "done"
    for feature in ("20260101_first", "20260908_second"):
        assert sorted(p.name for p in (done / feature).iterdir()) == [
            "00-context.md",
            "01-step-1.md",
            "REPORT.md",
        ]
        assert not (repo / "plan" / feature).exists()
        # Each folder gets its own report, listing only its own single session.
        report = (done / feature / "REPORT.md").read_text(encoding="utf-8")
        assert f"# Implementation Report — {feature}" in report
        assert "| Claude sessions | 1 |" in report


LISTING_CLAUDE_PY = """
import json
import os
import sys

with open(os.environ["PLAN_LISTING_FILE"], "w", encoding="utf-8") as handle:
    handle.write("\\n".join(sorted(os.listdir("plan"))))
print(json.dumps({"type": "result", "is_error": False, "result": "implemented",
                  "duration_ms": 10, "total_cost_usd": 0.01, "usage": {}}), flush=True)
sys.exit(0)
"""


def test_a_claimed_folder_is_hidden_from_a_concurrent_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fake Claude lists `plan/` mid-phase — exactly what a second run would resolve."""
    repo = tmp_path / "repo"
    plan = make_plan_repo(repo, phase_count=1)
    (repo / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    listing = tmp_path / "plan_listing.txt"
    monkeypatch.setenv("PLAN_LISTING_FILE", str(listing))
    monkeypatch.setenv(
        ENV_CLAUDE_EXECUTABLE,
        str(_stub_launcher(tmp_path, "listing_claude", LISTING_CLAUDE_PY)),
    )
    monkeypatch.setenv(ENV_COMMIT, "")

    exit_code = run_cli(str(plan))

    mid_run = listing.read_text(encoding="utf-8").splitlines()
    assert exit_code == 0
    assert mid_run == ["implementing"]
    assert (repo / "plan" / "done" / "demo" / "REPORT.md").exists()
    assert not (repo / "plan" / "implementing").exists()
    assert not plan.exists()
