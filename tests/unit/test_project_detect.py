"""Unit tests for project type detection and verify-command resolution."""

from pathlib import Path

import pytest

from plan_implementer import project_detect
from plan_implementer.constants import DEFAULT_PROJECT_TYPES_CONFIG, UNKNOWN_PROJECT_TYPE

CONFIG = project_detect.load_config(DEFAULT_PROJECT_TYPES_CONFIG)

# One marker file per configured type, taken from the production config so the
# table cannot drift from config/project_types.json.
MARKER_FILES = {
    "unity": "ProjectSettings/ProjectVersion.txt",
    "flutter": "pubspec.yaml",
    "svelte": "svelte.config.js",
    "node": "package.json",
    "php": "composer.json",
    "python": "pyproject.toml",
    "csharp": "App.csproj",
    "arduino": "platformio.ini",
}
MARKER_CONTENT = {"flutter": "name: demo\nflutter:\n  uses-material-design: true\n"}


def write(root: Path, relative: str, content: str = "x") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.mark.parametrize("expected_type", sorted(MARKER_FILES))
def test_every_configured_type_is_detected_from_its_marker(
    tmp_path: Path, expected_type: str
) -> None:
    write(tmp_path, MARKER_FILES[expected_type], MARKER_CONTENT.get(expected_type, "x"))

    detected = project_detect.detect(tmp_path, CONFIG)

    assert detected.name == expected_type


def test_every_configured_type_is_covered_by_the_table() -> None:
    assert set(MARKER_FILES) == set(CONFIG)


def test_pubspec_without_flutter_key_is_not_flutter(tmp_path: Path) -> None:
    write(tmp_path, "pubspec.yaml", "name: pure_dart\n")

    assert project_detect.detect(tmp_path, CONFIG).name == UNKNOWN_PROJECT_TYPE


def test_higher_priority_marker_wins(tmp_path: Path) -> None:
    write(tmp_path, "package.json", "{}")
    write(tmp_path, "svelte.config.js")

    assert project_detect.detect(tmp_path, CONFIG).name == "svelte"


def test_fvm_prefix_is_applied_when_the_marker_exists(tmp_path: Path) -> None:
    write(tmp_path, "pubspec.yaml", MARKER_CONTENT["flutter"])
    write(tmp_path, ".fvmrc", "{}")

    commands = [entry.command for entry in project_detect.detect(tmp_path, CONFIG).verify]

    assert commands == ["fvm flutter analyze", "fvm flutter test"]


def test_bat_override_replaces_the_same_role_and_is_listed_first(tmp_path: Path) -> None:
    write(tmp_path, "pyproject.toml", "[project]\n")
    write(tmp_path, "tools/run_tests.bat", "@echo off\n")

    commands = [entry.command for entry in project_detect.detect(tmp_path, CONFIG).verify]

    assert commands[0] == r"tools\run_tests.bat"
    assert "uv run pytest" not in commands
    assert "uv run mypy" in commands


def test_unknown_stack_still_reports_its_bats(tmp_path: Path) -> None:
    write(tmp_path, "tools/analyze_code.bat", "@echo off\n")

    detected = project_detect.detect(tmp_path, CONFIG)

    assert detected.name == UNKNOWN_PROJECT_TYPE
    assert [entry.command for entry in detected.verify] == [r"tools\analyze_code.bat"]


def test_unknown_stack_without_bats_has_no_commands(tmp_path: Path) -> None:
    detected = project_detect.detect(tmp_path, CONFIG)

    assert detected.name == UNKNOWN_PROJECT_TYPE
    assert detected.verify == ()
