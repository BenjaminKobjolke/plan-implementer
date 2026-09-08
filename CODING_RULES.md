<!-- Managed by /coding-rules:apply — do not edit rule blocks by hand -->
<!-- codex: enabled -->
<!-- deepseek: disabled -->

# Version
5

Increase this version number whenever this rule file changes.

# Common Rules (All Languages)

These rules apply to all projects, regardless of language. Language-specific rules live in the
corresponding `*_RULES.md` files.

---

## Keep CODING_RULES.md in Sync

When working on a project, copy all relevant rules into the project's `CODING_RULES.md` file
(project root). The project's `CLAUDE.md` carries only a small versioned pointer block that
mandates reading `CODING_RULES.md` before code work — never the full rules, and never an
`@import` of `CODING_RULES.md` (imports auto-expand into context every turn).

- Always include all rules from `COMMON_RULES.md` and `AI_RULES.md`
- Also include applicable language-specific, project-type, and supplemental rule files
  (see `PROJECT_TYPES.md` for the project-type overview)
- Include optional addon rule files only when the user has opted in to that addon
- If applicability is unclear, ask the user which rules to include
- Include each source file's `# Version` block with its copied rules
- If `CODING_RULES.md` already exists, compare each source file's version with the corresponding
  copied rule block and update only stale or unversioned blocks, keeping the result deduplicated
- If `CLAUDE.md` contains inlined rule blocks or coding-rule `@import` lines from an earlier run,
  migrate that content into `CODING_RULES.md` and leave only the pointer block in `CLAUDE.md`

---

## Use Objects for Related Values

When multiple related values must be passed between classes or methods, bundle them into a
dedicated object (e.g., DTO/Settings/Config) instead of passing many parameters. This improves
readability, reduces call-site churn, and makes changes safer.

---

## No Bag-of-Keys Returns at Module Boundaries

When a public method on a manager/repository/service returns data that crosses a module
boundary, the return type must be a typed object (DTO, value object, or domain model) — never
a raw associative array indexed by string keys. Plain `array` returns silently swallow shape
bugs: a missing key reads as `null`, a list-vs-single mix-up reads as "no data", and renames
go undetected by static analysis.

- **Anti-pattern.** `getSettingsValue(...)` returns `array|null`; callers do `$result['value']`,
  `$result['type']`. A consumer mis-indexes `$result[0]['value']` after a refactor; nothing
  flags the change. The function silently returns `null` and downstream defaults take over.
- **Correct pattern.** Return a class — `getSettingsElement(...): ?SettingsElement`. The class
  exposes `getValue()`, `getType()`, `exists()`. Typed, autocompleted, statically checked;
  renames propagate via the IDE.
- **Lists vs single must be obvious from the type and the name.** `getThing(): ?Thing`
  (zero or one) vs `getThings(): ThingList` or `iterable<Thing>`. Never overload the same
  return type to mean both.
- **Distinguish absent from empty.** `null` from a lookup means "not found"; an empty
  collection means "found, but had nothing". A typed return makes this contract explicit;
  a bag-of-keys array hides it.
- **JSON-decoded blobs are arrays too.** The rule applies equally to `json_decode($column, true)`
  results that cross a module boundary — wrap them in a value object before they leave the
  layer that owns the schema.
- **Internal helpers may stay arrays.** This rule targets *public* API on managers and the
  boundary where a domain abstraction starts. Pure-private array juggling inside a single
  method is fine.

---

## Reuse Existing Models Before Inventing Array Shapes

Before designing a new return type or DTO, search the codebase for an existing domain class
that already owns the same data. Most "should this be a DTO?" decisions are actually
"is there already a `Contest` / `User` / `Order` class that should absorb this method?"

- Grep for the table name, the primary key, and the most distinctive column.
- If a model already exists with a constructor that accepts the row shape, use it — don't
  invent a parallel array shape that mirrors the same columns.
- Adding a `getXxxObject()` alongside a legacy `getXxxData()` is acceptable as a migration
  step; keep both only until consumers are migrated, then delete the array-returning version.

---

## Tests Pin the Shape Before the Refactor

When converting a bag-of-keys return to a typed object, write a **characterization test
first** that locks the current behavior using the existing API, run it green against the
unrefactored code, and then refactor. The same test (or a renamed-but-equivalent one) must
remain green afterward.

This converts "I think the new object preserves behavior" into "the test proves it." Pair
with the "Test-Driven Development" rule below — characterization tests are TDD applied to
refactors instead of new features.

---

## Test-Driven Development for Features and Bug Fixes

Follow TDD when implementing features or fixing bugs:

1. Write tests first
2. Run the tests and confirm they fail
3. Implement the change or fix
4. Run the tests again and confirm they pass

---

## Integration Tests

Every project must include integration tests in addition to unit tests. Integration tests verify that
components work correctly together and catch issues that unit tests alone cannot detect.

---

## Test Runner Scripts

Every project must provide the following batch files in the `tools/` directory:

- `tools/run_tests.bat` — runs unit tests
- `tools/run_integration_tests.bat` — runs integration tests

These scripts ensure a consistent way to execute tests across environments.

Both must **exit with the test runner's own exit code** — capture it right after the run
(`set TESTRESULT=%ERRORLEVEL%`) and end with `exit /b %TESTRESULT%`. A bat that prints
"Some tests failed!" but exits 0 reports green to CI, to callers and to AI agents. Never pipe the
test command into a filter — the pipe's exit code is the *filter's*, not the runner's; write to a
temp file and filter that instead.

---

## No `pause` in Batch Files

Batch files must never contain a `pause` line. `pause` waits for a keypress, so any bat that has one
hangs forever when run by CI, another bat, or an AI agent. End with an explicit `exit /b <code>`
instead, and let the caller decide whether to keep the window open (`cmd /k`).

---

## Prefer Type-Safe Values

Use strong, explicit types instead of loosely typed or stringly typed values (e.g., typed DTOs,
enums, generics, typed settings). This ensures mistakes are caught at compile time or by tests
early in development.

---

## String Constants

Centralize string constants in a dedicated module/class. Do not scatter raw strings across
the codebase. Use language-appropriate patterns for constants and reuse them consistently.

---

## Reusable Tooling

Before building project-specific infrastructure scripts (audits, codemods,
build helpers, lint checks, etc.) for a project, check the matching
language's `*_setup_files/` folder under this `coding-rules` repo for an
existing equivalent. If found, copy or reference it. If not:

1. Build the script in the project and prove it on real data.
2. Copy the script into the right `*_setup_files/tools/` folder.
3. Document it in that language's `*_RULES.md` so the next project picks
   it up automatically.

This keeps cross-project tooling consistent and prevents the same script
from being re-invented in every new project.

---

## README.md is Mandatory

Every project must have a `README.md` file in the root directory. It should include:

- Project name and description
- Installation/setup instructions
- Usage examples
- Dependencies and requirements

---

## Don't Repeat Yourself (DRY)

Avoid code duplication. If the same logic appears in multiple places, extract it into a
reusable function, class, module, or utility.

- Duplicate code is harder to maintain and leads to bugs
- Extract shared logic into helpers or base abstractions
- Use constants for repeated values

---

## Derive, Don't Duplicate — One Value Owns the Derivation

