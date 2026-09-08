"""Install the Claude Code slash commands this tool expects, from the claude-code repo."""

import os
from collections.abc import Callable
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from plan_implementer.app_logger import AppLogger
from plan_implementer.constants import (
    CLAUDE_COMMANDS_DIR,
    COMMANDS_RAW_BASE,
    DOWNLOAD_TIMEOUT_SECONDS,
    ENV_COMMANDS_DIR,
    INSTALLED_COMMANDS,
)

Fetch = Callable[[str], str]
"""Download one command file: its URL in, its text out."""


def download(url: str) -> str:
    """Read a text file over HTTP."""
    with urlopen(url, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
        raw: bytes = response.read()
    return raw.decode("utf-8")


def install_commands(target_dir: Path, logger: AppLogger, fetch: Fetch = download) -> bool:
    """Install every configured command below `target_dir`; True when all of them landed."""
    if target_dir.is_symlink():
        logger.warning(
            f"{target_dir} is a symlink into a checkout - "
            "update it with `git pull` there instead. Nothing installed."
        )
        return True

    for command in INSTALLED_COMMANDS:
        url = f"{COMMANDS_RAW_BASE}{command}"
        destination = target_dir / command
        try:
            text = fetch(url)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(text, encoding="utf-8")
        except (URLError, OSError) as error:
            logger.error(f"Failed to install {command} from {url}: {error}")
            return False
        logger.info(f"Installed {destination}")

    return True


def main() -> int:
    """Entry point for `install-skills.bat`."""
    logger = AppLogger()
    target_dir = Path(os.getenv(ENV_COMMANDS_DIR, str(CLAUDE_COMMANDS_DIR)))
    logger.info(f"Installing slash commands into {target_dir}")
    return 0 if install_commands(target_dir, logger) else 1


if __name__ == "__main__":
    raise SystemExit(main())
