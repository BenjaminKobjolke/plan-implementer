"""Write what a run did into REPORT.md, and ERROR.md when it failed."""

from collections.abc import Sequence
from pathlib import Path

from plan_implementer import plan_folder
from plan_implementer.app_logger import AppLogger
from plan_implementer.constants import ERROR_FILE_NAME, REPORT_FILE_NAME
from plan_implementer.errors import OperationalError
from plan_implementer.models import PhaseResult, PlanFolder, RunSummary, SessionRecord, TokenUsage
from plan_implementer.tool_summary import truncate

_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
_RUN_HEADING = "\n## Run "
_MINUTES_PER_DAY = 24 * 60


def write(
    folder: PlanFolder,
    summary: RunSummary,
    sessions: Sequence[SessionRecord],
    logger: AppLogger,
) -> None:
    """Append this run to done/<feature>/REPORT.md; add ERROR.md on failure."""
    report_path = _append_report(folder, summary, sessions)
    logger.info(f"Report: {plan_folder.relative_to_repo(report_path, folder.repo_root)}")

    error_path = folder.path / ERROR_FILE_NAME
    if not summary.failed:
        # A stale ERROR.md would otherwise be read as live — and `archive()` may already have
        # swept it next to the report, so clear both places.
        _remove(error_path)
        _remove(report_path.parent / ERROR_FILE_NAME)
        return

    _write(error_path, _render_error(folder, summary, report_path))
    logger.error(f"Error report: {plan_folder.relative_to_repo(error_path, folder.repo_root)}")


def format_duration(seconds: float) -> str:
    """Render a run length as `0d 1h 32m`."""
    minutes = int(seconds // 60)
    days, minutes = divmod(minutes, _MINUTES_PER_DAY)
    hours, minutes = divmod(minutes, 60)
    return f"{days}d {hours}h {minutes}m"


def _append_report(
    folder: PlanFolder, summary: RunSummary, sessions: Sequence[SessionRecord]
) -> Path:
    destination = plan_folder.done_root(folder)
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / REPORT_FILE_NAME

    existing = _read(path)
    run_number = existing.count(_RUN_HEADING) + 1
    title = "" if existing else f"# Implementation Report — {folder.feature_name}\n"
    _write(path, existing + title + _render_run(run_number, summary, sessions))
    return path


def _render_run(number: int, summary: RunSummary, sessions: Sequence[SessionRecord]) -> str:
    started = summary.started_at.strftime(_TIMESTAMP_FORMAT)
    duration = format_duration((summary.ended_at - summary.started_at).total_seconds())
    lines = [
        "",
        f"## Run {number} — {started}",
        "",
        "| | |",
        "|---|---|",
        f"| Started | {started} |",
        f"| Ended | {summary.ended_at.strftime(_TIMESTAMP_FORMAT)} |",
        f"| Duration | {duration} |",
        f"| Phases | {summary.completed} completed, {summary.failed} failed of {summary.total} |",
        f"| Claude sessions | {len(sessions)} |",
        "",
        "### Phases",
        "",
        "| Phase | Status | Elapsed | Cost |",
        "|---|---|---|---|",
        *(_phase_row(result) for result in summary.phases),
        "",
        "### Claude sessions",
        "",
        "| # | Session | in | out | cache read | cache write | Cost |",
        "|---|---|---|---|---|---|---|",
        *(_session_row(number, record) for number, record in enumerate(sessions, start=1)),
        _totals_row(sessions),
        "",
    ]
    return "\n".join(lines)


def _phase_row(result: PhaseResult) -> str:
    status = "done" if result.success else "FAILED"
    elapsed = f"{result.elapsed_seconds / 60:.1f} min"
    return f"| {result.phase.name} | {status} | {elapsed} | {_cost(result.cost_usd)} |"


def _session_row(number: int, record: SessionRecord) -> str:
    usage = record.result.usage
    return (
        f"| {number} | {record.label} | {usage.input_tokens:,} | {usage.output_tokens:,} "
        f"| {usage.cache_read_tokens:,} | {usage.cache_creation_tokens:,} "
        f"| {_cost(record.result.cost_usd)} |"
    )


def _totals_row(sessions: Sequence[SessionRecord]) -> str:
    usage = sum((record.result.usage for record in sessions), TokenUsage())
    cost = sum(record.result.cost_usd or 0.0 for record in sessions)
    return (
        f"| **Total** | **{len(sessions)} sessions** | **{usage.input_tokens:,}** "
        f"| **{usage.output_tokens:,}** | **{usage.cache_read_tokens:,}** "
        f"| **{usage.cache_creation_tokens:,}** | **${cost:.2f}** |"
    )


def _render_error(folder: PlanFolder, summary: RunSummary, report_path: Path) -> str:
    report = plan_folder.relative_to_repo(report_path, folder.repo_root)
    lines = [
        f"# Failed Run — {folder.feature_name}",
        "",
        f"{summary.ended_at.strftime(_TIMESTAMP_FORMAT)} — {summary.completed} of "
        f"{summary.total} phases completed, {summary.failed} failed.",
        "",
        "| Phase | Elapsed | Reason |",
        "|---|---|---|",
        *(_error_row(result) for result in summary.phases if not result.success),
        "",
        f"Times, sessions and token totals for every run are in `{report}`.",
        "",
    ]
    return "\n".join(lines)


def _error_row(result: PhaseResult) -> str:
    # A Claude result message runs over several lines and may contain `|` — flatten both away
    # so one failure cannot break the table.
    reason = truncate(result.message or "unknown").replace("|", "\\|")
    return f"| {result.phase.name} | {result.elapsed_seconds / 60:.1f} min | {reason} |"


def _cost(value: float | None) -> str:
    return "-" if value is None else f"${value:.2f}"


def _read(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _write(path: Path, text: str) -> None:
    try:
        path.write_text(text, encoding="utf-8")
    except OSError as error:
        raise OperationalError(f"Could not write {path}: {error}") from error


def _remove(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as error:
        raise OperationalError(f"Could not remove {path}: {error}") from error