When one value strictly determines another, pass only the determinant and derive the rest —
never thread both side-by-side through call sites, constructors, and events. Two co-varying
parameters are a functional dependency in disguise; passing both lets them drift into illegal
combinations.

- **Anti-pattern.** `createLog(ActionCategory $cat, ActionType $type)` threaded through ~10
  sites. Nothing stops a caller passing `category: email, type: lead.created`.
- **Correct pattern.** The richer type owns the relationship: `ActionType::category()` returns
  its `ActionCategory` via a single exhaustive `match`. Call sites pass only `ActionType`;
  category is always derived, so a mismatch is unconstructable.
- **Apply when** one value *determines* the other (a true functional dependency).
- **Don't apply when** the relationship is many-to-many or genuinely independent — forcing a
  derivation that doesn't exist couples things that should stay separate.
- **Keep derivation cheap and pure** — a getter/match, no DB or IO behind a call that looks free.
- **Keep the mapping exhaustive** (enum + exhaustive match) so a new case cannot silently skip
  its derived value.

This is Single Source of Truth applied to parameters, and a form of "make illegal states
unrepresentable." Pairs with "Prefer Type-Safe Values" and "Self-Describing Classes".

---

## Keep It Simple (KISS)

Prefer the simplest solution that actually works. Complicated logic for a simple result must be
kept to a minimum — a future maintainer (or you, at 3am) has to understand it.

- **YAGNI.** Don't build for a need that isn't here yet: no interface with a single
  implementation, no factory for one product, no config for a value that never changes.
- **Boring over clever.** Clever is what someone decodes later. The obvious solution wins.
- **Deletion over addition.** The shortest working change is usually the right one.
- Pairs with "Don't Repeat Yourself" and "No God Classes" — simplicity is what those rules
  are protecting.

---

## Confirm Dependency Versions

Before adding any new package or library, confirm the version with the user to ensure we use
up-to-date dependencies.

- Do not assume which version to use
- Ask the user to verify the latest stable version
- Avoid outdated packages that may have security vulnerabilities or missing features

---

## Error Handling & Logging Strategy

Every project must have a centralized error handler rather than ad-hoc try/catch blocks scattered
throughout the codebase.

- Use structured logging (not `print`/`console.log`/`echo`)
- Log at appropriate levels: debug, info, warning, error
- Include context in log messages (module name, operation, relevant IDs)

---

## Centralized Logger — Single Off Switch

Route all logging through one dedicated logger class/module. Never call the language's
built-in output directly for logging (`print`, `console.log`, `echo`, `Debug.Log`,
`System.out`). Code calls the project logger; the project logger wraps the underlying sink.

- **One toggle.** Because every log goes through one place, logging can be turned off,
  level-filtered, or redirected (file, console, remote) from a single config flag — without
  touching call sites. Example: a `logEnabled` / `logLevel` setting the logger checks once.
- **Levels live in the logger.** Callers pass a level (debug/info/warning/error); the logger
  decides what is emitted based on central config. Callers never branch on "should I log?".
- **Wrap, don't scatter.** Built-in calls (`print`, framework loggers, `Debug.Log`) appear
  in exactly one file — the logger implementation. Everywhere else imports the logger.
- **Language specifics** still apply (e.g. Unity `[Conditional]` stripping, Flutter `logger`
  package, Python `logging`) — but they are configured inside the central logger, not at
  call sites.

The logger's name is fixed per language so it is the same known type in every project (see each
`*_RULES.md` for details):

| Language      | Class / export     | File                |
|---------------|--------------------|---------------------|
| Python        | `AppLogger`        | `app_logger.py`     |
| PHP           | `Logger`           | `Logger.php`        |
| Dart/Flutter  | `AppLogger`        | `app_logger.dart`   |
| Kotlin        | `AppLogger`        | `AppLogger.kt`      |
| C# (plain)    | `AppLogger`        | `AppLogger.cs`      |
| Unity C#      | `GameLog` (static) | `GameLog.cs`        |
| Svelte/JS/TS  | `logger` (export)  | `logger.ts`         |
| Arduino       | `Log`              | `Log.h` / `Log.cpp` |

---

## Input Validation at Boundaries

Always validate data at system boundaries — API inputs, user input, file uploads, external service
responses.

- Never trust external data; validate before processing
- Use language-appropriate validation libraries (e.g., Pydantic, Zod, FluentValidation)
- Fail fast with clear error messages when validation fails

---

## Maximum File Length — 300 Lines

Split files when they exceed 300 lines to keep code navigable during fast iteration.

- Extract classes, functions, or components into separate modules
- Group related extractions logically (by domain, not by type)
- Exceptions: generated files, configuration files, test files with many similar cases

---

## Naming Conventions

Be consistent within a project. Follow these defaults unless the language or framework dictates
otherwise:

