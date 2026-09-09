# Architecture

How `plan-implementer` turns a multi-step plan folder into a sequence of headless Claude Code
runs. For usage and flags see [`../README.md`](../README.md); for the stack table see
[`PROJECT_TYPES_JSON.md`](PROJECT_TYPES_JSON.md).

## What it automates

`/plan:multi-step` writes a feature plan as ordered phase files; `/plan:implement-phase`
implements them one at a time, interactively, inside the target repo. This tool is the
unattended version of that second command, and it works against any stack rather than one.

The two source commands live in `D:\GIT\BenjaminKobjolke\claude-code\commands\plan\` and define
the contract below. **When they change, this tool has to follow** — that already happened once
(see [Plan folder contract](#plan-folder-contract)).

## Plan folder contract

```
<repo>/plan/YYYYMMDD_<feature-name>/
  00-context.md      shared reference — never implemented, always read first
  01-<kebab>.md      phase 1, ending in a "## Verify" section
  02-<kebab>.md      …
  ERROR.md           written by a failed run, overwritten by the next one
<repo>/plan/implementing/YYYYMMDD_<feature-name>/
                     the folder a run currently holds; invisible to another run
<repo>/plan/errors/YYYYMMDD_<feature-name>/
                     where a failed run parks the folder, ERROR.md included
<repo>/plan/done/YYYYMMDD_<feature-name>/
                     finished phase files, then 00-context.md at the end
  REPORT.md          one "## Run N" section per run: times, sessions, tokens, cost
```

| Rule | Where |
|---|---|
| A folder is a plan folder when it holds `00-context.md` | `plan_folder.resolve` |
| A folder without one stands for every immediate subfolder that has one, in name order | `plan_folder.resolve_all` |
| Phases are `NN-*.md` directly in the folder, ordered by `NN` | `plan_folder.phases` |
| `00-context.md` is context, never a phase | `constants.CONTEXT_FILE_NAME` |
| Coding-rules workflow output (`*-changed-files.md`, `*-post-implementation-check.md`) is not a phase, despite matching `NN-*.md` | `constants.WORKFLOW_ARTIFACT_SUFFIXES` |
| A finished phase and its `<stem>-*` sidecars (reports, delegate logs) move to `<repo>/plan/done/<folder-name>/` | `plan_folder.done_root`, `mark_done` |
| An existing destination is never overwritten | `mark_done`, `archive` |
| When no phase remains, the leftovers follow and the emptied folder is removed | `plan_folder.archive` |
| A folder being implemented lives in `plan/implementing/<folder-name>/`, so `resolve_all` cannot hand it to a concurrent run | `plan_folder.claim`, `release` |
| A run ends by archiving the folder, parking it in `plan/errors/<folder-name>/` after a failed phase, or putting it back — including after Ctrl-C | `plan_folder.release` |
| `implementing/`, `errors/` and `done/` are states, not locations: the owning `plan/` dir is one level further up | `constants.STATE_DIR_NAMES`, `plan_folder.plan_parent` |
| Every run appends itself to `REPORT.md`; a failed run also writes `ERROR.md` | `run_report.write` |
| A successful run clears the `ERROR.md` an earlier failed run left behind | `run_report.write` |

`archive()` deletes the plan folder **only** when nothing is left in it. A folder still holding
subfolders or tooling output (delegate logs, for instance) is kept, so nothing that is not ours
gets removed.

### Repository root

Claude runs with its working directory set to the target repo, and every path in the prompt is
repo-relative, so the root has to be right:

1. `--project PATH`, when given, wins.
2. Otherwise `<repo>/plan/<feature>` by convention — the folder's grandparent.
3. Otherwise the nearest ancestor holding `.git`.
4. Otherwise a `ConfigurationError` asking for `--project`.

## Run flow

```
cli.main
  Settings.load                   settings.json + environment overrides
  plan_folder.resolve_all         one plan folder, or every plan subfolder of a plan/ parent
  project_detect.load_config      the stack table, read once for the whole run
  _log_parked                   name what implementing/ and errors/ hold, so nothing is silently skipped
  for each plan folder:
    plan_folder.claim             move to plan/implementing/ (not under --dry-run) — before phases,
                                  or every Phase.path would point at the old location
    plan_folder.phases            remaining phases in NN order (or one, via --phase)
                                  --phase absent here -> skip the folder (multi-folder runs only)
    project_detect.detect         marker files -> stack -> verify commands
    --dry-run ? render and continue
    ClaudeRunner                  a fresh one per folder: REPORT.md lists only its own sessions
    PhaseRunner.run(phases)
      for each phase:
        prompt_builder.build_phase_prompt
        ClaudeRunner.run          one fresh `claude -p` process, cwd = repo root
        failed  -> report, do NOT move, do NOT commit, stop (unless --continue-on-failure)
        ok      -> plan_folder.mark_done
                   Committer.commit
      plan_folder.archive         only when every phase succeeded
    run_report.write              REPORT.md in done/, ERROR.md in the plan folder on failure
    plan_folder.release           finally, so Ctrl-C and a raised error restore too: errors/ after a
                                  failed phase, otherwise back next to the waiting plans
    failed folder -> stop, unless --continue-on-failure
