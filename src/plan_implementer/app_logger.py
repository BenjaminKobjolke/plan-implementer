"""Centralized application logging — the only module writing to the console."""

import logging
import sys
from typing import TextIO


class AppLogger:
    """Route all console output through one configurable boundary."""

    def __init__(self, *, enabled: bool = True, level: int = logging.INFO) -> None:
        self._enabled = enabled
        self._stream: TextIO = sys.stdout
        self._logger = logging.getLogger("plan_implementer")
        self._logger.handlers.clear()
        self._logger.propagate = False
        self._logger.disabled = not enabled
        self._logger.setLevel(level)

        handler = logging.StreamHandler(self._stream)
        handler.setFormatter(logging.Formatter("%(message)s"))
        self._logger.addHandler(handler)

    def debug(self, message: str) -> None:
        """Write a diagnostic application message."""
        self._logger.debug(message)

    def info(self, message: str) -> None:
        """Write an informational application message."""
        self._logger.info(message)

    def warning(self, message: str) -> None:
        """Write a warning application message."""
        self._logger.warning(message)

    def error(self, message: str) -> None:
        """Write an error application message."""
        self._logger.error(message)

    def stream(self, text: str) -> None:
        """Write model output verbatim, without a trailing newline."""
        if not self._enabled:
            return
        self._stream.write(text)
        self._stream.flush()
