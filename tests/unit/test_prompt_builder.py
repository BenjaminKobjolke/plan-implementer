"""Unit tests for the per-phase prompt."""

from pathlib import Path

from plan_implementer import plan_folder, prompt_builder
from plan_implementer.models import ProjectType, VerifyCommand

PYTHON_TYPE = ProjectType(
    name="python",
    verify=(
        VerifyCommand(role="test", command="uv run pytest"),
        VerifyCommand(role="analyze", command="uv run mypy"),
    ),
)


def build(plan_repo: Path, project_type: ProjectType = PYTHON_TYPE) -> str:
    folder = plan_folder.resolve(plan_repo / "plan" / "demo")
    phase = plan_folder.phases(folder)[0]
    return prompt_builder.build_phase_prompt(folder, phase, project_type)


def test_prompt_names_the_context_and_phase_paths(plan_repo: Path) -> None:
    prompt = build(plan_repo)

    assert "plan/demo/00-context.md" in prompt
    assert "plan/demo/01-step-1.md" in prompt


def test_prompt_lists_verify_commands_not_already_in_the_phase(plan_repo: Path) -> None:
    prompt = build(plan_repo)

    # The fixture phase file already asks for `uv run pytest` in its Verify section.
    assert prompt.count("uv run pytest") == 0
    assert "uv run mypy" in prompt


def test_prompt_forbids_moving_the_phase_file_and_committing(plan_repo: Path) -> None:
    prompt = build(plan_repo)

    assert "Do NOT move, rename or delete" in prompt
    assert "Do NOT commit" in prompt


def test_prompt_forbids_backgrounded_checks(plan_repo: Path) -> None:
    prompt = build(plan_repo)

    assert "NEVER use `run_in_background: true`" in prompt
    assert "never poll a task output file in a loop" in prompt


def test_prompt_without_commands_tells_claude_to_pick_them(plan_repo: Path) -> None:
    prompt = build(plan_repo, ProjectType(name="unknown", verify=()))

    assert "CLAUDE.md" in prompt
