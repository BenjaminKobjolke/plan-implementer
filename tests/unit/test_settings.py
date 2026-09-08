"""Unit tests for settings resolution."""

import json
from pathlib import Path

import pytest

from plan_implementer.constants import DEFAULT_PERMISSION_MODE, ENV_COMMIT, ENV_PERMISSION_MODE
from plan_implementer.errors import ConfigurationError
from plan_implementer.settings import Settings


def test_defaults_apply_without_a_settings_file(tmp_path: Path) -> None:
    settings = Settings.load(tmp_path / "missing.json")

    assert settings.commit == ""
    assert settings.permission_mode == DEFAULT_PERMISSION_MODE


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