- Files: `snake_case` (or language convention, e.g., `PascalCase` for C# classes)
- Classes: `PascalCase`
- Functions/methods: language convention (`snake_case` for Python/PHP, `camelCase` for Dart/JS/C#)
- Constants: `UPPER_SNAKE_CASE`
- Variables: language convention (`snake_case` for Python/PHP, `camelCase` for Dart/JS/C#)

---

## Comments Explain Why, Not What

Comment intent and non-obvious reasoning — not a restatement of the code. Good names carry the
*what*; comments carry the *why*.

- **Anti-pattern.** `i++ // increment i`. Redundant comments add noise and rot the moment the
  code changes.
- **Correct pattern.** Document *why* a workaround exists, why a non-obvious algorithm was
  chosen, or a constraint that isn't visible locally (`// API rejects batches > 500`).
- Prefer self-documenting code (clear names, small functions) over a comment that compensates
  for unclear code — see "Naming Conventions" and "Keep It Simple".
- Document the purpose of each module/class at its top.
- Keep comments in sync with the code; delete stale ones rather than letting them mislead.

---

## Security Baseline

Every project must follow these minimum security practices:

- Never commit secrets (`.env`, API keys, credentials, private keys)
- Escape output to prevent XSS/injection attacks
- Use parameterized queries or ORM-provided methods — never concatenate user input into queries
- Validate and sanitize all user input at system boundaries
- Keep dependencies updated to avoid known vulnerabilities

---

## No Hardcoded Environment Values

Never hardcode environment-specific values in code — filesystem paths, hostnames, IP addresses,
ports, base URLs. They differ across machines and environments and make code non-portable.

- **Anti-pattern.** `connect("192.168.1.50:5432")`, `open("C:\\Users\\bob\\data\\out.json")`.
- **Correct pattern.** Read them from the project's central config (the config class each
  `*_RULES.md` already mandates), with a committed `.example` template documenting every key.
- Distinct from the secrets rule above: this is about **portability** (runs anywhere), not
  secrecy. A non-secret hostname still belongs in config, not in code.

---

## No God Classes

A class that handles too many responsibilities becomes fragile, hard to test, and impossible to
reuse. Keep each class focused on a single purpose.

- **Warning signs**: more than 5 public methods, more than 4 constructor dependencies, or methods that span unrelated domains (e.g., a class that validates input, queries the database, and sends emails)
- Split by responsibility: extract collaborators (e.g., a `Validator`, a `Repository`, a `Notifier`) rather than piling logic into one class
- If you struggle to name the class without using "Manager", "Handler", "Service", or "Helper" as a catch-all, it likely does too much
- This complements the 300-line file rule — a short class can still be a god class if it owns too many concerns

---

## Self-Describing Classes

When behavior depends on which fields or properties a class has — such as search, serialization,
display, validation, or auditing — the class itself must declare those fields through a contract
(interface, abstract method, attribute/annotation, or introspection pattern). Never hardcode field
lists in consuming code.

- **Anti-pattern**: A search service contains a hardcoded list of fields to index for each entity;
  adding a new field requires updating every consumer manually
- **Correct pattern**: Each class implements a contract (e.g., `GetSearchableFields()`,
  `GetDisplayColumns()`) that returns its own relevant fields, so adding a field in one place
  automatically propagates everywhere
- This applies to any cross-cutting concern that operates over class fields: search, filtering,
  export, form generation, diffing, logging, etc.
- Combine with compile-time checks where the language supports them (e.g., sealed interfaces,
  exhaustive matching) to ensure new fields cannot be silently ignored

---

## Inject Collaborators, Don't Fold Dependencies In

Composition reuse comes in two shapes, and they differ sharply in how much coupling they add to
the reusing class. **Folding** a helper into a class (mixin, trait, multiple inheritance, copy-in
include) merges *all of the helper's own dependencies* into that class — reuse five such helpers
and every one of their imports is now the host's coupling. **Injecting** a collaborator adds a
single dependency: the collaborator, which is built once and shared as a hub.

Prefer injected collaborators. Reserve fold-in reuse for helpers that are stateless and carry no
dependencies of their own.

- **Anti-pattern**: A controller reuses five behavior mixins/traits; each brings its own service,
  DTO, and constant imports, so the controller transitively depends on a few dozen things and is
  hard to test in isolation.
- **Correct pattern**: Extract that behavior into a collaborator object injected via the
  constructor. The controller depends on the collaborator; the collaborator is reused across many
  controllers as a shared, well-tested hub.

### Inject services; never instantiate one inside a method

Constructing a service with `new` (or the language equivalent) inside a method hides the
dependency from the class's public contract and makes it impossible to substitute in a test. Pass
collaborators in through the constructor.

- **Anti-pattern**: A method does `helper = new EmailPreparer(); helper.prepare(...)`. Nothing in
  the class signature reveals the dependency, and no test can replace it.
- **Correct pattern**: Inject `EmailPreparer` once; the method calls the injected instance.

### Collapse config-callback swarms into one value object

When a base class pulls its configuration from the subclass through many small overridable getters
that the subclass fills in one-line-each, each getter is a separate touch-point and the wiring is
spread across dozens of methods. Bundle the related values into a single config object built once
and handed to the base (see **Use Objects for Related Values**). This also keeps such classes off
the wrong side of **No God Classes**.

- **Anti-pattern**: A subclass implements `getSendEndpoint()`, `getSendSuccessKey()`,
  `getSendFailureRedirect()`, and a dozen more one-line getters, each naming one constant.
- **Correct pattern**: The subclass builds one `SendConfig` value object once; the base reads its
  fields.

# Version
20

Increase this version number whenever this rule file changes.

# AI Workflow Rules (All Languages)

See `COMMON_RULES.md` for rules that apply to all languages.

Unlike the per-language `*_RULES.md` files, these rules are **language-independent** and
**always apply**. They are not subject to the "some rules may not apply to this project"
filtering — include them in every project's `CODING_RULES.md`.

These rules define the end-to-end workflow an AI agent must follow when planning and
implementing changes. Each step is an existing skill referenced by its slash name; run the
skill rather than reimplementing its behavior.

---

## Delegation backends (Codex / DeepSeek)

Some of the workflow steps below can be delegated to an external CLI instead
of being performed by the agent itself. Two backends are supported, and they
are **mutually exclusive** — at most one is enabled at a time:

- `<!-- codex: enabled -->` — delegate to Codex, running:
  `codex exec --dangerously-bypass-approvals-and-sandbox "<PROMPT>"`
- `<!-- deepseek: enabled -->` — delegate to DeepSeek, running:
  `reasonix run --auto "<PROMPT>"`
- Neither marker `enabled` (or no marker) — do NOT delegate; perform the same
  checks yourself via the listed fallback skills.

Read precedence if both markers somehow end up `enabled`: Codex wins, then
DeepSeek, then the self-fallback.

**Self-fallback in a subagent.** When neither backend is enabled, prefer
running each fallback skill in a subagent (Agent/Task tool, `general-purpose`
type) rather than inline — the skill's file reads and reasoning stay out of
the main context window. The subagent runs the skill and returns **only**
its summary (and the list of files it changed). Any file edits the skill
makes (plan file, code) persist, so the main agent picks them up.

Exceptions that MUST stay in the main context: `/plan:dry-checked` (it
reloads the adjusted plan INTO context) and restating the
Definition-of-Done / DRY gate aloud.

**Graphify preamble (optional).** If this project's `CODING_RULES.md` includes
the graphify addon, prepend its graphify delegate preamble to every `<PROMPT>`
below before invoking the backend CLI (see the graphify addon's "Delegated
checks" section). If the addon is not present, send `<PROMPT>` unchanged.

The markers are managed by `/coding-rules:codex on|off|status|test` and
`/coding-rules:deepseek on|off|status|test` (or set during
`/coding-rules:apply`). Do not flip them yourself without the user asking.

### Delegation contract (never let a delegate hang)

Applies to EVERY delegated `<PROMPT>` below, both backends. A delegate that
stops to ask a question blocks forever on stdin nobody can answer — these four
rules make that impossible and leave a debug trail when it happens anyway.

- **No questions.** Append this suffix to every `<PROMPT>` before sending it:

  > "Run fully non-interactively. NEVER ask a question and NEVER wait for
  > input. If anything is ambiguous, blocked, or you cannot complete the task,
  > do NOT stop to ask — write your questions and what blocked you into your
  > output file (the plan file, or the check file for steps that write one)
  > under a heading `## DELEGATE QUESTIONS`, then exit immediately. Always
  > write the required SUMMARY block, even on failure."

- **Timeout.** Run every delegate call with `timeout: 600000` (10 min, the
  Bash tool maximum). Never make an untimed delegate call.

- **Log.** Capture stdout+stderr to a log next to the plan file, named
  `<plan-file-path-without-.md>-<step>-delegate.log` where `<step>` is
  `plan-dry`, `convention`, `post-impl` or `graphify`; close stdin so a
  delegate that ignores the contract dies instead of blocking:

  ```
  codex exec --dangerously-bypass-approvals-and-sandbox "<PROMPT>" > "<log>" 2>&1 < /dev/null
  ```

  Overwrite the log per run. On any failure, report the log path to the user
  in one line — that is the debug handle.

- **Success check.** A delegated step counts as done only if its required
  SUMMARY block is present (`SUMMARY DRY`, `SUMMARY CONVENTION CHECK`,
  `SUMMARY GRAPHIFY`, or the post-implementation check file). A permission
  block/denial, timeout, non-zero exit, missing SUMMARY, or a
  `## DELEGATE QUESTIONS` heading all count as failure. Never retry a failed
  delegate call. How to handle the failure depends on its kind:

- **Permission failure — STOP and ask the user.** If a backend is enabled but
  the call never ran because it was blocked or denied (permission prompt
  denied, the permission classifier blocked it, or the error is an
  approval/permission error rather than backend output), do NOT run the
  `delegate disabled` branch, do NOT perform the check yourself, and do NOT
  perform any other action designated for the delegate. Report in one line
  which command was blocked and which permission entry is likely missing
  (`Bash(codex exec:*)` / `PowerShell(codex exec:*)`, or the matching
  `reasonix run` pair), then ASK the user how to proceed, offering:

  1. fix the permissions (`/coding-rules:codex on` / `/coding-rules:deepseek on`)
     and re-run the delegated step,
  2. run the `delegate disabled` fallback in a subagent this once,
  3. skip the step.

  Wait for the answer. The workflow stays paused — the DRY gate is NOT cleared,
  so implementing does not start.

- **Other failures — fallback.** For timeout, non-zero exit, missing SUMMARY,
  or `## DELEGATE QUESTIONS`: report one line plus the log path, then run that
  step's `delegate disabled` branch (subagent). If the delegate wrote
  `## DELEGATE QUESTIONS`, answer those questions yourself in the fallback run,
  or surface them to the user if they need a decision.

These rules apply to EVERY delegated step below — the plan DRY + convention
check, the post-implementation DRY audit and the graphify refresh.

## Feature / Change Workflow

After a plan is proposed and the user approves it, follow this chain. The DRY
gate is a precondition for implementing — not just an earlier step.

The approved plan must first exist as an explicit Markdown file. Pass that same
path to both plan-DRY commands.

```
plan approved

plan DRY + convention check — one step; conventions first, so what already
exists in the codebase informs the DRY rewrite instead of arriving after it
  delegate enabled (codex or deepseek — run <PROMPT> via that backend's CLI, see Delegation backends above; prepend graphify preamble if applicable; obey the Delegation contract — no-questions suffix, timeout, log, SUMMARY check; this step needs BOTH summary blocks, a missing one counts as a failed SUMMARY check):
    <PROMPT> = "FULL PATH TO PLAN $convention-check - First scan the codebase for the existing utilities, patterns and naming conventions this plan should reuse. Then, with those findings in hand, check the plan for DRY, KISS and YAGNI opportunities. Apply both sets of findings to the original plan file. Only edit the plan file — do NOT modify any source code or implement the plan. Always end with two summary blocks: SUMMARY CONVENTION CHECK — what you reused and why, or 'No convention issues found.' — and SUMMARY DRY — what you consolidated and why, or 'No DRY opportunities found.'"
  delegate disabled (two subagents, in this order — /convention:check is
  read-only and its report does not reach the /plan:dry subagent by itself):
    1. run /convention:check in a subagent (see "Self-fallback in a subagent")
    2. apply its findings to the plan file yourself
    3. run /plan:dry <plan-file> in a subagent; inline only if a subagent
       isn't available.

/plan:dry-checked    reload the DRY and convention adjusted plan

restate Definition-of-Done aloud

implement
  While implementing, keep the list of every file you created or modified in THIS
  session — you know it from your own edits; do NOT derive it from git (other
  sessions may have concurrent uncommitted changes). After implementing, write the
  list (one path per line) to a changed-files file next to the plan, named after it:
  <plan-file-path-without-.md>-changed-files.md
  (e.g. claude-plans/my-feature-changed-files.md). The plan file is unique per
  session, so concurrent sessions never collide.
  Include only source-code files. Exclude documentation and other non-code
  files (`.md`, plain-text docs, the plan file itself) — the DRY audit only
  looks at code.

post-implementation DRY audit — scope is ONLY the changed-files file above
  delegate enabled (codex or deepseek — run <PROMPT> via that backend's CLI, see Delegation backends above; prepend graphify preamble if applicable; obey the Delegation contract — no-questions suffix, timeout, log, SUMMARY check):
    <PROMPT> = "Read FULL PATH TO CHANGED-FILES FILE and check ONLY the files listed there for DRY opportunities. Do not use git status or git diff to widen the scope — other sessions may have concurrent uncommitted changes. Do NOT modify any code. Write your suggestions to <plan-file-path-without-.md>-post-implementation-check.md (next to the plan, same naming as the changed-files file), overwriting the file if it already exists. Include for each finding the affected files and a short rationale. Always write the file, even if you found nothing — in that case write a SUMMARY block stating 'No DRY opportunities found.'"
    then read that post-implementation-check file, validate each finding, and apply the valid ones. Bring a finding to the user only if a question arises — otherwise apply silently.
  delegate disabled:
    run /dry:check <files from the changed-files file, as pathspec> in a
    subagent (see note)

Post-Feature Verification + Post-Implementation Code Analysis (project-specific, below)

refresh graphify graph — only if the graphify addon is present in this project's CODING_RULES.md
  NEVER run this rebuild yourself in the main context: the graphify skill loads a
  large instruction file and its build output into the window. Delegate it — the
  rules it must follow live in the graphify addon's "Refreshing after a code
  change" section, already copied into this project's CODING_RULES.md.
  delegate enabled (codex or deepseek — run <PROMPT> via that backend's CLI, see Delegation backends above; prepend graphify preamble if applicable; obey the Delegation contract — no-questions suffix, timeout, log, SUMMARY check):
    <PROMPT> = "Rebuild this project's graphify knowledge graph. Read the graphify section of CODING_RULES.md and follow its 'Refreshing after a code change' rules exactly, including the scope rules — rebuild at the scope the existing graph already has, never narrower. Run the graphify skill's directed rebuild from the repo root (/graphify <code-dir> --directed), writing to the root graphify-out/. Do NOT run a bare `graphify update`. If the graphify skill is not available to you, change nothing and reply exactly GRAPHIFY SKILL UNAVAILABLE. Otherwise end with a summary called SUMMARY GRAPHIFY stating the scan root built, whether graph.json has directed: true, and the node count before and after."
  delegate disabled:
    run the same rebuild in a subagent (see "Self-fallback in a subagent") with the
    same instructions; it returns only the SUMMARY GRAPHIFY block.
  then verify yourself — cheap, no skill load: root `graphify-out/graph.json` has
  `directed: true`, and `graphify-out/.graphify_root` matches the scope that was
  built. If the delegate replied GRAPHIFY SKILL UNAVAILABLE, or either check fails,
  redo the rebuild via the subagent branch.
```

### DRY gate (precondition for implementing)

Do not write a single line until ALL are true. Restate this gate aloud at the
moment you start implementing — if you cannot, the gate is not cleared:

- [ ] `/convention:check` found the existing utilities/patterns to reuse, and
      they are written into the plan file.
- [ ] `/plan:dry <plan-file>` adjusted that file and completed its Ponytail pass.
- [ ] `/plan:dry-checked <plan-file>` reloaded the same adjusted plan.

The gate survives the `implement` step: if mid-implementation you add a new
helper, type, or pattern the gate would have caught, stop and re-clear it
before continuing.

### Definition of Done — restate aloud before implementing

Before the first edit, state in chat what "done" means for THIS change:

- [ ] Scope: <one line — what changes, what does not>
- [ ] Reuse: <existing function/component this builds on, with path>
- [ ] DRY gate cleared (above)
- [ ] `/dry:check <session changed-files>` clean (scoped to the changed-files file, never bare; may run via subagent)
- [ ] `/verify:after-change` green (tests + analysis; may run via subagent)

### Post-implementation DRY audit — paste-in template

Run `/dry:check` scoped to the session's changed-files file, then paste and fill:

```
DRY audit — <change name>
Changed files:     <list from the changed-files file, not git>
Duplication found: <none | describe>
Consolidated into: <shared fn/module + path | n/a>
Convention reused: <name + path>
Verdict:           <clean | needs rework>
```

---

## Bug-Fix Workflow

Bug fixes use a shorter variant (no plan-DRY phase):

```
bugs:fix
  → /verify:after-change  (run in a subagent — see "Self-fallback in a
    subagent")
```

---

## Optional Addons

These live in `ai_rules_addons/` and are **not** always-on. Each is opt-in per project — ASK
the user whether they want it before wiring it into that project's `CODING_RULES.md`.

- [`ai_rules_addons/graphify.md`](ai_rules_addons/graphify.md) — graphify knowledge graph:
  scoped + directed AST build, folder layout, gitignore, and the query/refresh rules to paste
  into a project's `CODING_RULES.md`.

# Version
6

Increase this version number whenever this rule file changes.

# Python Rules (uv)

See `COMMON_RULES.md` for rules that apply to all languages.

## Template Engine

Keep Python, HTML, CSS, and JS separated.
This means using a template engine.

Use Jinja2:

```bash
uv add jinja2
```

Do not put JS code into templates. Use separate `.js` files.

Example structure:

```
project/
├── app/
├── templates/
└── static/
    ├── css/
    └── js/
```

Example template:

```html
<!-- templates/page.html -->
<!doctype html>
<html>
  <head>
    <link rel="stylesheet" href="/static/css/app.css">
  </head>
  <body>
    <h1>{{ title }}</h1>
    <script src="/static/js/app.js"></script>
  </body>
</html>
```

---

## GUI Framework

For **desktop GUI** applications use **PySide6** (Qt for Python). Always install the
latest version — do not pin an old one:

```bash
uv add pyside6
```

This is separate from the web template engine above: Jinja2 renders web HTML,
PySide6 builds native desktop windows. Pick by app type.

### Make it look modern

Default Qt reads as a debug tool: gradient buttons, boxed tabs, a caption bar in the
user's OS accent color, no type hierarchy. Follow
[`python_setup_files/MODERN_GUI.md`](python_setup_files/MODERN_GUI.md) — the palette /
stylesheet / icons / window-chrome module split, the vendored-and-tinted icon recipe,
the Qt gotchas that break a restyle (size policies, per-widget fonts, minimum-size
floors, focus rings), and how to screenshot pages offscreen to verify it.

The design decisions behind it — tokens, one accent, hierarchy, focus states, empty and
error states — are language-independent and live in `DESIGN_RULES.md`.

---

## CLI Menus

For **interactive command-line** applications, never hand-roll a menu out of `input()`
and printed option lists. Use **`pick`** — an arrow-key menu with a selection
indicator, scrolling for long lists, and optional multiselect — on its **blessed**
backend:

```bash
uv add "pick[blessed]"
```

**Always pass `backend="blessed"`.** `pick`'s default curses backend breaks on Windows
the moment the program runs a child that inherits the console — a `git` call, a build
step, anything streaming its output live. From then on curses stops translating the
arrow keys for the rest of the process: the keys still arrive, but as raw `ESC [ A`
sequences that `pick` ignores, so every later menu draws and then accepts nothing. It
looks like a hang and it is sticky — re-initialising curses does not recover it, and
neither does restoring the console mode. Only never letting the child touch the console
(capturing its output, which costs live streaming) or decoding the sequences avoids it.
blessed decodes them, so subprocesses keep the console and their live output.

### Wrap it — one menu helper per project

Never import `pick` at more than one call site. Wrap it in a single helper class
(e.g. `menu.py` / `UserChoicesHandler`) so keyboard handling, the indicator style,
and Ctrl-C behavior are defined once:

```py
# src/<pkg>/menu.py
import sys
from pick import pick


def show_menu(
    options: list[str],
    title: str,
    indicator: str = "*",
    default_index: int = 0,
) -> int:
    """Show an arrow-key menu; return the selected index. Ctrl-C exits."""
    try:
        _, index = pick(
            options=options,
            title=title,
            indicator=indicator,
            default_index=default_index,
            backend="blessed",  # never the curses default: see above
        )
        return index
    except KeyboardInterrupt:
        sys.exit(1)
```

### Keep option labels and actions in step

The menu returns an **index**, not a parsed letter. Build the label list and a parallel
list of typed action values (enum members — see "Prefer Type-Safe Values") in the same
place, so an option can never be shown without a handler:

```py
options: list[str] = []
actions: list[MenuAction] = []
options.append("Commit"); actions.append(MenuAction.COMMIT)
if repo.has_untracked:
    options.append("Add all"); actions.append(MenuAction.ADD_ALL)
options.append("Cancel"); actions.append(MenuAction.CANCEL)

action = actions[show_menu(options, title)]
```

### Testing

`pick` needs a real terminal, so tests must not call it. Patch the project's wrapper
(`show_menu`) — not `pick` itself — and assert on the option labels it was handed:

```py
monkeypatch.setattr("<pkg>.menu.show_menu", lambda options, title, **kw: 0)
```

Keep a non-interactive path for every menu (a CLI flag, or auto-select when there is a
single option) so the program stays scriptable and testable without a TTY. Have the
wrapper refuse outright when `sys.stdin`/`sys.stdout` is not a TTY: without a console the
menu blocks on a key that can never arrive, which reads as a freeze rather than an error.

Because the tests patch the wrapper, nothing in the suite ever drives a real menu — so
also keep a small manual script (`tools/menu_smoke.py` + a `.bat`) that opens a menu, runs
a subprocess inheriting the console, then opens another menu. That second menu is exactly
what the curses backend breaks, and only a human at a terminal can see it.

---

## Localization

Use the `python-localization` library for multi-language support:
https://github.com/BenjaminKobjolke/python-localization

### Installation (uv)

#### Option A (recommended): Add as dependency to the project

```bash
uv add "git+https://github.com/BenjaminKobjolke/python-localization.git"
```

#### Option B: Install into the current environment (without adding to project deps)

```bash
uv pip install "git+https://github.com/BenjaminKobjolke/python-localization.git"
```

### Directory Structure

```
project/
├── lang/
│   ├── en.json    # English (default)
│   ├── de.json    # German
│   └── fr.json    # French
├── app/
└── templates/
```

### Translation File Format

Create `lang/en.json` with nested structure:

```json
{
  "nav": {
    "dashboard": "Dashboard",
    "settings": "Settings",
    "logout": "Logout"
  },
  "auth": {
    "login_title": "Login",
    "signin_subtitle": "Sign in to access your dashboard",
    "error": {
      "auth_failed": "Authentication failed. Please try again.",
      "rate_limited": "Too many attempts. Please try again later."
    }
  },
  "flash": {
    "success": {
      "saved": "Changes saved successfully.",
      "deleted": "Item deleted successfully."
    },
    "error": {
      "not_found": "Item not found.",
      "invalid_id": "Invalid ID."
    }
  },
  "common": {
    "cancel": "Cancel",
    "save": "Save",
    "delete": "Delete",
    "edit": "Edit"
  }
}
```

### Python Setup

#### Container Integration

Add a method to your DI container:

```py
# app/container.py
from pathlib import Path

# Adjust import to the real package name of your library
# from python_localization import Localization

class Container:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self._localization = None

    def get_localization(self):
        if self._localization is None:
            self._localization = Localization(
                driver="json",
                lang_dir=str(self.base_dir / "lang"),
                default_lang="en",
                fallback_lang="en",
            )
        return self._localization
```

#### Controller Helper

Add translation helper to your base controller:

```py
# app/web/base_controller.py
class BaseController:
    def __init__(self, container):
        self.container = container

    def get_localization(self):
        return self.container.get_localization()

    def t(self, key: str, params: dict[str, object] | None = None) -> str:
        return self.get_localization().t(key, params or {})
        # or .translate(...) / .lang(...), depending on your library
```

Usage in controllers:

```py
from app.i18n.keys import TK

# Simple translation
self.add_flash("success", self.t(TK.FLASH_SUCCESS_SAVED))

# With placeholders
self.add_flash("info", self.t("messages.welcome", {":name": user.name}))
```

---

## Jinja2 Integration

### Add the `t()` Function

Where you configure Jinja2:

```py
# app/web/templates.py
from jinja2 import Environment, FileSystemLoader
from app.i18n.keys import TK

def create_env(localization, templates_dir: str) -> Environment:
    env = Environment(loader=FileSystemLoader(templates_dir), autoescape=True)

    def t(key: str, params: dict[str, object] | None = None) -> str:
        return localization.t(key, params or {})

    env.globals["t"] = t
    env.globals["TK"] = TK
    return env
```

### Usage in Templates

Simple translations:

```html
<h1>{{ t(TK.NAV_DASHBOARD) }}</h1>
<button>{{ t(TK.COMMON_SAVE) }}</button>
<a href="/logout">{{ t(TK.NAV_LOGOUT) }}</a>
```

With placeholders (define in JSON as `:placeholder`):

```json
{
  "messages": {
    "welcome": "Hello, :name!",
    "items_count": "You have :count items"
  }
}
```

```html
<p>{{ t("messages.welcome", {":name": user.name}) }}</p>
<p>{{ t("messages.items_count", {":count": items|length}) }}</p>
```

Conditional content:

```html
{% if error == "auth_failed" %}
  {{ t("auth.error.auth_failed") }}
{% elif error == "rate_limited" %}
  {{ t("auth.error.rate_limited") }}
{% endif %}
```

In attributes:

```html
<a href="/back" title="{{ t('common.back') }}">
  <i class="icon-back"></i>
</a>

<button onclick="return confirm('{{ t('confirm.delete') }}')">
  {{ t('common.delete') }}
</button>
```

---

## Translation Key Naming Convention

Use dot notation with logical grouping:

```
section.subsection.key

nav.dashboard            - Navigation items
auth.login_title         - Authentication related
flash.success.saved      - Flash messages by type
flash.error.not_found
form.label.name          - Form labels
form.placeholder.email   - Form placeholders
form.validation.required - Validation messages
common.save              - Reusable UI elements
errors.404.title         - Error pages
```

---

## Translation Keys as Constants

Using raw strings like `t("nav.dashboard")` is error-prone. Create a `TK` class with all keys as constants for IDE autocomplete and refactoring safety.

Create `app/i18n/keys.py`:

```py
# app/i18n/keys.py
class TK:
    # Navigation
    NAV_DASHBOARD = "nav.dashboard"
    NAV_SETTINGS = "nav.settings"
    NAV_LOGOUT = "nav.logout"

    # Auth
    AUTH_LOGIN_TITLE = "auth.login_title"
    AUTH_ERROR_AUTH_FAILED = "auth.error.auth_failed"

    # Flash messages
    FLASH_SUCCESS_SAVED = "flash.success.saved"
    FLASH_ERROR_NOT_FOUND = "flash.error.not_found"

    # Common
    COMMON_CANCEL = "common.cancel"
    COMMON_SAVE = "common.save"
```

Usage in controllers:

```py
from app.i18n.keys import TK
self.add_flash("success", self.t(TK.FLASH_SUCCESS_SAVED))
```

Usage in templates:

```html
{{ t(TK.NAV_DASHBOARD) }}
```

### Benefits

* IDE autocomplete for all translation keys
* Refactoring support
* Easy to find all usages of a key
* Fewer typos / runtime missing-key bugs

---

## Adding New Languages

1. Copy `lang/en.json` to `lang/de.json`
2. Translate all values (keep keys identical)
3. Change language in configuration:

```py
self._localization = Localization(
    driver="json",
    lang_dir=str(self.base_dir / "lang"),
    default_lang="de",
    fallback_lang="en",
)
```

---

## Project Setup Scripts

Copy the setup batch files from the `python_setup_files/` folder bundled with the
coding-rules plugin (next to this rules file).

### install.bat

Initial project setup:

- Checks if `uv` is installed
- Creates virtual environment via `uv sync --all-extras`
- Runs tests to verify setup

### update.bat

Update all dependencies:

- Updates lock file with `uv lock --upgrade`
- Syncs updated dependencies
- Runs linting checks (`ruff`, `mypy`)
- Runs tests to verify compatibility

### tools/run_tests.bat

Run the test suite:

- Runs `pytest tests/ -v` with verbose output
- Shows pass/fail summary
- Projects that split unit/integration point it at `tests/unit`

### tools/run_integration_tests.bat

Run the integration test suite:

- Runs `pytest tests/integration -v`
- Same uv check + summary as run_tests.bat

### Usage

```bash
# First time setup
install.bat

# Run tests
tools\run_tests.bat

# Update dependencies
update.bat
```

---

## Release Workflow

Set up the release system with `/release:setup`. Reusable pieces live in
`python_setup_files/`:

- `tools/release/build_number.py` — self-contained helper: manages the integer in
  `build_version.txt` (project root) and prints the `<version>_<build>` label
  (version from `pyproject.toml`). Actions: `get | increment | decrement | label`.
- `tools/build_get.bat`, `tools/build_increment.bat`, `tools/build_decrement.bat`,
  `tools/version_get.bat` — thin `uv run` wrappers over the helper.
- `CREATE_NEW_RELEASE.template.md` — fill-in-the-blanks for `docs/CREATE_NEW_RELEASE.md`.
- The Python stack recipe read by `/release:create-release-notes` lives in the shared
  `coding-rules/CREATE_RELEASE_NOTES.md` (`## Python / uv` section), not here.

Conventions:

- **Release label** = `<version>_<build>` (e.g. `0.1.0_22`). `version` is semver in
  `pyproject.toml` (bumped by hand); `build` is an integer in `build_version.txt`.
- **Release notes** = `release_notes/<version>_<build>/<locale>.json`. The actual
  text is the `notes` array. Author **only `en.json`**; generate other locales with
  a translation bat (mandatory — never skip).
- **Bundle `release_notes/` into the build** so the in-app view ships with the binary
  (PyInstaller: add to spec `datas` + `copy_metadata(<pkg>)`).
- **In-app view**: load all releases, sort **newest first**, show the latest first
  with Older/Newer navigation, fall back to `en.json` when a locale is missing.

---

## Windows Installer (NSIS)

Ship a single `…Setup.exe`, not a zipped folder. Use **NSIS** (`makensis`) — it is
the tool already in use across these projects, and a hand-written `.nsi` is ~100
lines. Do not reach for Inno Setup, WiX, or fbs: fbs generates its NSIS script for
you but drags in a whole build system, and a plain `uv run pyinstaller` project does
not need one.

Reusable pieces in `python_setup_files/`:

- `installer/setup.nsi.template` — the script; fill in app name, exe name, company.
- `tools/build_installer.bat` — packages an existing `dist/<App>/` into the setup exe.
- `tools/sign_exe.bat` — code-signs one exe via the XIDA network-share handshake.

Conventions:

- **Two separate bats, no chaining.** `tools/compile_exe.bat` freezes;
  `tools/build_installer.bat` packages and fails with "run compile_exe.bat first" if
  `dist/` is missing. Neither bat calls the other.
- **Version and build reach the installer as `/D` defines** from the bat
  (`/DVERSION= /DBUILD= /DSRCDIR= /DOUTFILE=`), never via the exe's version resource.
  A bare PyInstaller CLI build has no `--version-file`, so there is no resource to
  read — the bat owns the label. `tools/version_get.bat` already prints the full
  `<version>_<build>` label, so read it once and split on `_` rather than also
  calling `build_get.bat`.
- **Output** = `dist/<App>Setup_<version>_<build>.exe`, so the filename carries the
  release label (see **Release Workflow** above).
- **Exclude the app's own runtime files from the payload**:
  `File /r /x settings.json /x sessions.db "${SRCDIR}\*.*"`. PyInstaller builds into
  `dist/`, and every local test run of that exe drops its config and database right
  beside it. Without the exclusions the installer ships the developer's machine
  config and personal data to every user. Verify by listing the install directory
  after a test install — this is not theoretical, it happened.
- **Per-user install into `$LOCALAPPDATA` with `RequestExecutionLevel user`** whenever
  the app writes its data next to its own exe (the
  `DATA_ROOT = Path(sys.executable).parent` pattern). A `C:\Program Files` install
  cannot write there unelevated. Bonus: no UAC prompt at all.
- **Kill the running instance before install and uninstall**:
  `nsExec::Exec 'taskkill /F /IM "${EXENAME}"'`. Ships with Windows, needs no NSIS
  plugin, and a non-zero exit just means it was not running. Without it, upgrading
  while the app is open fails on a locked file.
- **Never delete user data on uninstall.** Remove the program files, shortcuts and
  the `HKCU\...\Uninstall\<App>` key; leave `settings.json` and the database. Use
  plain `RMDir` (not `/r`) on the install root so the folder survives when they do.
- **Registry** goes under `HKCU` (per-user install) with `DisplayName`,
  `DisplayVersion` = the full label, `Publisher`, `DisplayIcon`, `InstallLocation`,
  `UninstallString`, `EstimatedSize`.
- **Signing is opt-in** via `build_installer.bat --sign`, off by default: the XIDA
  handshake needs the `//XIDA-SERVER` share and takes ~5 minutes per binary, so local
  test builds stay unsigned. When on, sign the app exe **before** packaging (the
  signed binary must be the one inside) and the setup exe after. `sign_exe.bat` `cd`s
  into the release-tool checkout, so it must be handed an **absolute** path.
- **Test the installer silently**, no clicking: `Setup.exe /S`, then
  `Uninstall.exe /S`. Check the install dir contents, the Start Menu shortcut, the
  `HKCU` key, that the installed app can write its database, and that a reinstall
  over a running instance succeeds.

---

# 8 Essential Additional Rules (must-have)

## 1) Use `pyproject.toml` as the single source of truth

No scattered config files. Keep tooling config in `pyproject.toml` (and commit `uv.lock`).

Recommended baseline:

* Python version pinned (e.g. `>=3.11,<3.13`)
* Dependencies managed via `uv add ...`
* Lockfile committed: `uv.lock`

---

## 2) Enforce formatting + linting + type checking in CI

Minimum toolchain:

```bash
uv add --dev ruff mypy
```

Rules:

* Ruff handles lint + formatting (replace black/isort/flake8).
* MyPy (or pyright) for typing.
* CI must run: `ruff check`, `ruff format --check`, `mypy`.

---

## 3) Require type hints on public APIs

Rule of thumb:

* All public functions/classes/methods: typed parameters + return types.
* Use `typing` well: `Sequence`, `Mapping`, `Protocol`, `TypedDict`, `Literal` when helpful.
* Avoid `Any` unless you have a boundary (I/O, third-party libs).

---

## 4) Centralize configuration with environment-driven settings

No “magic values” in code. Use a single settings module with env overrides.

```py
# app/config/settings.py
from dataclasses import dataclass
import os

@dataclass(frozen=True)
class Settings:
    env: str = os.getenv("APP_ENV", "dev")
    debug: bool = os.getenv("DEBUG", "0") == "1"
    default_lang: str = os.getenv("DEFAULT_LANG", "en")
```

Everything reads from `Settings`, not directly from `os.getenv()` scattered around.

---

## 5) Tests are mandatory, fast, and isolated

Use pytest:

```bash
uv add --dev pytest
```

Rules:

* Unit tests for core logic.
* No network in unit tests.
* Use tmp dirs / fixtures; no reliance on developer machine state.
* Run tests in CI on every push.

---

## 6) Database access uses SQLAlchemy ORM

If a database is needed, use SQLAlchemy ORM (not raw SQL or ad-hoc drivers).

---

## 7) Use `spec=` with MagicMock to catch interface mismatches

`MagicMock` without `spec` accepts **any** attribute, even non-existent ones:

```python
# BAD - No interface validation
mock = MagicMock()
mock.nonexistent_attribute = "test"  # Silently works
mock.typo_method()                   # Also works - won't catch bugs!
```

**Always use `spec=ClassName`** to validate against the real interface:

```python
# GOOD - Validates against real class
from unittest.mock import MagicMock
from mylib import EmailMessage

mock = MagicMock(spec=EmailMessage)
mock.nonexistent = "test"  # AttributeError - catches the bug!
```

### Common Pitfall: Mocking Methods vs Attributes

If the real class has a **method**, mock it as a method:

```python
# Real class has: def get_body(self) -> str
class EmailMessage:
    def get_body(self) -> str:
        return "content"

# WRONG - Creates fake attribute that doesn't exist
mock = MagicMock()
mock.body = "test"  # EmailMessage has no .body attribute!

# CORRECT - Mock the actual method
mock = MagicMock(spec=EmailMessage)
mock.get_body.return_value = "test"
```

### Quick Reference

```python
from unittest.mock import MagicMock, patch

# Mock with spec (recommended)
mock_obj = MagicMock(spec=RealClass)

# Mock method return value
mock_obj.method_name.return_value = "value"

# Mock method to raise exception
mock_obj.method_name.side_effect = ValueError("error")

# Mock property (use PropertyMock)
from unittest.mock import PropertyMock
type(mock_obj).prop_name = PropertyMock(return_value="value")

# Patch with spec
with patch("module.ClassName", spec=RealClass) as mock_cls:
    mock_cls.return_value.method.return_value = "value"
```

---

## 8) Required Batch Files

Every project must include these batch files:

* `start.bat` - In the root directory, starts the application
* `tools/run_tests.bat` - Runs the test suite

---

## Async Patterns

Use `asyncio` for I/O-bound tasks (network requests, file I/O, database queries). Avoid blocking
calls (`time.sleep`, synchronous HTTP) in async contexts — they block the entire event loop.

---

## Validation

Use Pydantic for request and data validation at API boundaries. Define models for incoming data
and let Pydantic handle type coercion and error reporting.

---

## Structured Logging

Use `structlog` or the `logging` module with JSON formatters — not `print()`. Configure a
centralized logging setup that all modules use consistently.

Route all logging through one class named **`AppLogger`** (`app_logger.py`) that wraps
`structlog`/`logging`. Feature code calls `AppLogger`, never `logging.getLogger(...)` or
`print()` directly — this gives a single enable/level toggle without touching call sites.

---

## Self-Describing Classes

Implement the common "Self-Describing Classes" rule using a Protocol/ABC or dataclass field
metadata.

### Option A: Protocol with abstract method

```python
from typing import Protocol


class Searchable(Protocol):
    def get_searchable_fields(self) -> list[str]: ...


class Customer:
    def __init__(self, name: str, email: str, phone: str) -> None:
        self.name = name
        self.email = email
        self.phone = phone

    def get_searchable_fields(self) -> list[str]:
        return [self.name, self.email, self.phone]
```

### Option B: Dataclass field metadata

```python
from dataclasses import dataclass, field, fields

SEARCHABLE = "searchable"


@dataclass
class Customer:
    name: str = field(metadata={SEARCHABLE: True})
    email: str = field(metadata={SEARCHABLE: True})
    internal_notes: str = field(default="", metadata={SEARCHABLE: False})


def get_searchable_values(obj: object) -> list[str]:
    return [getattr(obj, f.name) for f in fields(obj) if f.metadata.get(SEARCHABLE)]
```

Prefer the Protocol approach for simple cases. Use dataclass metadata when you need declarative
per-field control without writing boilerplate methods.

# Version
11

Increase this version number whenever this rule file changes.

# graphify Knowledge Graph (Optional Addon)
<!-- tailored -->

graphify turns a code folder into a queryable knowledge graph — god nodes, communities,
cross-file relationships, fan-in/fan-out. Use it to orient before grep and to spot god classes.

**This project's `<code-dir>` is `src/`.** Every build is
`/graphify src/ --directed` from the repo root, writing to the root `graphify-out/`.
Never build the repo root: a code-dir-scoped build is AST-only (free, no LLM), while a
root build sweeps in `docs/`, `README.md` and other non-code files and forces the paid
LLM pass. There is no in-tree vendored code under `src/`, so no `.graphifyignore` is needed.

---

## Using the graph

- For codebase questions, run `graphify query "<question>"` first when `graphify-out/graph.json`
  exists. `graphify path "<A>" "<B>"` for relationships; `graphify explain "<concept>"` for a
  focused node. These return a small scoped subgraph vs. reading GRAPH_REPORT.md or raw grep.
- Judge coupling by direction: high **fan-in** + low fan-out (shared base / constants / DTO) is
  healthy; high **fan-out** (>~20 outgoing deps) is god-class risk and a refactor signal.
- Read `graphify-out/GRAPH_REPORT.md` only for broad architecture review, or when
  query/path/explain do not surface enough context.

## Folder layout (know which is which)

- `graphify-out/` at the **project root** = the **live graph** (`graph.json`, `GRAPH_REPORT.md`,
  `graph.html`). The only one queries read. Keep it `directed=True`.
- `src/graphify-out/` = **AST cache only** (`cache/`). Scratch that speeds re-extraction.
  Never the live graph. Do not query it.

## Delegated checks (Codex / DeepSeek)

This project delegates the plan/DRY/convention checks to Codex (see the AI workflow rules'
"Delegation backends"). Prepend this **graphify delegate preamble** to the `<PROMPT>` before
sending it to the backend:

```
Graphify: this project has a graphify knowledge graph, built at the repo-root
`graphify-out/graph.json`. Run all graphify commands FROM THE REPO ROOT (the
graph is resolved relative to the current directory). For any codebase question,
run `graphify query "<question>"` first (also `graphify path "<A>" "<B>"`,
`graphify explain "<concept>"`) instead of raw grep.
```

Prepend only — do not otherwise change the `<PROMPT>`. The cwd line matters:
`codex exec` inherits the caller's directory, and `graphify query` reads `graphify-out/`
relative to cwd — run from a subdir and it finds nothing, silently degrading to grep.
Harmless if the graph is not built yet: `graphify query` returns nothing and the CLI falls
back to reading files.

## Refreshing after a code change

- After a feature or any code change, rebuild via the **directed skill flow**: re-run
  `/graphify src/ --directed` from the repo root, writing to the project-root `graphify-out/`.
- Do NOT use the bare `graphify update src` CLI — it has no `--directed` flag and writes a
  full UNDIRECTED graph into `src/graphify-out/` (wrong location), desyncing the live graph.
  If that stray graph appears, delete `src/graphify-out/graph.json` (keep `cache/`).
- **Rebuild at the scope the existing graph already has**, not narrower. Check it first: group
  `graphify-out/graph.json` nodes by the first path segment of their `source_file`. A graph
  built from a wider scope holds `docs/` and root `*.md` nodes — the ones that answer "how does
  X work" rather than "where is X defined" — and a narrower rebuild deletes every one of them.
  graphify's shrink guard catches that and refuses the write: re-run at the original scope,
  never force past it.
- **Confirm `.graphify_root` after every rebuild.** The scan root lives in
  `graphify-out/.graphify_root`, and EVERY `/graphify <path>` run overwrites it. One wrong-path
  invocation leaves it pointing at a subtree the graph was not built from, and a later bare
  `graphify update` rescans only that subtree and reads every file outside it as deleted. It
  cannot be committed (absolute path, and `graphify-out/` is gitignored) — the intended scan
  root is recorded in `CLAUDE.md`.
- Verify after rebuild: `graph.json` has `directed: true` and lives in root `graphify-out/`.

## Manual test bat (`tools/graphify_update.bat`)

A no-AI convenience for manually checking graphify works (`CODE_DIR=src`).
Run it from anywhere — it `pushd`es to the repo root itself.

- **Does:** (1) code-only AST refresh (`graphify update`, no LLM/API cost);
  (2) smoke-tests the live root graph — `god-nodes` + a sample `query`. Proves the interpreter
  resolves, the graph is present and directed, and queries answer.
- **Does NOT:** rebuild the live root `graphify-out/graph.json`. `graphify update` writes only
  the AST cache under `src/graphify-out/`. The authoritative **directed** rebuild is the agent
  skill flow (`/graphify src/ --directed`) — a `.bat` cannot run it.
- **When to use:** quick "is graphify still wired up?" check after cloning, a dependency change,
  or a graphify upgrade. For an actual refresh of the graph the queries read, use the skill flow.
