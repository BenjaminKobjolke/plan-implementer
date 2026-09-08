"""Command line entry point: argument parsing and wiring."""

import argparse
from collections.abc import Sequence
from pathlib import Path

from plan_implementer import plan_folder, project_detect, run_report
from plan_implementer.app_logger import AppLogger
from plan_implementer.claude_runner import ClaudeRunner
from plan_implementer.committer import Committer
from plan_implementer.errors import ConfigurationError, PlanImplementerError
from plan_implementer.models import Phase, PlanFolder, ProjectType
from plan_implementer.runner import PhaseRunner, RunContext
from plan_implementer.settings import Settings

EXIT_OK = 0
EXIT_FAILED_PHASE = 1
EXIT_CONFIGURATION = 2


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return the process exit code."""
    arguments = _parse_arguments(argv)
    logger = AppLogger()

    try:
        return _run(arguments, logger)
    except PlanImplementerError as error:
        logger.error(f"ERROR: {error}")
        return EXIT_CONFIGURATION
    except KeyboardInterrupt:
        logger.error("Interrupted.")
        return EXIT_CONFIGURATION


def _run(arguments: argparse.Namespace, logger: AppLogger) -> int:
    settings = Settings.load()
    folders = plan_folder.resolve_all(Path(arguments.plan_folder), arguments.project)
    config = project_detect.load_config(settings.project_types_config)
    commit_spec = "" if arguments.no_commit else (arguments.commit or settings.commit)

    if len(folders) > 1:
        logger.info(f"{len(folders)} plan folders: {', '.join(f.feature_name for f in folders)}")

    exit_code = EXIT_OK
    for folder in folders:
        try:
            phases = plan_folder.phases(folder, arguments.phase)
        except ConfigurationError:
            # `--phase NN` naming a phase this folder no longer has: skip it rather than abort
            # the whole run. A single folder keeps the explicit error.
            if len(folders) == 1:
                raise
            logger.info(f"No phase {arguments.phase} left in {folder.path} - skipped")
            continue

        project_type = project_detect.detect(folder.repo_root, config)

        if not phases:
            logger.info(f"No phases left in {folder.path}")
            archived = plan_folder.archive(folder)
            if archived is not None:
                logger.info(f"Plan complete - archived to {archived}")
            continue

        if arguments.dry_run:
            _render_dry_run(folder, phases, project_type, commit_spec, logger)
            continue

        if _implement(folder, phases, project_type, commit_spec, arguments, settings, logger):
            continue

        exit_code = EXIT_FAILED_PHASE
        if not arguments.continue_on_failure:
            break

    return exit_code


def _implement(
    folder: PlanFolder,
    phases: Sequence[Phase],
    project_type: ProjectType,
    commit_spec: str,
    arguments: argparse.Namespace,
    settings: Settings,
    logger: AppLogger,
) -> bool:
    """Implement one plan folder; `True` when every phase succeeded."""
    # A fresh runner per folder: `sessions` is cumulative, and each folder's REPORT.md must list
    # only its own sessions.
    claude = ClaudeRunner(logger, settings.permission_mode)
    runner = PhaseRunner(
        RunContext(
            folder=folder,
            project_type=project_type,
            continue_on_failure=arguments.continue_on_failure,
        ),
        claude,
        Committer(commit_spec, claude, logger),
        logger,
    )
    summary = runner.run(phases)
    run_report.write(folder, summary, claude.sessions, logger)
    return not summary.failed


def _render_dry_run(
    folder: PlanFolder,
    phases: Sequence[Phase],
    project_type: ProjectType,
    commit_spec: str,
    logger: AppLogger,
) -> None:
    logger.info(f"Repository:   {folder.repo_root}")
    logger.info(f"Plan folder:  {folder.path}")
    logger.info(f"Project type: {project_type.name}")
    logger.info(f"Commit:       {commit_spec or '(disabled)'}")
    logger.info("Verify commands:")
    for entry in project_type.verify:
        logger.info(f"  [{entry.role}] {entry.command}")
    if not project_type.verify:
        logger.info("  (none - Claude picks them from CLAUDE.md)")
    logger.info("Phases:")
    for phase in phases:
        logger.info(f"  {phase.label}  {phase.name}")


def _parse_arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="plan-implementer",
        description=(
            "Implement the phases of a multi-step plan folder "
            "(plan/<feature>/) sequentially with headless Claude Code."
        ),
    )
    parser.add_argument(
        "plan_folder",
        help=(
            "Path to plan/<feature>/ containing 00-context.md, or the plan/ parent "
            "to implement every plan subfolder in name order"
        ),
    )
    parser.add_argument(
        "--project",
        type=Path,
        default=None,
        help="Repository root, when it cannot be derived from the plan folder path",
    )
    parser.add_argument(
        "--phase",
        default=None,
        metavar="NN",
        help=(
            "Implement only this phase (e.g. 03) instead of every remaining one; "
            "with several plan folders it applies to each of them"
        ),
    )
    parser.add_argument(
        "--commit",
        default=None,
        help='Commit spec for this run: a Claude prompt ("/git:commit") or a shell command',
    )
    parser.add_argument("--no-commit", action="store_true", help="Do not commit after a phase")
    parser.add_argument(
        "--continue-on-failure",
        action="store_true",
        help="Keep going after a failed phase instead of stopping",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the resolved repository, project type, checks and phases, then exit",
    )
    return parser.parse_args(argv)
