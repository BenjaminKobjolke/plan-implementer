"""Central string, path, and pattern constants."""

import re
from pathlib import Path
from typing import Final

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
DEFAULT_PROJECT_TYPES_CONFIG: Final[Path] = PROJECT_ROOT / "config" / "project_types.json"
DEFAULT_SETTINGS_FILE: Final[Path] = PROJECT_ROOT / "settings.json"

ENV_SETTINGS: Final[str] = "PLAN_IMPLEMENTER_SETTINGS"
ENV_COMMANDS_DIR: Final[str] = "PLAN_IMPLEMENTER_COMMANDS_DIR"
ENV_PROJECT_TYPES: Final[str] = "PLAN_IMPLEMENTER_PROJECT_TYPES"
ENV_COMMIT: Final[str] = "PLAN_IMPLEMENTER_COMMIT"
ENV_PERMISSION_MODE: Final[str] = "PLAN_IMPLEMENTER_PERMISSION_MODE"
ENV_CLAUDE_EXECUTABLE: Final[str] = "PLAN_IMPLEMENTER_CLAUDE"

# The slash commands this tool assumes exist in the target repository. They are maintained in
# a separate repository, so `install-skills.bat` downloads them instead of vendoring copies.
COMMANDS_RAW_BASE: Final[str] = (
    "https://raw.githubusercontent.com/BenjaminKobjolke/claude-code/main/commands/"
)
INSTALLED_COMMANDS: Final[tuple[str, ...]] = (
    "plan/multi-step.md",
    "plan/implement-phase.md",
    "git/commit.md",
)
CLAUDE_COMMANDS_DIR: Final[Path] = Path.home() / ".claude" / "commands"
DOWNLOAD_TIMEOUT_SECONDS: Final[int] = 30

CONTEXT_FILE_NAME: Final[str] = "00-context.md"
ORIGINAL_FILE_NAME: Final[str] = "original.md"
REPORT_FILE_NAME: Final[str] = "REPORT.md"
ERROR_FILE_NAME: Final[str] = "ERROR.md"
DONE_DIR_NAME: Final[str] = "done"
PLAN_DIR_NAME: Final[str] = "plan"
GIT_DIR_NAME: Final[str] = ".git"
PHASE_FILE_PATTERN: Final[re.Pattern[str]] = re.compile(r"^(?P<number>\d{2})-.+\.md$")

# Files the coding-rules AI workflow writes next to a plan file. They match the phase
# pattern but are output, not work to implement.
WORKFLOW_ARTIFACT_SUFFIXES: Final[tuple[str, ...]] = (
    "-changed-files",
    "-post-implementation-check",
)

DEFAULT_PERMISSION_MODE: Final[str] = "bypassPermissions"
CLAUDE_EXECUTABLE_NAME: Final[str] = "claude"
CLAUDE_PROMPT_PREFIX: Final[str] = "/"

# How a Claude session is named in the run report.
COMMIT_SESSION_LABEL: Final[str] = "commit"
DEFAULT_SESSION_LABEL: Final[str] = "session"
UNKNOWN_PROJECT_TYPE: Final[str] = "unknown"

# Existing project tooling wins over a stack's default command for the same role.
TOOL_BAT_ROLES: Final[dict[str, str]] = {
    "tools/run_tests.bat": "test",
    "tools/run_integration_tests.bat": "integration",
    "tools/analyze_code.bat": "analyze",
}

MAX_DISPLAY_LENGTH: Final[int] = 180
