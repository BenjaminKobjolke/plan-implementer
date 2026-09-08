"""Shared fixtures: temporary repositories with a multi-step plan folder."""

from pathlib import Path

import pytest

CONTEXT_BODY = "# Context — Demo (shared reference for all phases)\n"
PHASE_BODY = "# Phase {number} — Demo\n\n1. Do the thing.\n\n## Verify\n\n- `uv run pytest`\n"


def make_plan_repo(root: Path, feature: str = "demo", phase_count: int = 2) -> Path:
    """Create <root>/plan/<feature>/ with a context file and NN phase files."""
    plan_folder = root / "plan" / feature
    plan_folder.mkdir(parents=True)
    (plan_folder / "00-context.md").write_text(CONTEXT_BODY, encoding="utf-8")
    for number in range(1, phase_count + 1):
        name = f"{number:02d}-step-{number}.md"
        (plan_folder / name).write_text(PHASE_BODY.format(number=number), encoding="utf-8")
    return plan_folder


@pytest.fixture
def plan_repo(tmp_path: Path) -> Path:
    """A repo root holding plan/demo/ with two phases."""
    make_plan_repo(tmp_path)
    return tmp_path
