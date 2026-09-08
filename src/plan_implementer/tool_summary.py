"""Turn Claude tool-call arguments into one readable console line."""

import json

from plan_implementer.constants import MAX_DISPLAY_LENGTH

# The argument worth showing, per tool. Anything else falls back to compact JSON.
_INTERESTING_FIELDS: dict[str, tuple[str, ...]] = {
    "Read": ("file_path", "path"),
    "Edit": ("file_path", "path"),
    "Write": ("file_path", "path"),
    "Bash": ("command",),
    "PowerShell": ("command",),
    "Glob": ("pattern",),
    "Task": ("description", "prompt", "name"),
    "Agent": ("description", "prompt", "name"),
    "WebSearch": ("query",),
    "Skill": ("skill",),
}


def truncate(text: object, length: int = MAX_DISPLAY_LENGTH) -> str:
    """Collapse whitespace and cut overlong values down to one console line."""
    flattened = " ".join(str(text).replace("\r", " ").replace("\n", " ").split())
    if len(flattened) <= length:
        return flattened
    return flattened[: length - 3] + "..."


def summarize_tool(name: str, data: object) -> str:
    """Summarize one tool call for the console."""
    if not isinstance(data, dict):
        return truncate(data)

    if name == "Grep":
        pattern = data.get("pattern", "")
        path = data.get("path", ".")
        return truncate(f'"{pattern}" in {path}')

    for field in _INTERESTING_FIELDS.get(name, ()):
        value = data.get(field)
        if value:
            return truncate(value)

    if not data:
        return ""

    try:
        return truncate(json.dumps(data, ensure_ascii=False))
    except TypeError, ValueError:
        return truncate(data)
