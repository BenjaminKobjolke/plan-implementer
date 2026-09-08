"""Unit tests for the slash command installer."""

from pathlib import Path
from urllib.error import URLError

import pytest

from plan_implementer.app_logger import AppLogger
from plan_implementer.constants import COMMANDS_RAW_BASE, INSTALLED_COMMANDS
from plan_implementer.skill_installer import install_commands

SILENT = AppLogger(enabled=False)


def test_every_command_is_written_below_the_target_directory(tmp_path: Path) -> None:
    assert install_commands(tmp_path, SILENT, fetch=lambda url: f"body of {url}") is True

    for command in INSTALLED_COMMANDS:
        installed = tmp_path / command
        assert installed.read_text(encoding="utf-8") == f"body of {COMMANDS_RAW_BASE}{command}"


def test_a_download_failure_reports_failure(tmp_path: Path) -> None:
    def fail(url: str) -> str:
        raise URLError("no network")

    assert install_commands(tmp_path, SILENT, fetch=fail) is False


def test_a_symlinked_commands_directory_is_left_alone(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    link = tmp_path / "commands"
    try:
        link.symlink_to(checkout, target_is_directory=True)
    except OSError:
        pytest.skip("creating a symlink needs a privilege this machine does not grant")

    assert install_commands(link, SILENT, fetch=lambda url: "body") is True
    assert list(checkout.iterdir()) == []
