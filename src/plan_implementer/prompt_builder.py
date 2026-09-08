"""Build the prompt that implements one plan phase in a fresh Claude session."""

from pathlib import Path

from plan_implementer.models import Phase, PlanFolder, ProjectType, VerifyCommand
from plan_implementer.plan_folder import relative_to_repo

_VERIFY_HEADING = "## verify"

_TEMPLATE = """
Implement one phase of a multi-step plan.

Shared context: {context}
Phase file:     {phase}

Read {context} completely, then {phase} completely, before changing anything.
The recorded research is your starting point — do NOT redo it. Quickly confirm that the key
files and symbols it references still exist; re-research only a gap where something moved.

Then:

1. Follow the phase file's steps in order.
2. Follow all project conventions, CLAUDE.md and CODING_RULES.md.
3. Do not make unrelated changes.
4. Run the phase's own "## Verify" checks{checks_sentence}
5. Fix anything that fails and re-run until everything is green.
6. Review your own implementation before finishing.
7. Do not stop until the phase is fully implemented and its checks pass.

Detected project type: {project_type}

If this phase depends on an unresolved question in the "Open Questions" section of {context},
stop immediately and report which question blocks you — do not guess.

IMPORTANT:

Do NOT move, rename or delete the phase file {phase} — the calling script moves it once you
have successfully finished. Do NOT commit; the calling script handles committing.

When finished, briefly summarize:
- what you implemented
- which files you changed
- which checks you ran
- whether everything passed
""".strip()

_CHECKS_WITH_COMMANDS = """, then these project checks:

{commands}
"""

_CHECKS_WITHOUT_COMMANDS = """.
   The project stack could not be detected — read CLAUDE.md and pick the appropriate
   tests, analyzers and build commands yourself.
"""


def build_phase_prompt(folder: PlanFolder, phase: Phase, project_type: ProjectType) -> str:
    """Render the phase prompt with repo-relative paths and de-duplicated checks."""
    commands = _additional_commands(phase.path, project_type.verify)
    if commands:
        rendered = "\n".join(f"   - `{command}`" for command in commands)
        checks_sentence = _CHECKS_WITH_COMMANDS.format(commands=rendered).rstrip()
    else:
        checks_sentence = _CHECKS_WITHOUT_COMMANDS.rstrip()

    return _TEMPLATE.format(
        context=relative_to_repo(folder.context_path, folder.repo_root),
        phase=relative_to_repo(phase.path, folder.repo_root),
        project_type=project_type.name,
        checks_sentence=checks_sentence,
    )


def _additional_commands(phase_path: Path, verify: tuple[VerifyCommand, ...]) -> list[str]:
    """Drop commands the phase's own Verify section already asks for."""
    already_asked = _normalized_verify_section(phase_path)
    return [entry.command for entry in verify if _normalize(entry.command) not in already_asked]


def _normalized_verify_section(phase_path: Path) -> str:
    text = phase_path.read_text(encoding="utf-8", errors="replace")
    lowered = text.lower()
    start = lowered.find(_VERIFY_HEADING)
    return _normalize(text[start:] if start >= 0 else "")


def _normalize(text: str) -> str:
    return " ".join(text.replace("\\", "/").split()).lower()
