"""Implement plan phases sequentially, one fresh Claude session per phase."""

import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from plan_implementer import plan_folder, prompt_builder
from plan_implementer.app_logger import AppLogger
from plan_implementer.claude_runner import ClaudeRun
from plan_implementer.committer import Committer
from plan_implementer.models import Phase, PhaseResult, PlanFolder, ProjectType, RunSummary

_SEPARATOR = "=" * 70
_RULE = "-" * 70


@dataclass(frozen=True)
class RunContext:
    """Everything a run needs to know about what it is implementing."""

    folder: PlanFolder
    project_type: ProjectType
    continue_on_failure: bool


class PhaseRunner:
    """Drive the plan folder's phases, keeping `done/` and commits in step."""

    def __init__(
        self,
        context: RunContext,
        claude: ClaudeRun,
        committer: Committer,
        logger: AppLogger,
    ) -> None:
        self._context = context
        self._claude = claude
        self._committer = committer
        self._logger = logger

    def run(self, phases: Sequence[Phase]) -> RunSummary:
        """Implement `phases` in order and report what happened."""
        total = len(phases)
        self._logger.info(_SEPARATOR)
        self._logger.info(f"Repository:   {self._context.folder.repo_root}")
        self._logger.info(f"Plan folder:  {self._context.folder.path}")
        self._logger.info(f"Project type: {self._context.project_type.name}")
        self._logger.info(f"Phases:       {total}")
        self._logger.info(_SEPARATOR)

        started_at = datetime.now()
        completed = 0
        failed = 0
        results: list[PhaseResult] = []

        for index, phase in enumerate(phases, start=1):
            result = self._run_phase(phase, index, total)
            results.append(result)

            if not result.success:
                failed += 1
                if not self._context.continue_on_failure:
                    self._logger.error("Stopping.")
                    break
                continue

            completed += 1

        archived = plan_folder.archive(self._context.folder) if failed == 0 else None
        if archived is not None:
            self._logger.info(f"Plan complete - all phase files are now in {archived}")

        self._logger.info("")
        self._logger.info(_SEPARATOR)
        self._logger.info(f"Completed: {completed}/{total}   Failed: {failed}")
        self._logger.info(_SEPARATOR)

        return RunSummary(
            completed=completed,
            failed=failed,
            total=total,
            started_at=started_at,
            ended_at=datetime.now(),
            archived_to=archived,
            phases=tuple(results),
        )

    def _run_phase(self, phase: Phase, index: int, total: int) -> PhaseResult:
        self._logger.info("")
        self._logger.info(_SEPARATOR)
        self._logger.info(f"[{index}/{total}] {phase.name}")
        self._logger.info(_SEPARATOR)

        prompt = prompt_builder.build_phase_prompt(
            self._context.folder, phase, self._context.project_type
        )
        started = time.monotonic()
        result = self._claude.run(prompt, self._context.folder.repo_root, label=phase.name)
        elapsed = time.monotonic() - started

        self._logger.info("")
        self._logger.info(_RULE)

        if not result.success:
            self._report_failure(phase, result.result_message, elapsed)
            return PhaseResult(
                phase=phase,
                success=False,
                elapsed_seconds=elapsed,
                message=result.result_message,
                cost_usd=result.cost_usd,
            )

        destination = plan_folder.mark_done(self._context.folder, phase)
        moved_to = plan_folder.relative_to_repo(destination, self._context.folder.repo_root)
        self._logger.info(f"Done: {phase.name} -> {moved_to}")

        if not self._committer.commit(self._context.folder.repo_root):
            self._logger.error(
                f"Commit failed for {phase.name}. The phase IS implemented and was moved to "
                f"{moved_to}, but the changes are NOT committed."
            )
            return PhaseResult(
                phase=phase,
                success=False,
                elapsed_seconds=elapsed,
                message="commit failed",
                cost_usd=result.cost_usd,
            )

        self._logger.info(f"Elapsed: {elapsed / 60:.1f} minutes")
        if result.cost_usd is not None:
            self._logger.info(f"Cost: ${result.cost_usd:.2f}")

        return PhaseResult(
            phase=phase, success=True, elapsed_seconds=elapsed, cost_usd=result.cost_usd
        )

    def _report_failure(self, phase: Phase, message: str | None, elapsed: float) -> None:
        self._logger.error(f"FAILED: {phase.name}")
        self._logger.error(f"Elapsed: {elapsed / 60:.1f} minutes")
        if message:
            self._logger.error(f"Claude result: {message}")
        self._logger.error("The phase file was NOT moved. No commit was created.")
