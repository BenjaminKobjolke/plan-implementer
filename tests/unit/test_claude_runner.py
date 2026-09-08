"""Unit tests for the Claude stream-json parser."""

import json

from plan_implementer.app_logger import AppLogger
from plan_implementer.claude_runner import ClaudeStream
from plan_implementer.models import TokenUsage
from plan_implementer.tool_summary import summarize_tool


def feed(stream: ClaudeStream, events: list[dict[str, object]]) -> None:
    for event in events:
        stream.handle(json.loads(json.dumps(event)))


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
