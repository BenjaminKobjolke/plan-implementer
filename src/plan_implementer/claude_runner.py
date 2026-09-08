"""Run headless Claude Code processes and render their stream-json live."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Protocol

from plan_implementer.app_logger import AppLogger
from plan_implementer.constants import CLAUDE_EXECUTABLE_NAME, ENV_CLAUDE_EXECUTABLE
from plan_implementer.errors import ConfigurationError
from plan_implementer.models import ClaudeResult
from plan_implementer.tool_summary import summarize_tool


class ClaudeRun(Protocol):
    """The single entry point every caller uses to talk to Claude Code."""

    def run(self, prompt: str, cwd: Path) -> ClaudeResult:
        """Run one fresh Claude Code process to completion."""
        ...


class ClaudeStream:
    """Parse a `stream-json` event stream into console output and a result."""

    def __init__(self, logger: AppLogger) -> None:
        self._logger = logger
        self._tool_name: str | None = None
        self._tool_json = ""
        self._tool_input: dict[str, object] = {}
        self._in_text = False
        self.tool_names: dict[str, str] = {}
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
            )

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
            self._logger.info(f"  {marker} {name}")

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
        self._logger.info(f"  -> {self._tool_name}{suffix}")

        self._tool_name = None
        self._tool_json = ""
        self._tool_input = {}


class ClaudeRunner:
    """Start one fresh Claude Code process per call — no session is ever reused."""

    def __init__(
        self,
        logger: AppLogger,
        permission_mode: str,
        executable: str | None = None,
    ) -> None:
        self._logger = logger
        self._permission_mode = permission_mode
        self._executable = executable or find_claude()

    def run(self, prompt: str, cwd: Path) -> ClaudeResult:
        """Run `prompt` in `cwd` and stream its progress to the console."""
        command = [
            self._executable,
            "-p",
            prompt,
            "--permission-mode",
            self._permission_mode,
            "--no-session-persistence",
            "--output-format",
            "stream-json",
            "--verbose",
            "--include-partial-messages",
        ]
        stream = ClaudeStream(self._logger)

        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        try:
            for line in process.stdout or ():
                self._consume(stream, line.strip())
            return_code = process.wait()
        except KeyboardInterrupt:
            self._logger.warning("\n\nInterrupted. Stopping Claude...")
            process.terminate()
            raise
        finally:
            if process.stdout is not None:
                process.stdout.close()

        if return_code != 0:
            return ClaudeResult(
                success=False,
                result_message=stream.result.result_message or f"claude exited with {return_code}",
                duration_ms=stream.result.duration_ms,
                cost_usd=stream.result.cost_usd,
            )
        return stream.result

    def _consume(self, stream: ClaudeStream, line: str) -> None:
        if not line:
            return
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            # Startup banners and error text are not JSON but still worth seeing.
            self._logger.info(f"[Claude] {line}")
            return
        if isinstance(event, dict):
            stream.handle(event)


def find_claude() -> str:
    """Locate the Claude Code CLI, honoring an explicit override."""
    override = os.getenv(ENV_CLAUDE_EXECUTABLE)
    if override:
        return override

    executable = shutil.which(CLAUDE_EXECUTABLE_NAME)
    if not executable:
        raise ConfigurationError(
            "Could not find 'claude' in PATH. Install Claude Code or set "
            f"{ENV_CLAUDE_EXECUTABLE} to its full path."
        )
    return executable


def _as_optional_str(value: object) -> str | None:
    return None if value is None else str(value)


def _as_optional_int(value: object) -> int | None:
    return int(value) if isinstance(value, int | float) else None


def _as_optional_float(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) else None
