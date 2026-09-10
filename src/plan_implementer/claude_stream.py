"""Parse a headless Claude Code `stream-json` event stream into console output."""

import json
from collections import deque

from plan_implementer.app_logger import AppLogger
from plan_implementer.constants import REPEAT_WINDOW_LINES
from plan_implementer.models import (
    DEFAULT_CLAUDE_LIMITS,
    ClaudeLimits,
    ClaudeResult,
    TokenUsage,
)
from plan_implementer.tool_summary import summarize_tool


class ClaudeStream:
    """Parse a `stream-json` event stream into console output and a result."""

    def __init__(self, logger: AppLogger, limits: ClaudeLimits = DEFAULT_CLAUDE_LIMITS) -> None:
        self._logger = logger
        self._limits = limits
        self._tool_name: str | None = None
        self._tool_json = ""
        self._tool_input: dict[str, object] = {}
        self._in_text = False
        # A poll loop alternates between a handful of lines, so only a window catches it -
        # two consecutive lines are never equal.
        self._recent: deque[str] = deque(maxlen=REPEAT_WINDOW_LINES)
        self._hidden = 0
        self.tool_names: dict[str, str] = {}
        self.stalled = False
        self.result = ClaudeResult(success=False)

    def handle(self, event: dict[str, object]) -> None:
        """Dispatch one top-level stream event."""
        kind = event.get("type")

        if kind == "stream_event":
            inner = event.get("event")
            if isinstance(inner, dict):
                self._handle_stream_event(inner)
        elif kind == "user":
            self._handle_tool_results(event)
        elif kind == "result":
            self.result = ClaudeResult(
                success=not bool(event.get("is_error", False)),
                result_message=_as_optional_str(event.get("result")),
                duration_ms=_as_optional_int(event.get("duration_ms")),
                cost_usd=_as_optional_float(event.get("total_cost_usd")),
                usage=_as_usage(event.get("usage")),
            )

    def flush(self) -> None:
        """Report any lines still held back, so a run never ends mid-suppression."""
        self._flush_hidden()

    def _emit(self, line: str) -> None:
        """Print one tool line, unless the same line is already in the recent window."""
        if line in self._recent:
            self._hidden += 1
            if self._limits.repeats_exhausted(self._hidden):
                self.stalled = True
            return

        self._flush_hidden()
        self._logger.info(line)
        self._recent.append(line)

    def _flush_hidden(self) -> None:
        if not self._hidden:
            return
        self._logger.info(f"  ... {self._hidden} repeated lines hidden")
        self._hidden = 0

    def _handle_tool_results(self, event: dict[str, object]) -> None:
        message = event.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            return

        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            name = self.tool_names.get(str(block.get("tool_use_id")), "Tool")
            marker = "[FAILED]" if block.get("is_error", False) else "[done]  "
            self._emit(f"  {marker} {name}")

    def _handle_stream_event(self, event: dict[str, object]) -> None:
        kind = event.get("type")

        if kind == "content_block_start":
            self._start_block(event.get("content_block"))
        elif kind == "content_block_delta":
            self._append_delta(event.get("delta"))
        elif kind == "content_block_stop":
            self._stop_block()

    def _start_block(self, block: object) -> None:
        if not isinstance(block, dict):
            return

        if block.get("type") == "text":
            self._in_text = True
            # Model text is never suppressed, but a pending count must not straddle it.
            self._flush_hidden()
            self._logger.stream("\nClaude: ")
            return

        if block.get("type") == "tool_use":
            self._tool_name = str(block.get("name", "Tool"))
            self._tool_json = ""
            raw_input = block.get("input")
            self._tool_input = raw_input if isinstance(raw_input, dict) else {}
            tool_id = block.get("id")
            if tool_id:
                self.tool_names[str(tool_id)] = self._tool_name

    def _append_delta(self, delta: object) -> None:
        if not isinstance(delta, dict):
            return

        if delta.get("type") == "text_delta":
            self._logger.stream(str(delta.get("text", "")))
        elif delta.get("type") == "input_json_delta":
            self._tool_json += str(delta.get("partial_json", ""))

    def _stop_block(self) -> None:
        if self._in_text:
            self._logger.stream("\n")
            self._in_text = False
            return

        if not self._tool_name:
            return

        arguments: object = self._tool_input
        if self._tool_json:
            try:
                arguments = json.loads(self._tool_json)
            except json.JSONDecodeError:
                arguments = {"arguments": self._tool_json}

        summary = summarize_tool(self._tool_name, arguments)
        suffix = f": {summary}" if summary else ""
        self._emit(f"  -> {self._tool_name}{suffix}")

        self._tool_name = None
        self._tool_json = ""
        self._tool_input = {}


def _as_optional_str(value: object) -> str | None:
    return None if value is None else str(value)


def _as_optional_int(value: object) -> int | None:
    return int(value) if isinstance(value, int | float) else None


def _as_optional_float(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) else None


def _as_usage(value: object) -> TokenUsage:
    if not isinstance(value, dict):
        return TokenUsage()
    return TokenUsage(
        input_tokens=_as_int(value.get("input_tokens")),
        output_tokens=_as_int(value.get("output_tokens")),
        cache_read_tokens=_as_int(value.get("cache_read_input_tokens")),
        cache_creation_tokens=_as_int(value.get("cache_creation_input_tokens")),
    )


def _as_int(value: object) -> int:
    return int(value) if isinstance(value, int | float) else 0
