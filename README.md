# plan-implementer

Implements a multi-step plan folder's phases sequentially with headless Claude Code.

The [`/plan:multi-step`](#slash-commands) slash command writes a plan as ordered phase files:

```
<repo>/plan/YYYYMMDD_<feature-name>/
  00-context.md      shared reference — never implemented, always read first
  01-<kebab>.md      phase 1, ending in a "## Verify" section
  02-<kebab>.md      …
<repo>/plan/done/YYYYMMDD_<feature-name>/
                     finished phase files land here
```

`plan-implementer` points a fresh Claude Code session at one phase at a time, in order. After a
phase succeeds its file moves to `plan/done/<folder-name>/` and the repository is committed; once
the last phase is done, `00-context.md` follows it there and the emptied plan folder is removed.
(A plan folder holding anything else — tooling output, subfolders — is left in place instead.)

It works with any stack: the target repository's project type is detected from marker files, and
the matching checks are named in the prompt. Existing `tools/*.bat` in the target repo always win
over the stack defaults.

## Requirements

- Windows
- [uv](https://docs.astral.sh/uv/) (Python 3.14 is installed by `install.bat`)
- Claude Code on `PATH` (`claude`)

## Installation

```
install.bat
```

Then copy the settings template and edit it:

```
copy settings.example.json settings.json
```

## Slash commands

The plan folders this tool implements are written by Claude Code slash commands that live in a
separate repository, [BenjaminKobjolke/claude-code](https://github.com/BenjaminKobjolke/claude-code),
not in this one. `install-skills.bat` downloads the current version of the ones this tool relies on
into `%USERPROFILE%\.claude\commands\`, where they are available in every repository:

| Command | Role |
|---|---|
| `/plan:multi-step` | writes the `plan/<feature>/` folder this tool implements |
| `/plan:implement-phase` | the manual per-phase workflow this tool automates |
| `/git:commit` | the default `commit` spec in `settings.example.json` |

```
install-skills.bat
```

`/git:commit` also needs the global permissions its own `/git:setup` command grants. If
`%USERPROFILE%\.claude\commands` is a symlink into a checkout of that repository, the installer
leaves it alone — `git pull` there instead. Set `PLAN_IMPLEMENTER_COMMANDS_DIR` to install
somewhere else.

None of this is mandatory: any plan folder matching the layout above works, and `commit` accepts a
plain shell command instead of a slash command.

## Usage

```
start.bat D:\GIT\BenjaminKobjolke\tickets-watcher\plan\tickets-watcher
```

| Flag | Meaning |
|---|---|
| `--dry-run` | Show the resolved repository, project type, checks and phases, then exit |
| `--phase NN` | Implement only that phase (e.g. `--phase 03`) instead of every remaining one |
| `--project PATH` | Repository root, when it cannot be derived from the plan folder path |
| `--commit SPEC` | Commit spec for this run (see below), overriding `settings.json` |
| `--no-commit` | Do not commit after a phase |
| `--continue-on-failure` | Keep going after a failed phase instead of stopping |

The repository root is `<repo>/plan/<feature>` by convention; otherwise the nearest `.git`
ancestor is used, and failing that `--project` is required.

Exit codes: `0` all phases done, `1` at least one phase failed, `2` bad configuration or input.

## Settings

`settings.json` (gitignored; `settings.example.json` is the committed template):

```json
{
  "commit": "/git:commit",
  "permission_mode": "bypassPermissions"
}
```

| Key | Meaning |
|---|---|
| `commit` | Empty = never commit. Starting with `/` = run it as a Claude prompt in the target repo. Anything else = run it as a shell command in the target repo. |
| `permission_mode` | Passed to `claude --permission-mode`. Default `bypassPermissions`. |
| `project_types_config` | Path to an alternative project-type table. Default `config/project_types.json`. |

A custom commit command, for example:

```json
{
  "commit": "codex --yolo \"git commit and push using those guidelines D:\\GIT\\BenjaminKobjolke\\claude-code\\commands\\git\\commit-fast.md\""
}
```

Every setting has an environment override: `PLAN_IMPLEMENTER_SETTINGS`,
`PLAN_IMPLEMENTER_COMMIT`, `PLAN_IMPLEMENTER_PERMISSION_MODE`, `PLAN_IMPLEMENTER_PROJECT_TYPES`
and `PLAN_IMPLEMENTER_CLAUDE` (full path to the `claude` executable).

## Project types

`config/project_types.json` maps marker files to a stack and its checks — unity, flutter (with
`fvm` prefix when `.fvmrc`/`.fvm` exists), svelte, node, php, python, csharp, arduino. Add a stack
by adding an entry; no code changes are needed.

Roles let existing project tooling take precedence: `tools\run_tests.bat` (test),
`tools\run_integration_tests.bat` (integration) and `tools\analyze_code.bat` (analyze) replace the
stack default for the same role. An undetectable stack with no bats tells Claude to read
`CLAUDE.md` and pick the checks itself.

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — the plan folder contract, the run flow, the
  module map and the prompt.
- [`docs/PROJECT_TYPES_JSON.md`](docs/PROJECT_TYPES_JSON.md) — the `config/project_types.json`
  format and how to add a stack.

## Development

```
tools\run_tests.bat               unit tests
tools\run_integration_tests.bat   integration tests
tools\analyze_code.bat            ruff check, ruff format --check, mypy
update.bat                        upgrade dependencies and re-verify
```

## Dependencies

`pydantic` at runtime; `pytest`, `ruff` and `mypy` for development.
