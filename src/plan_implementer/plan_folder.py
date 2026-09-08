"""Resolve a multi-step plan folder and keep its state and `done/` bookkeeping."""

import shutil
from contextlib import suppress
from dataclasses import replace
from pathlib import Path

from plan_implementer.constants import (
    CONTEXT_FILE_NAME,
    DONE_DIR_NAME,
    ERRORS_DIR_NAME,
    GIT_DIR_NAME,
    IMPLEMENTING_DIR_NAME,
    PHASE_FILE_PATTERN,
    PLAN_DIR_NAME,
    STATE_DIR_NAMES,
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


def resolve_all(plan_path: Path, project_override: Path | None = None) -> list[PlanFolder]:
    """One plan folder, or every plan subfolder of a `plan/` parent, in name order.

    `done/` needs no special case: its archived contexts sit one level deeper, so it never
    qualifies as a plan folder itself.
    """
    folder = plan_path.resolve()
    if not folder.is_dir():
        raise ConfigurationError(f"Plan folder does not exist: {folder}")

    if (folder / CONTEXT_FILE_NAME).is_file():
        return [resolve(folder, project_override)]

    nested = sorted(
        path for path in folder.iterdir() if path.is_dir() and (path / CONTEXT_FILE_NAME).is_file()
    )
    if not nested:
        raise ConfigurationError(
            f"No {CONTEXT_FILE_NAME} in {folder} and no subfolder holding one."
        )
    return [resolve(path, project_override) for path in nested]


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


def plan_parent(folder: PlanFolder) -> Path:
    """The `plan/` dir this folder belongs to, seeing through a state-directory level."""
    return _plan_dir(folder.path)


def done_root(folder: PlanFolder) -> Path:
    """`plan/done/<folder-name>/` — where finished phases of this plan live."""
    return plan_parent(folder) / DONE_DIR_NAME / folder.feature_name


def mark_done(folder: PlanFolder, phase: Phase) -> Path:
    """Move a finished phase file and its sidecars next to the other finished phases."""
    destination_dir = done_root(folder)
    destination_dir.mkdir(parents=True, exist_ok=True)

    for source in (phase.path, *_sidecars(folder, phase)):
        _move_path(source, destination_dir / source.name)

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
        _move_path(leftover, destination_dir / leftover.name)

    # Anything left is not ours to delete (nested folders, tooling output) — keep it.
    if not any(folder.path.iterdir()):
        folder.path.rmdir()

    return destination_dir


def claim(folder: PlanFolder) -> PlanFolder:
    """Move the folder into `implementing/`, where a concurrent run cannot see it.

    `resolve_all` only looks at immediate subfolders for a context file, so a folder one level
    deeper is skipped — the same reason `done/` needs no special case.
    """
    if folder.path.parent.name == IMPLEMENTING_DIR_NAME:
        return folder  # already there: an interrupted run's leftover, pointed at directly
    return _move(folder, plan_parent(folder) / IMPLEMENTING_DIR_NAME / folder.feature_name)


def release(folder: PlanFolder, failed: bool) -> PlanFolder:
    """Park a failed plan in `errors/`, put any other one back next to the waiting plans."""
    holding_dir = folder.path.parent
    if holding_dir.name != IMPLEMENTING_DIR_NAME:
        return folder

    parent = holding_dir.parent
    destination = (parent / ERRORS_DIR_NAME if failed else parent) / folder.feature_name
    # Nothing to move when the run archived the folder away.
    released = _move(folder, destination) if folder.path.is_dir() else folder
    with suppress(OSError):  # not empty: another run still holds a folder in there
        holding_dir.rmdir()
    return released


def _move(folder: PlanFolder, destination: Path) -> PlanFolder:
    """Relocate the whole plan folder and repoint it; `repo_root` is unaffected by the move."""
    _move_path(folder.path, destination)
    return replace(folder, path=destination, context_path=destination / CONTEXT_FILE_NAME)


def _move_path(source: Path, destination: Path) -> Path:
    """The one move in this module: never overwrite, and create the parent on the way."""
    if destination.exists():
        raise OperationalError(f"Destination already exists, not overwriting: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))
    return destination


def relative_to_repo(path: Path, repo_root: Path) -> str:
    """Render a path for the console and for prompts, repo-relative where possible."""
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _plan_dir(folder: Path) -> Path:
    """The `plan/` dir owning this folder — one level up, or two through a state directory."""
    parent = folder.parent
    return parent.parent if parent.name in STATE_DIR_NAMES else parent


def _find_repo_root(folder: Path) -> Path:
    """`<repo>/plan/<feature>` by convention, otherwise the nearest `.git` ancestor."""
    plan_dir = _plan_dir(folder)
    if plan_dir.name == PLAN_DIR_NAME:
        return plan_dir.parent

    for candidate in folder.parents:
        if (candidate / GIT_DIR_NAME).exists():
            return candidate

    raise ConfigurationError(
        f"Cannot derive the repository root from {folder} — pass --project <path> explicitly."
    )
