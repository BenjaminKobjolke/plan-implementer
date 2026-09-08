"""Unit tests for plan folder resolution and bookkeeping."""

import shutil
from pathlib import Path

import pytest

from plan_implementer import plan_folder
from plan_implementer.errors import ConfigurationError, OperationalError
from tests.conftest import make_plan_repo


def test_resolve_derives_repo_root_from_plan_parent(plan_repo: Path) -> None:
    folder = plan_folder.resolve(plan_repo / "plan" / "demo")

    assert folder.repo_root == plan_repo
    assert folder.feature_name == "demo"
    assert folder.context_path == plan_repo / "plan" / "demo" / "00-context.md"


def test_resolve_falls_back_to_git_walk_up(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    folder_path = repo / "plans-elsewhere" / "demo"
    folder_path.mkdir(parents=True)
    (folder_path / "00-context.md").write_text("x", encoding="utf-8")

    assert plan_folder.resolve(folder_path).repo_root == repo


def test_resolve_accepts_project_override(tmp_path: Path) -> None:
    folder_path = tmp_path / "loose" / "demo"
    folder_path.mkdir(parents=True)
    (folder_path / "00-context.md").write_text("x", encoding="utf-8")
    override = tmp_path / "elsewhere"
    override.mkdir()

    assert plan_folder.resolve(folder_path, override).repo_root == override


def test_resolve_without_repo_root_is_configuration_error(tmp_path: Path) -> None:
    folder_path = tmp_path / "loose" / "demo"
    folder_path.mkdir(parents=True)
    (folder_path / "00-context.md").write_text("x", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="--project"):
        plan_folder.resolve(folder_path)


def test_resolve_requires_context_file(tmp_path: Path) -> None:
    folder_path = tmp_path / "plan" / "demo"
    folder_path.mkdir(parents=True)

    with pytest.raises(ConfigurationError, match=r"00-context\.md"):
        plan_folder.resolve(folder_path)


def test_phases_are_ordered_and_exclude_non_phase_files(tmp_path: Path) -> None:
    path = make_plan_repo(tmp_path, phase_count=3)
    (path / "original.md").write_text("x", encoding="utf-8")
    (path / "notes.md").write_text("x", encoding="utf-8")
    (path / "done").mkdir()
    (path / "done" / "01-already.md").write_text("x", encoding="utf-8")
    (path / "04-notes.log").write_text("x", encoding="utf-8")
    (path / "02-step-2-changed-files.md").write_text("x", encoding="utf-8")
    (path / "02-step-2-post-implementation-check.md").write_text("x", encoding="utf-8")
    folder = plan_folder.resolve(path)

    assert [phase.number for phase in plan_folder.phases(folder)] == [1, 2, 3]


def test_phases_can_select_a_single_phase(plan_repo: Path) -> None:
    folder = plan_folder.resolve(plan_repo / "plan" / "demo")

    selected = plan_folder.phases(folder, only="02")

    assert [phase.number for phase in selected] == [2]


def test_phases_rejects_an_unknown_selection(plan_repo: Path) -> None:
    folder = plan_folder.resolve(plan_repo / "plan" / "demo")

    with pytest.raises(ConfigurationError, match="09"):
        plan_folder.phases(folder, only="09")


def test_mark_done_moves_the_phase_into_plan_done(plan_repo: Path) -> None:
    folder = plan_folder.resolve(plan_repo / "plan" / "demo")
    phase = plan_folder.phases(folder)[0]

    destination = plan_folder.mark_done(folder, phase)

    assert destination == plan_repo / "plan" / "done" / "demo" / phase.name
    assert destination.exists()
    assert not phase.path.exists()


def test_mark_done_takes_the_phase_sidecars_along(plan_repo: Path) -> None:
    folder = plan_folder.resolve(plan_repo / "plan" / "demo")
    phase = plan_folder.phases(folder)[0]
    sidecars = ["01-step-1-changed-files.md", "01-step-1-post-impl-delegate.log"]
    for name in sidecars:
        (folder.path / name).write_text("workflow output", encoding="utf-8")

    plan_folder.mark_done(folder, phase)

    done_dir = plan_repo / "plan" / "done" / "demo"
    for name in sidecars:
        assert (done_dir / name).exists()
        assert not (folder.path / name).exists()
    # The next phase and its own files must stay put.
    assert (folder.path / "02-step-2.md").exists()


def test_mark_done_refuses_to_overwrite(plan_repo: Path) -> None:
    folder = plan_folder.resolve(plan_repo / "plan" / "demo")
    phase = plan_folder.phases(folder)[0]
    done_dir = plan_folder.done_root(folder)
    done_dir.mkdir(parents=True)
    (done_dir / phase.path.name).write_text("older", encoding="utf-8")

    with pytest.raises(OperationalError, match="already exists"):
        plan_folder.mark_done(folder, phase)


def test_done_root_keeps_a_dated_folder_name_as_is(tmp_path: Path) -> None:
    path = make_plan_repo(tmp_path, feature="20260908_demo")
    folder = plan_folder.resolve(path)

    assert plan_folder.done_root(folder) == tmp_path / "plan" / "done" / "20260908_demo"


def test_archive_moves_the_leftovers_and_drops_the_folder(plan_repo: Path) -> None:
    folder = plan_folder.resolve(plan_repo / "plan" / "demo")
    for phase in plan_folder.phases(folder):
        plan_folder.mark_done(folder, phase)

    archived = plan_folder.archive(folder)

    assert archived == plan_repo / "plan" / "done" / "demo"
    assert (archived / "00-context.md").exists()
    assert (archived / "01-step-1.md").exists()
    assert not folder.path.exists()


def test_archive_keeps_a_folder_that_still_holds_other_content(plan_repo: Path) -> None:
    folder = plan_folder.resolve(plan_repo / "plan" / "demo")
    (folder.path / "notes").mkdir()
    for phase in plan_folder.phases(folder):
        plan_folder.mark_done(folder, phase)

    plan_folder.archive(folder)

    assert folder.path.exists()
    assert (folder.path / "notes").exists()


def test_archive_is_a_no_op_while_phases_remain(plan_repo: Path) -> None:
    folder = plan_folder.resolve(plan_repo / "plan" / "demo")

    assert plan_folder.archive(folder) is None
    assert folder.path.exists()


def test_resolve_all_returns_the_single_folder_it_was_pointed_at(plan_repo: Path) -> None:
    folders = plan_folder.resolve_all(plan_repo / "plan" / "demo")

    assert [folder.feature_name for folder in folders] == ["demo"]
    assert folders[0].repo_root == plan_repo


def test_resolve_all_finds_every_plan_subfolder_of_a_plan_parent(tmp_path: Path) -> None:
    make_plan_repo(tmp_path, feature="20260908_second")
    make_plan_repo(tmp_path, feature="20260101_first")

    folders = plan_folder.resolve_all(tmp_path / "plan")

    assert [folder.feature_name for folder in folders] == ["20260101_first", "20260908_second"]
    assert {folder.repo_root for folder in folders} == {tmp_path}


def test_resolve_all_ignores_subfolders_without_a_context_file(tmp_path: Path) -> None:
    make_plan_repo(tmp_path)
    # The `done/` archive keeps its contexts one level deeper, so it never qualifies.
    (tmp_path / "plan" / "done" / "older").mkdir(parents=True)
    (tmp_path / "plan" / "done" / "older" / "00-context.md").write_text("x", encoding="utf-8")
    (tmp_path / "plan" / "scratch").mkdir()

    folders = plan_folder.resolve_all(tmp_path / "plan")

    assert [folder.feature_name for folder in folders] == ["demo"]


def test_resolve_all_prefers_the_folder_itself_over_its_subfolders(tmp_path: Path) -> None:
    make_plan_repo(tmp_path, feature="outer")
    make_plan_repo(tmp_path / "plan" / "outer", feature="inner")

    folders = plan_folder.resolve_all(tmp_path / "plan" / "outer")

    assert [folder.feature_name for folder in folders] == ["outer"]


def test_resolve_all_without_any_plan_folder_is_configuration_error(tmp_path: Path) -> None:
    (tmp_path / "plan" / "scratch").mkdir(parents=True)

    with pytest.raises(ConfigurationError, match=r"00-context\.md"):
        plan_folder.resolve_all(tmp_path / "plan")


def test_resolve_all_requires_an_existing_folder(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="does not exist"):
        plan_folder.resolve_all(tmp_path / "nope")


def _folder_in_state(root: Path, state: str, feature: str = "demo") -> Path:
    """A plan folder sitting in `plan/<state>/`, as an interrupted or failed run leaves it."""
    source = make_plan_repo(root, feature=feature)
    destination = root / "plan" / state / feature
    destination.parent.mkdir(exist_ok=True)
    shutil.move(str(source), str(destination))
    return destination


@pytest.mark.parametrize("state", ["", "implementing", "errors", "done"])
def test_plan_parent_sees_through_a_state_directory(tmp_path: Path, state: str) -> None:
    path = make_plan_repo(tmp_path) if not state else _folder_in_state(tmp_path, state)
    folder = plan_folder.resolve(path)

    assert plan_folder.plan_parent(folder) == tmp_path / "plan"
    assert folder.repo_root == tmp_path


def test_claim_moves_the_folder_into_implementing(plan_repo: Path) -> None:
    folder = plan_folder.resolve(plan_repo / "plan" / "demo")

    claimed = plan_folder.claim(folder)

    assert claimed.path == plan_repo / "plan" / "implementing" / "demo"
    assert claimed.context_path == claimed.path / "00-context.md"
    assert claimed.repo_root == plan_repo
    assert (claimed.path / "01-step-1.md").exists()
    assert not (plan_repo / "plan" / "demo").exists()


def test_claim_refuses_a_folder_another_run_holds(plan_repo: Path) -> None:
    folder = plan_folder.resolve(plan_repo / "plan" / "demo")
    (plan_repo / "plan" / "implementing" / "demo").mkdir(parents=True)

    with pytest.raises(OperationalError, match="not overwriting"):
        plan_folder.claim(folder)


def test_claim_adopts_a_folder_already_in_implementing(tmp_path: Path) -> None:
    path = _folder_in_state(tmp_path, "implementing")
    folder = plan_folder.resolve(path)

    claimed = plan_folder.claim(folder)

    assert claimed.path == path
    assert (path / "01-step-1.md").exists()


def test_claim_from_errors_moves_to_implementing(tmp_path: Path) -> None:
    folder = plan_folder.resolve(_folder_in_state(tmp_path, "errors"))

    claimed = plan_folder.claim(folder)

    assert claimed.path == tmp_path / "plan" / "implementing" / "demo"
    assert not (tmp_path / "plan" / "errors" / "implementing").exists()


def test_done_root_and_mark_done_ignore_the_implementing_level(plan_repo: Path) -> None:
    claimed = plan_folder.claim(plan_folder.resolve(plan_repo / "plan" / "demo"))

    assert plan_folder.done_root(claimed) == plan_repo / "plan" / "done" / "demo"

    moved = plan_folder.mark_done(claimed, plan_folder.phases(claimed)[0])

    assert moved == plan_repo / "plan" / "done" / "demo" / "01-step-1.md"


@pytest.mark.parametrize(
    ("failed", "expected"), [(False, ("plan", "demo")), (True, ("plan", "errors", "demo"))]
)
def test_release_moves_the_folder_to_its_state_directory(
    plan_repo: Path, failed: bool, expected: tuple[str, ...]
) -> None:
    claimed = plan_folder.claim(plan_folder.resolve(plan_repo / "plan" / "demo"))
    (claimed.path / "ERROR.md").write_text("x", encoding="utf-8")

    released = plan_folder.release(claimed, failed=failed)

    assert released.path == plan_repo.joinpath(*expected)
    assert released.context_path == released.path / "00-context.md"
    assert (released.path / "01-step-1.md").exists()
    assert (released.path / "ERROR.md").exists()
    assert not (plan_repo / "plan" / "implementing").exists()


def test_release_after_archive_only_drops_the_implementing_dir(plan_repo: Path) -> None:
    claimed = plan_folder.claim(plan_folder.resolve(plan_repo / "plan" / "demo"))
    for phase in plan_folder.phases(claimed):
        plan_folder.mark_done(claimed, phase)
    plan_folder.archive(claimed)

    plan_folder.release(claimed, failed=False)

    assert not (plan_repo / "plan" / "implementing").exists()
    assert not (plan_repo / "plan" / "demo").exists()
    assert (plan_repo / "plan" / "done" / "demo" / "00-context.md").exists()


def test_release_keeps_implementing_while_another_folder_is_claimed(tmp_path: Path) -> None:
    make_plan_repo(tmp_path, feature="first")
    make_plan_repo(tmp_path, feature="second")
    first = plan_folder.claim(plan_folder.resolve(tmp_path / "plan" / "first"))
    plan_folder.claim(plan_folder.resolve(tmp_path / "plan" / "second"))

    plan_folder.release(first, failed=False)

    assert (tmp_path / "plan" / "implementing" / "second").is_dir()
    assert (tmp_path / "plan" / "first").is_dir()


def test_release_is_a_no_op_for_an_unclaimed_folder(plan_repo: Path) -> None:
    folder = plan_folder.resolve(plan_repo / "plan" / "demo")

    released = plan_folder.release(folder, failed=True)

    assert released.path == folder.path
    assert not (plan_repo / "plan" / "errors").exists()


def test_resolve_all_skips_claimed_and_parked_folders(tmp_path: Path) -> None:
    make_plan_repo(tmp_path)
    _folder_in_state(tmp_path, "implementing", feature="running")
    _folder_in_state(tmp_path, "errors", feature="broken")

    folders = plan_folder.resolve_all(tmp_path / "plan")

    assert [folder.feature_name for folder in folders] == ["demo"]
