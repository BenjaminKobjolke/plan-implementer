"""Unit tests for settings resolution."""

import json
from pathlib import Path

import pytest

from plan_implementer.constants import (
    DEFAULT_IDLE_TIMEOUT_SECONDS,
    DEFAULT_MAX_REPEATED_LINES,
    DEFAULT_PERMISSION_MODE,
    ENV_COMMIT,
    ENV_IDLE_TIMEOUT,
    ENV_MAX_REPEATED_LINES,
    ENV_PERMISSION_MODE,
)
from plan_implementer.errors import ConfigurationError
from plan_implementer.settings import Settings


def test_defaults_apply_without_a_settings_file(tmp_path: Path) -> None:
    settings = Settings.load(tmp_path / "missing.json")

    assert settings.commit == ""
    assert settings.permission_mode == DEFAULT_PERMISSION_MODE
    assert settings.idle_timeout_seconds == DEFAULT_IDLE_TIMEOUT_SECONDS
    assert settings.max_repeated_lines == DEFAULT_MAX_REPEATED_LINES


def test_settings_file_is_read(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({"commit": "/git:commit", "permission_mode": "auto"}), encoding="utf-8"
    )

    settings = Settings.load(path)

    assert settings.commit == "/git:commit"
    assert settings.permission_mode == "auto"


def test_environment_overrides_the_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"commit": "/git:commit"}), encoding="utf-8")
    monkeypatch.setenv(ENV_COMMIT, "git commit -am wip")
    monkeypatch.setenv(ENV_PERMISSION_MODE, "auto")

    settings = Settings.load(path)

    assert settings.commit == "git commit -am wip"
    assert settings.permission_mode == "auto"


def test_invalid_settings_file_is_a_configuration_error(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"commit": 5}', encoding="utf-8")

    with pytest.raises(ConfigurationError):
        Settings.load(path)


def test_limits_are_read_from_the_file(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({"idle_timeout_seconds": 60, "max_repeated_lines": 0}), encoding="utf-8"
    )

    settings = Settings.load(path)

    assert settings.idle_timeout_seconds == 60
    assert settings.max_repeated_lines == 0


def test_environment_overrides_the_limits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"idle_timeout_seconds": 60}), encoding="utf-8")
    monkeypatch.setenv(ENV_IDLE_TIMEOUT, "120")
    monkeypatch.setenv(ENV_MAX_REPEATED_LINES, "5")

    settings = Settings.load(path)

    assert settings.idle_timeout_seconds == 120
    assert settings.max_repeated_lines == 5


def test_a_non_numeric_limit_is_a_configuration_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_IDLE_TIMEOUT, "half an hour")

    with pytest.raises(ConfigurationError):
        Settings.load(Path("missing.json"))
