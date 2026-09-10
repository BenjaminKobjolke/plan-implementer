"""Unit tests for the Claude stream-json parser."""

import json

import pytest

from plan_implementer.app_logger import AppLogger
from plan_implementer.claude_stream import ClaudeStream
from plan_implementer.constants import REPEAT_WINDOW_LINES
from plan_implementer.models import ClaudeLimits, TokenUsage
from plan_implementer.tool_summary import summarize_tool


def feed(stream: ClaudeStream, events: list[dict[str, object]]) -> None:
    for event in events:
        stream.handle(json.loads(json.dumps(event)))


def read_call(tool_id: str, path: str) -> list[dict[str, object]]:
    """The three events one `Read` tool call produces, plus its result."""
    return [
        {
            "type": "stream_event",
            "event": {
                "type": "content_block_start",
                "content_block": {"type": "tool_use", "name": "Read", "id": tool_id},
            },
        },
        {
            "type": "stream_event",
            "event": {
                "type": "content_block_delta",
                "delta": {"type": "input_json_delta", "partial_json": f'{{"file_path": "{path}"}}'},
            },
        },
        {"type": "stream_event", "event": {"type": "content_block_stop"}},
        {
            "type": "user",
            "message": {"content": [{"type": "tool_result", "tool_use_id": tool_id}]},
        },
    ]


def poll_loop(rounds: int) -> list[dict[str, object]]:
    """What a headless Claude polling two never-filled task output files emits."""
    events: list[dict[str, object]] = []
    for index in range(rounds):
        events += read_call(f"a{index}", "tasks/first.output")
        events += read_call(f"b{index}", "tasks/second.output")
    return events


def test_result_event_is_captured(caplog_free_logger: AppLogger) -> None:
    stream = ClaudeStream(caplog_free_logger)

    feed(
        stream,
        [{"type": "result", "is_error": False, "result": "done", "total_cost_usd": 1.5}],
    )

    assert stream.result.success is True
    assert stream.result.result_message == "done"
    assert stream.result.cost_usd == 1.5


def test_result_event_token_usage_is_captured(caplog_free_logger: AppLogger) -> None:
    stream = ClaudeStream(caplog_free_logger)

    feed(
        stream,
        [
            {
                "type": "result",
                "is_error": False,
                "usage": {
                    "input_tokens": 1120,
                    "output_tokens": 210,
                    "cache_read_input_tokens": 40010,
                    "cache_creation_input_tokens": 900,
                },
            }
        ],
    )

    assert stream.result.usage == TokenUsage(
        input_tokens=1120,
        output_tokens=210,
        cache_read_tokens=40010,
        cache_creation_tokens=900,
    )
    assert stream.result.usage.total == 42240


def test_missing_or_unusable_usage_counts_as_zero(caplog_free_logger: AppLogger) -> None:
    stream = ClaudeStream(caplog_free_logger)

    feed(stream, [{"type": "result", "is_error": False, "usage": "not a mapping"}])

    assert stream.result.usage == TokenUsage()


def test_error_result_marks_failure(caplog_free_logger: AppLogger) -> None:
    stream = ClaudeStream(caplog_free_logger)

    feed(stream, [{"type": "result", "is_error": True, "result": "boom"}])

    assert stream.result.success is False
    assert stream.result.result_message == "boom"


def test_tool_use_arguments_are_assembled_from_deltas(caplog_free_logger: AppLogger) -> None:
    stream = ClaudeStream(caplog_free_logger)

    feed(
        stream,
        [
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_start",
                    "content_block": {"type": "tool_use", "name": "Bash", "id": "t1"},
                },
            },
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_delta",
                    "delta": {"type": "input_json_delta", "partial_json": '{"command": "ls"}'},
                },
            },
            {"type": "stream_event", "event": {"type": "content_block_stop"}},
        ],
    )

    assert stream.tool_names["t1"] == "Bash"


def test_summarize_tool_uses_the_interesting_field() -> None:
    assert summarize_tool("Bash", {"command": "pytest -q"}) == "pytest -q"
    assert summarize_tool("Read", {"file_path": "src/app.py"}) == "src/app.py"
    assert summarize_tool("Grep", {"pattern": "todo", "path": "src"}) == '"todo" in src'


def test_missing_result_event_is_a_failure(caplog_free_logger: AppLogger) -> None:
    stream = ClaudeStream(caplog_free_logger)

    assert stream.result.success is False


def test_a_poll_loop_prints_each_line_once_and_counts_the_rest(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A real logger, because the shared fixture is silenced and would capture nothing.
    stream = ClaudeStream(AppLogger())

    feed(stream, poll_loop(rounds=25))
    # The tail of a suppression run is only reported once something else needs printing.
    stream.flush()

    printed = capsys.readouterr().out.splitlines()
    # 25 rounds x 2 files x (call + result) = 100 lines, only 3 of them distinct.
    assert printed == [
        "  -> Read: tasks/first.output",
        "  [done]   Read",
        "  -> Read: tasks/second.output",
        "  ... 97 repeated lines hidden",
    ]


def test_distinct_tool_lines_are_never_suppressed(capsys: pytest.CaptureFixture[str]) -> None:
    stream = ClaudeStream(AppLogger())

    for index in range(REPEAT_WINDOW_LINES * 2):
        feed(stream, read_call(f"t{index}", f"src/file_{index}.py"))

    printed = capsys.readouterr().out.splitlines()
    for index in range(REPEAT_WINDOW_LINES * 2):
        assert f"  -> Read: src/file_{index}.py" in printed


def test_a_long_enough_repeat_run_marks_the_stream_stalled(
    capsys: pytest.CaptureFixture[str],
) -> None:
    stream = ClaudeStream(AppLogger(), ClaudeLimits(max_repeated_lines=20))

    feed(stream, poll_loop(rounds=25))

    assert stream.stalled is True
    capsys.readouterr()


def test_a_zero_cap_never_marks_the_stream_stalled(capsys: pytest.CaptureFixture[str]) -> None:
    stream = ClaudeStream(AppLogger(), ClaudeLimits(max_repeated_lines=0))

    feed(stream, poll_loop(rounds=200))

    assert stream.stalled is False
    capsys.readouterr()


def test_flush_reports_lines_still_held_back(capsys: pytest.CaptureFixture[str]) -> None:
    stream = ClaudeStream(AppLogger())
    feed(stream, poll_loop(rounds=3))
    capsys.readouterr()

    stream.flush()

    assert "repeated lines hidden" in capsys.readouterr().out
