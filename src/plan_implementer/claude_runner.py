"""Run headless Claude Code processes and render their stream-json live."""

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import IO, Protocol

from plan_implementer.app_logger import AppLogger
from plan_implementer.claude_stream import ClaudeStream
from plan_implementer.constants import (
    CLAUDE_EXECUTABLE_NAME,
    DEFAULT_SESSION_LABEL,
    ENV_CLAUDE_EXECUTABLE,
    SHUTDOWN_GRACE_SECONDS,
)
from plan_implementer.errors import ConfigurationError
from plan_implementer.models import (
    DEFAULT_CLAUDE_LIMITS,
    ClaudeLimits,
    ClaudeResult,
    SessionRecord,
)


class ClaudeRun(Protocol):
    """The single entry point every caller uses to talk to Claude Code."""

    def run(self, prompt: str, cwd: Path, label: str = "") -> ClaudeResult:
        """Run one fresh Claude Code process to completion; `label` names it in the report."""
        ...


class ClaudeRunner:
    """Start one fresh Claude Code process per call — no session is ever reused."""

    def __init__(
        self,
        logger: AppLogger,
        permission_mode: str,
        limits: ClaudeLimits = DEFAULT_CLAUDE_LIMITS,
        executable: str | None = None,
    ) -> None:
        self._logger = logger
        self._permission_mode = permission_mode
        self._limits = limits
        self._executable = executable or find_claude()
        self.sessions: list[SessionRecord] = []

    def run(self, prompt: str, cwd: Path, label: str = "") -> ClaudeResult:
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
        stream = ClaudeStream(self._logger, self._limits)

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
            stalled = self._pump(process, stream)
            if stalled:
                return self._record(label, ClaudeResult(success=False, result_message=stalled))
            return_code = process.wait()
        except KeyboardInterrupt:
            # Not recorded: `cli.main` returns on the interrupt before any report is written.
            self._logger.warning("\n\nInterrupted. Stopping Claude...")
            self._shutdown(process)
            raise
        finally:
            # The pipe belongs to the reader thread, which closes it at EOF. Closing it here
            # would deadlock against a reader still blocked inside `readline`.
            stream.flush()

        if return_code != 0:
            return self._record(
                label,
                ClaudeResult(
                    success=False,
                    result_message=(
                        stream.result.result_message or f"claude exited with {return_code}"
                    ),
                    duration_ms=stream.result.duration_ms,
                    cost_usd=stream.result.cost_usd,
                    usage=stream.result.usage,
                ),
            )
        return self._record(label, stream.result)

    def _pump(self, process: subprocess.Popen[str], stream: ClaudeStream) -> str | None:
        """Feed the child's output to `stream`; return why it was stopped, or `None` at EOF.

        A blocking `for line in process.stdout` can never time out, so a reader thread owns the
        pipe and this loop waits on a queue instead.
        """
        lines: queue.Queue[str | None] = queue.Queue()
        reader = threading.Thread(
            target=_pump_lines, args=(process.stdout, lines), daemon=True, name="claude-stdout"
        )
        reader.start()

        while True:
            try:
                line = lines.get(timeout=self._limits.idle_timeout)
            except queue.Empty:
                minutes = self._limits.idle_timeout_seconds / 60
                reason = f"no output from claude for {minutes:.0f} minutes - stopped"
                self._logger.error(f"\n\n{reason}")
                self._shutdown(process)
                return reason

            if line is None:
                return None

            self._consume(stream, line.strip())
            if stream.stalled:
                reason = (
                    f"claude repeated the same output more than "
                    f"{self._limits.max_repeated_lines} times - stopped"
                )
                self._logger.error(f"\n\n{reason}")
                self._shutdown(process)
                return reason

    def _shutdown(self, process: subprocess.Popen[str]) -> None:
        """End the child politely, then bluntly — a terminate alone can leave it running.

        On Windows `claude` resolves to a `.CMD` shim, so the process started here is the shim
        and the real Claude is its child. Terminating the shim would orphan that child, leave it
        holding the output pipe, and leave the run it was told to stop still running.
        """
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                capture_output=True,
                check=False,
            )
        else:
            process.terminate()

        try:
            process.wait(timeout=SHUTDOWN_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()

    def _record(self, label: str, result: ClaudeResult) -> ClaudeResult:
        """Remember this session for the run report, and hand the result back to the caller."""
        self.sessions.append(SessionRecord(label=label or DEFAULT_SESSION_LABEL, result=result))
        return result

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


def _pump_lines(stdout: IO[str] | None, lines: queue.Queue[str | None]) -> None:
    """Read the child's stdout to EOF, then post the sentinel that ends the consumer loop."""
    try:
        for line in stdout or ():
            lines.put(line)
    finally:
        if stdout is not None:
            stdout.close()
        lines.put(None)


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
