# Version
1

# Coding Rules (Pointer)

This project's coding rules live in `CODING_RULES.md` in the project root. They are
BINDING for all code work in this repository.

MANDATORY: Before writing or editing ANY code, you MUST Read `CODING_RULES.md`
in full **in the current session**. Do not rely on memory of a previous session,
a summary, or partial reads.

If you are about to make a code change and have not read `CODING_RULES.md` in
this session: STOP, read it, then continue.

Do not inline rules back into this file and do not use `@import` for
`CODING_RULES.md` — it is intentionally referenced, not imported.

# plan-implementer

A Windows CLI that implements a `plan/<feature>/` multi-step plan folder's `NN-*.md` phases
sequentially, one fresh headless Claude Code process per phase. See `README.md` for usage.

## Build & test

| Command | Purpose |
|---|---|
| `install.bat` | `uv sync --all-extras`, then the test suite |
| `install-skills.bat` | Download the external slash commands into `~/.claude/commands` |
| `start.bat <plan-folder> [flags]` | Run the CLI (`uv run plan-implementer`) |
| `tools\run_tests.bat` | Unit tests (`tests/unit`) |
| `tools\run_integration_tests.bat` | Integration tests (`tests/integration`) |
| `tools\analyze_code.bat` | `ruff check`, `ruff format --check`, `mypy` |
| `update.bat` | Upgrade dependencies, then lint and test |

## Layout

`src/plan_implementer/` — flat modules, one responsibility each: `plan_folder` (resolve the
folder, order phases, `done/` moves, archive), `project_detect` (marker files →
`config/project_types.json` → verify commands), `prompt_builder`, `claude_runner` (+
`tool_summary`) for the `stream-json` layer, `committer`, `runner`, `cli`, `skill_installer`. All
console output goes through `app_logger.AppLogger`.

## Documentation

`docs/ARCHITECTURE.md` (plan folder contract, run flow, module map, prompt) and
`docs/PROJECT_TYPES_JSON.md` (the stack table format). Keep both in step with the code.

## Related projects

- `D:\GIT\BenjaminKobjolke\project-health-check` — the Python/uv convention source (layout,
  `pyproject.toml`, `AppLogger`, `Settings`, batch files).
- `D:\GIT\BenjaminKobjolke\android\tickets-app\implement.py` — the original Flutter-only
  predecessor this tool generalizes; the `stream-json` parser is ported from it.
- `D:\GIT\BenjaminKobjolke\claude-code\commands\plan\` — `multi-step.md` and
  `implement-phase.md` define the plan folder layout and the per-phase workflow this tool
  automates. Keep them in step when either changes.

