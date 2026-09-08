"""Unit tests for the end-of-run REPORT.md and ERROR.md."""

from datetime import datetime, timedelta
from pathlib import Path

from plan_implementer import plan_folder, run_report
from plan_implementer.app_logger import AppLogger
from plan_implementer.constants import ERROR_FILE_NAME, REPORT_FILE_NAME
from plan_implementer.models import (
    ClaudeResult,
    Phase,
    PhaseResult,
    PlanFolder,
    RunSummary,
    SessionRecord,
    TokenUsage,
)
from tests.conftest import make_plan_repo

STARTED = datetime(2026, 9, 8, 14, 40, 12)
PHASE_USAGE = TokenUsage(
    input_tokens=12430,
    output_tokens=3102,
    cache_read_tokens=480220,
    cache_creation_tokens=24900,
)
COMMIT_USAGE = TokenUsage(input_tokens=1120, output_tokens=210, cache_read_tokens=40010)
SESSIONS = (
    SessionRecord(
        label="01-step-1.md",
        result=ClaudeResult(success=True, cost_usd=0.42, usage=PHASE_USAGE),
    ),
    SessionRecord(
        label="commit",
        result=ClaudeResult(success=True, cost_usd=0.03, usage=COMMIT_USAGE),
    ),
)


def make_folder(tmp_path: Path) -> PlanFolder:
    return plan_folder.resolve(make_plan_repo(tmp_path, phase_count=1))


def make_summary(folder: PlanFolder, *, failed: bool = False) -> RunSummary:
    phase = Phase(number=1, path=folder.path / "01-step-1.md")
    result = PhaseResult(
        phase=phase,
        success=not failed,
        elapsed_seconds=1344.0,
        message="verify failed\non the second line" if failed else None,
        cost_usd=0.42,
    )
    return RunSummary(
        completed=0 if failed else 1,
        failed=1 if failed else 0,
        total=1,
        started_at=STARTED,
        ended_at=STARTED + timedelta(days=1, hours=1, minutes=32),
        phases=(result,),
    )


def read_report(folder: PlanFolder) -> str:
    return (plan_folder.done_root(folder) / REPORT_FILE_NAME).read_text(encoding="utf-8")


def test_report_records_the_times_sessions_and_token_totals(
    tmp_path: Path, caplog_free_logger: AppLogger
) -> None:
    folder = make_folder(tmp_path)

    run_report.write(folder, make_summary(folder), SESSIONS, caplog_free_logger)

    report = read_report(folder)
    assert "# Implementation Report — demo" in report
    assert "## Run 1 — 2026-09-08 14:40:12" in report
    assert "| Ended | 2026-09-09 16:12:12 |" in report
    assert "| Duration | 1d 1h 32m |" in report
    assert "| Phases | 1 completed, 0 failed of 1 |" in report
    assert "| Claude sessions | 2 |" in report
    assert "| 01-step-1.md | done | 22.4 min | $0.42 |" in report
    assert "| 2 | commit | 1,120 | 210 | 40,010 | 0 | $0.03 |" in report
    assert "**13,550**" in report
    assert "**3,312**" in report
    assert "**520,230**" in report
    assert "**$0.45**" in report


def test_a_second_run_appends_without_repeating_the_title(
    tmp_path: Path, caplog_free_logger: AppLogger
) -> None:
    folder = make_folder(tmp_path)
    summary = make_summary(folder)

    run_report.write(folder, summary, SESSIONS, caplog_free_logger)
    run_report.write(folder, summary, SESSIONS, caplog_free_logger)

    report = read_report(folder)
    assert report.count("# Implementation Report") == 1
    assert "## Run 1 —" in report
    assert "## Run 2 —" in report


def test_failed_run_writes_error_md_naming_the_phase(
    tmp_path: Path, caplog_free_logger: AppLogger
) -> None:
    folder = make_folder(tmp_path)

    run_report.write(folder, make_summary(folder, failed=True), SESSIONS, caplog_free_logger)

    error = (folder.path / ERROR_FILE_NAME).read_text(encoding="utf-8")
    assert "01-step-1.md" in error
    # The Claude message is flattened so a multi-line failure cannot break the table.
    assert "| verify failed on the second line |" in error
    assert REPORT_FILE_NAME in error
    assert "## Run 1 —" in read_report(folder)


def test_a_successful_run_clears_a_stale_error_md(
    tmp_path: Path, caplog_free_logger: AppLogger
) -> None:
    folder = make_folder(tmp_path)
    stale = "# Failed Run — demo\n"
    (folder.path / ERROR_FILE_NAME).write_text(stale, encoding="utf-8")
    archived = plan_folder.done_root(folder)
    archived.mkdir(parents=True, exist_ok=True)
    (archived / ERROR_FILE_NAME).write_text(stale, encoding="utf-8")

    run_report.write(folder, make_summary(folder), SESSIONS, caplog_free_logger)

    assert not (folder.path / ERROR_FILE_NAME).exists()
    assert not (archived / ERROR_FILE_NAME).exists()


def test_duration_counts_days_hours_and_minutes() -> None:
    assert run_report.format_duration(0) == "0d 0h 0m"
    assert run_report.format_duration(2 * 86400 + 3 * 3600 + 4 * 60 + 59) == "2d 3h 4m"
