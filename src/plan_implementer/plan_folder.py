"""Resolve a multi-step plan folder and keep its `done/` bookkeeping."""

import shutil
from pathlib import Path

from plan_implementer.constants import (
    CONTEXT_FILE_NAME,
    DONE_DIR_NAME,
    GIT_DIR_NAME,
    PHASE_FILE_PATTERN,
    PLAN_DIR_NAME,
    WORKFLOW_ARTIFACT_SUFFIXES,
)
from plan_implementer.errors import ConfigurationError, OperationalError
from plan_implementer.models import Phase, PlanFolder


def resolve(plan_path: Path, project_override: Path | None = None) -> PlanFolder:
    """Validate a plan folder and work out which repository it belongs to."""
    folder = plan_path.resolve()
    if not folder.is_dir():
        raise ConfigurationError(f"Plan folder does not exist: {folder}")

    context_path = folder / CONTEXT_FILE_NAME
    if not context_path.is_file():
        raise ConfigurationError(f"Plan folder has no {CONTEXT_FILE_NAME}: {folder}")

    repo_root = project_override.resolve() if project_override else _find_repo_root(folder)
    return PlanFolder(path=folder, repo_root=repo_root, context_path=context_path)


def phases(folder: PlanFolder, only: str | None = None) -> list[Phase]:
    """Remaining phases in `NN` order; `only` selects a single one by its prefix."""
    found = [
        Phase(number=int(match.group("number")), path=path)
        for path in folder.path.iterdir()
        if path.is_file()
        and (match := PHASE_FILE_PATTERN.match(path.name))
        and path.name != CONTEXT_FILE_NAME
        and not path.stem.endswith(WORKFLOW_ARTIFACT_SUFFIXES)
    ]
    found.sort(key=lambda phase: phase.number)

    if only is None:
        return found

    wanted = int(only)
    selected = [phase for phase in found if phase.number == wanted]
    if not selected:
        raise ConfigurationError(f"No remaining phase {only} in {folder.path}")
    return selected


def done_root(folder: PlanFolder) -> Path:
    """`plan/done/<folder-name>/` — where finished phases of this plan live."""
    return folder.path.parent / DONE_DIR_NAME / folder.feature_name


def mark_done(folder: PlanFolder, phase: Phase) -> Path:
    """Move a finished phase file and its sidecars next to the other finished phases."""
    destination_dir = done_root(folder)
    destination_dir.mkdir(parents=True, exist_ok=True)

    for source in (phase.path, *_sidecars(folder, phase)):
        destination = destination_dir / source.name
        if destination.exists():
            raise OperationalError(f"Destination already exists, not overwriting: {destination}")
        shutil.move(str(source), str(destination))

    return destination_dir / phase.name


def _sidecars(folder: PlanFolder, phase: Phase) -> list[Path]:
    """The workflow output written next to a phase: reports and delegate logs named `<stem>-*`.

    Matched by prefix rather than by `WORKFLOW_ARTIFACT_SUFFIXES` so the delegate logs travel
    with their phase too. Phase numbers are unique, so the prefix cannot catch another phase.
    """
    prefix = f"{phase.path.stem}-"
    return sorted(
        path for path in folder.path.iterdir() if path.is_file() and path.name.startswith(prefix)
    )


def archive(folder: PlanFolder) -> Path | None:
    """Move the leftovers of a fully implemented plan and drop the empty folder."""
    if phases(folder):
        return None

    destination_dir = done_root(folder)
    destination_dir.mkdir(parents=True, exist_ok=True)

    for leftover in sorted(folder.path.iterdir()):
        if not leftover.is_file():
            continue
        destination = destination_dir / leftover.name
        if destination.exists():
            raise OperationalError(f"Destination already exists, not overwriting: {destination}")
        shutil.move(str(leftover), str(destination))

    # Anything left is not ours to delete (nested folders, tooling output) — keep it.
    if not any(folder.path.iterdir()):
        folder.path.rmdir()

    return destination_dir


def relative_to_repo(path: Path, repo_root: Path) -> str:
    """Render a path for the console and for prompts, repo-relative where possible."""
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _find_repo_root(folder: Path) -> Path:
    """`<repo>/plan/<feature>` by convention, otherwise the nearest `.git` ancestor."""
    if folder.parent.name == PLAN_DIR_NAME:
        return folder.parent.parent

    for candidate in folder.parents:
        if (candidate / GIT_DIR_NAME).exists():
            return candidate

    raise ConfigurationError(
        f"Cannot derive the repository root from {folder} — pass --project <path> explicitly."
    )