```

Every phase gets a **new** Claude process (`--no-session-persistence`); nothing carries over
between phases except what the phase files and the repository itself say. That is what makes the
`00-context.md` + one-phase-file contract load-bearing.

A failed commit is reported as a phase failure, but the message says plainly that the code *is*
implemented and the phase file *was* moved — only the commit is missing.

A commit backend that fails *after* git already committed is not taken at its word: when HEAD moved
and the phase left nothing uncommitted, the commit counts as successful. "Nothing uncommitted" is
measured against a `dirty_paths` baseline captured before the phase's session started, so a file
that was already dirty beforehand — an earlier phase, another session — cannot fail this phase.

## Modules

| Module | Responsibility |
|---|---|
| `cli.py` | Argument parsing, wiring, the loop over the resolved plan folders, dry-run rendering, exit codes |
| `runner.py` | `PhaseRunner` — the sequential loop and its `RunContext`; owns all success/failure bookkeeping |
| `plan_folder.py` | Resolve the folder (or every plan subfolder of a `plan/` parent) and its repo root, order phases, claim/release the folder's state directory, `done/` moves, archive, repo-relative path rendering |
| `project_detect.py` | Validate `config/project_types.json`, match markers, resolve verify commands |
| `prompt_builder.py` | Render the per-phase prompt |
| `claude_runner.py` | `ClaudeRunner` (process) and `ClaudeStream` (stream-json parsing) |
| `tool_summary.py` | One readable console line per tool call |
| `run_report.py` | Append the run to `REPORT.md`; write `ERROR.md` when a phase failed |
| `committer.py` | Dispatch the commit spec to Claude or to the shell |
| `settings.py` | `settings.json` + environment overrides, validated with pydantic |
| `models.py` | The typed values crossing those boundaries |
| `constants.py` | Every literal file name, pattern, environment variable and default |
| `errors.py` | `ConfigurationError` (exit 2) and `OperationalError` |
| `app_logger.py` | `AppLogger` — the only module that writes to the console |
| `skill_installer.py` | Download the slash commands this tool expects into `~/.claude/commands` (`install-skills.bat`) |

`ClaudeRun` (a `Protocol` in `claude_runner.py`) is the single seam: `PhaseRunner` and
`Committer` both take it, so a test can substitute the whole Claude interaction with
`MagicMock(spec=ClaudeRunner)`.

## Prompt

`prompt_builder.build_phase_prompt` follows `/plan:implement-phase` steps 3, 5, 6 and 7, with the
interactive parts removed. It tells Claude to:

- read `00-context.md` and then the phase file completely, treating the recorded research as a
  starting point and re-researching only what has actually moved;
- follow the phase steps in order, obeying `CLAUDE.md` / `CODING_RULES.md`, no unrelated changes;
- run the phase's own `## Verify` checks, then the detected stack's checks, and fix until green;
- **not** move, rename or delete the phase file, and **not** commit — this tool does both;
- stop and report if an unresolved Open Question in `00-context.md` blocks the phase, since a
  headless run cannot ask.

Commands already named in the phase's own `## Verify` section are dropped from the injected list
(whitespace-, slash- and case-insensitive comparison), so a check is never asked for twice. When
no stack could be detected and the repo has no `tools/*.bat`, the prompt instead tells Claude to
read `CLAUDE.md` and choose the checks itself.

## Console output

`ClaudeStream` parses the `stream-json` event stream into live output — model text streamed
verbatim, one `-> Tool: <argument>` line per tool call, one `[done]`/`[FAILED]` line per tool
result — plus the final `ClaudeResult` (success, message, duration, cost). Non-JSON lines
(startup banners, crashes) are printed as `[Claude] …` rather than swallowed.

A non-zero exit code from `claude` is a failure even when a `result` event said otherwise, and a
run that produced no `result` event at all is a failure too.

Everything goes through `AppLogger`, including the character-level streaming (`AppLogger.stream`),
so console output has one off switch.

## Run report

The console is not a record, so every run also writes one. `ClaudeRunner` keeps a `SessionRecord`
for each process it starts — the label the caller passed (the phase file name, or `commit`), the
result, its cost and its `TokenUsage`, parsed from the `usage` field of the `result` event. That
list lives on the concrete runner rather than on the `ClaudeRun` protocol, so `PhaseRunner` and
`Committer` need no extra dependency and `cli.main` can hand it straight to `run_report.write`.
Commit sessions therefore count too — `/git:commit` is a real Claude process with real tokens.

`REPORT.md` is appended, never overwritten: the next run number comes from counting the existing
`## Run ` headings, so a plan implemented across several sittings keeps its full history in one
file. An interrupted run writes nothing — `cli.main` returns on the `KeyboardInterrupt` before the
report is reached.

## Tests

- `tests/unit/` — plan folder resolution (single folder and `plan/` parent) and bookkeeping, detection (a parametrized table driven by the real
  `config/project_types.json`, so it cannot drift), commit dispatch, stream parsing from canned
  events, prompt content, settings resolution, slash command installation (with an injected downloader,
  so no test touches the network).
- `tests/integration/` — a full run against a fake `claude` batch stub emitting canned
  `stream-json`: phases land in `plan/done/<folder-name>/`, the commit spec runs once per phase,
  the folder is archived, `REPORT.md` lands next to them; a run pointed at the `plan/` parent does
  that for every plan subfolder, each with its own report; a failing run moves and commits nothing
  but still leaves `ERROR.md` and a report; `--dry-run` changes nothing.
  Windows-only (the stub is a `.bat`).

Run them with `tools\run_tests.bat` and `tools\run_integration_tests.bat`.
