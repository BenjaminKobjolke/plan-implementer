# config/project_types.json

The table that maps a repository to a stack and to the checks a phase must leave green. It is
data, not code: adding a stack means adding an entry here, nothing else.

Read by `project_detect.load_config` and validated with pydantic (`extra="forbid"`, so a typo is
an error rather than a silently ignored key). Point `settings.json`'s `project_types_config` or
the `PLAN_IMPLEMENTER_PROJECT_TYPES` environment variable at a different file to override it.

## Shape

```json
{
  "schema_version": 1,
  "types": {
    "python": {
      "priority": 60,
      "markers": [{ "path": "pyproject.toml" }],
      "verify": [
        { "role": "test", "command": "uv run pytest" },
        { "role": "lint", "command": "uv run ruff check ." },
        { "role": "analyze", "command": "uv run mypy" }
      ]
    }
  }
}
```

| Field | Meaning |
|---|---|
| `schema_version` | Format version of this file. Currently `1`. |
| `types` | Stack name → definition. The name is what `--dry-run` and the prompt report. |
| `priority` | Lower wins. Checked in ascending order, first match ends the search. |
| `markers` | Any one match identifies the stack (OR, not AND). |
| `verify` | The stack's default checks, one per role. |
| `command_prefix` | Optional prefix applied to every `verify` command of this stack. |

### markers

Each marker is `path` **or** `glob`, relative to the repository root, optionally narrowed by
`contains`:

```json
{ "path": "pubspec.yaml", "contains": "flutter:" }
{ "glob": "*.csproj" }
```

- `path` — that exact file must exist.
- `glob` — any file matching the pattern in the repository root must exist.
- `contains` — the matched file must also contain this substring. This is how a Flutter
  `pubspec.yaml` is told apart from a pure Dart one.

Only the repository root is looked at; markers are not searched recursively.

### verify and roles

`role` is what makes an existing project's own tooling able to replace a default. It is a free
string, but only these three are wired to a batch file:

| Role | Replaced by, when it exists in the repo |
|---|---|
| `test` | `tools\run_tests.bat` |
| `integration` | `tools\run_integration_tests.bat` |
| `analyze` | `tools\analyze_code.bat` |

Resolution, in `project_detect._resolve_verify` — the single path every consumer (prompt, dry
run, run) shares:

1. Every batch file present in the target repo is listed **first**, in the order of the table
   above.
2. Then each stack default whose role is not already covered by one of those batch files.
3. `command_prefix` is applied to the stack defaults only, never to a repo's own batch file.

So a Python repo with `tools\run_tests.bat` gets `tools\run_tests.bat`, `uv run ruff check .` and
`uv run mypy` — its own runner, plus the two roles it has no runner for.

Roles other than those three simply always keep their default. Give the `lint` and `build` roles
whatever name you like; nothing looks them up.

### command_prefix

```json
"command_prefix": { "value": "fvm ", "when_any_exists": [".fvmrc", ".fvm"] }
```

Applied to the stack's `verify` commands when any of the listed paths exists in the repository
root. `flutter analyze` becomes `fvm flutter analyze` in an FVM-managed repo and stays
`flutter analyze` elsewhere.

## Configured stacks

| Priority | Type | Marker | Default checks |
|---|---|---|---|
| 10 | `unity` | `ProjectSettings/ProjectVersion.txt` | none |
| 20 | `flutter` | `pubspec.yaml` containing `flutter:` | `flutter analyze`, `flutter test` (`fvm `-prefixed when `.fvmrc`/`.fvm` exists) |
| 30 | `svelte` | `svelte.config.js` | `npm run check`, `npm run lint`, `npm test` |
| 40 | `node` | `package.json` | `npm test`, `npm run lint` |
| 50 | `php` | `composer.json` | `composer test`, `vendor/bin/phpstan analyse` |
| 60 | `python` | `pyproject.toml` | `uv run pytest`, `uv run ruff check .`, `uv run mypy` |
| 70 | `csharp` | `*.sln`, `*.csproj` | `dotnet build`, `dotnet test` |
| 80 | `arduino` | `platformio.ini` | `pio run` |

Priorities are spaced by ten so a new stack fits between two existing ones without renumbering.
The order matters where markers overlap: a SvelteKit repo also has `package.json`, so `svelte`
sits above `node`; Unity sits at the top because a Unity project can carry almost anything else.

`unity` deliberately has no checks — there is no reliable command-line verification — so a Unity
repo without `tools/*.bat` falls back to the same prompt an undetected stack gets.

## No match

An unrecognized repository becomes the type `unknown`, whose checks are whatever `tools/*.bat` it
happens to have. With no batch files either, the prompt tells Claude to read `CLAUDE.md` and pick
the checks itself. This is the expected state for an empty repository whose first phase has not
run yet.

## Adding a stack

1. Add an entry under `types` with a free priority slot.
2. Give it markers that cannot match a neighbouring stack — use `contains` when a file name alone
   is ambiguous.
3. Tag each command with a role; use `test` / `integration` / `analyze` where the check really is
   that role, so an existing `tools/*.bat` can take over.
4. Add the type and one marker file to `MARKER_FILES` in
   `tests/unit/test_project_detect.py`. The suite asserts that the table covers every configured
   type, so a new stack without a test case fails the build.
