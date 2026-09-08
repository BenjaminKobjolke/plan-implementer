"""Fixtures for unit tests."""

import pytest

from plan_implementer.app_logger import AppLogger


@pytest.fixture
def caplog_free_logger() -> AppLogger:
    """A silenced logger so tests do not print Claude stream output."""
    return AppLogger(enabled=False)
