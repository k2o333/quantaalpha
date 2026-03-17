# Agent Delivery Audit Playbook

## Background

This playbook captures a recurring delivery pattern:

- the agent can read the task docs
- the agent can produce plausible code and a confident completion report
- tests may look numerous and mostly pass
- but the real delivery is still incomplete because the end-to-end path is not actually closed

The practical problem is not "the agent is bad at coding" in a simple sense.
The problem is that a medium-level agent is often good enough to satisfy visible checklists while still missing the real system contract.

This playbook is for reducing that gap.

## When To Use This Playbook

Use this playbook when:

- a task introduces a new mode, new CLI flag, or new execution path
- a task claims "already tested" and "report completed"
- the work touches write paths, state transitions, or scheduling
- an agent tends to add tracking, logs, or summaries without wiring them into control flow
- tests exist, but you are not sure they validate the real behavior

Boundary:
- this playbook is for code delivery, integration seams, validation claims, and operational closure
- if the task is mainly about governance/doc structure hardening, use `normal-agent-todo-hardening-lessons.md`

## Core Lesson

Do not evaluate this kind of delivery by:

- amount of code changed
- number of tests added
- confidence of the completion report

Evaluate it by closure:

- does the new path actually connect to the existing system?
- does the new output format match the downstream consumer?
- does the scheduler point at the real source of truth?
- does a failure surface as failure to the caller?
- do the tests falsify the dangerous cases, or only restate the implementation?

If the answer to any of these is unclear, the task is not complete.

## Typical Failure Modes

### 1. New behavior exists in local code only

Typical pattern:

- a new mode or flag is added
- helper functions are written
- docs and reports say the capability exists
- but the path is incompatible with the downstream loader, runner, or config format

Required countermeasure:

- for every new mode, verify one real execution path through the downstream consumer
- do not accept "unit-tested helper" as proof of integration

### 2. Tracking is mistaken for control flow

Typical pattern:

- the agent adds status tracking, summaries, counters, or audit records
- logs clearly describe the intended behavior
- but the workflow still executes the old full path

Required countermeasure:

- verify where the tracked result is consumed
- ask: "what line changes the next step's actual input set?"
- if nothing consumes it, the feature is observability, not behavior

### 3. Script defaults drift from runtime truth

Typical pattern:

- a script is added for scheduling or operations
- the script looks polished
- but its default paths, module imports, or config assumptions differ from the actual runtime writer

Required countermeasure:

- compare script defaults with the real write path and runtime entrypoint
- do not trust comments or variable names
- validate against the code that produces the data

### 4. Failures are reported inside a JSON result but not surfaced operationally

Typical pattern:

- per-item exceptions are caught
- the command returns a structured report with `failed > 0`
- but the process exits successfully, so the scheduler sees green

Required countermeasure:

- define which failures are informational and which must fail the command
- check the exit semantics, not only the returned dict

### 5. Tests mirror the implementation instead of challenging it

Typical pattern:

- tests manually reconstruct the same report shape as production code
- tests mock the important boundary away
- tests prove that the agent can keep its own story internally consistent

Required countermeasure:

- require at least one test per risky feature that exercises the public boundary
- examples: real CLI call, real parser, real file format, real scheduler invocation

### 5A. Test pass claims are not reproducible

Typical pattern:

- the agent reports `all tests passed`
- but the claimed command is not shown exactly, or only works from one directory
- tests rely on hidden import state, local stubs, or unspoken environment assumptions
- a reviewer reruns the tests in the obvious project location and gets collection errors

Required countermeasure:

- require the exact test command, working directory, and interpreter path in the report
- rerun the claimed command from a clean, obvious entrypoint before accepting the result
- treat collection/import errors as a failed validation claim, not a minor documentation issue
- do not accept "tests passed" if the result depends on hidden preload order or accidental module state

### 6. IDs and contracts diverge in adjacent modules

Typical pattern:

- one module generates full IDs
- another truncates them
- logging, persistence, and retry logic all look individually reasonable
- but cross-module correlation becomes unreliable

Required countermeasure:

- treat identifiers and file formats as contracts
- require one source of truth or one shared helper for contract generation

### 7. Input contract is fixed, output contract is still wrong

Typical pattern:

- the agent notices an input-format mismatch and fixes it
- the new path now reaches the downstream component
- but the code still reads the downstream result using the wrong field names or nesting
- the report says the integration is complete because the first contract break was fixed

Required countermeasure:

- verify both directions of the seam:
- can the downstream consumer read the produced input?
- can the caller correctly consume the downstream output?
- when integrating with an existing runner, parser, or service, inspect the real returned structure instead of inferring it
- require at least one boundary test that validates the actual returned payload shape

## Audit Procedure

For tasks of this type, use this review order.

### 1. Read the governing docs first

Minimum read order:

1. `docs/00-governance/agent.md`
2. `docs/00-governance/rules.md`
3. relevant module doc under `docs/02-modules/`
4. the accepted change doc under `docs/03-changes/...`
5. the code

This prevents the review from being anchored on the completion report.

### 2. Translate the task into contracts

Before reading diffs, write down:

- the new public behavior
- the downstream consumer
- the write target
- the failure surface
- the minimal validation that would disprove the claim

Example questions:

- What consumes this new JSON?
- What file does the script actually operate on?
- What makes the command fail from the scheduler's perspective?
- What exact line uses the "retry only failed items" result?

### 3. Review the code by seam, not by file

Do not review in "diff order".
Review in dependency order:

1. entrypoint
2. transformation/output format
3. downstream consumer
4. persistence
5. operational wrapper
6. tests

This is the fastest way to catch fake closure.

### 4. Run one disproving check per risky claim

For each major claim, run one small check that could prove it false.

Examples:

- if a new mode writes a temp JSON, feed it to the real parser
- if a script claims to summarize the factor library, compare its path with the real writer
- if a command claims to fail safely, trigger a controlled failure and inspect exit behavior
- if a test claim says `N passed`, rerun the exact command from the claimed working directory
- if a runner integration was changed, inspect one real returned payload and compare field paths

Do not stop at "tests pass".

## Task-Writing Hardening Rules

If you expect agents of this level in the future, strengthen task docs with these rules.

For document-heavy task hardening patterns such as section-shape constraints, edit-surface limits, and file-based reviewer checks, see `normal-agent-todo-hardening-lessons.md`.

### 1. Define the downstream contract explicitly

Instead of:

- "add real backtest support"

Write:

- "the temp factor file must be readable by `quantaalpha.backtest.factor_loader.FactorLoader._parse_factor_json`"

This removes room for a plausible but incompatible local format.

### 2. Force consumption checks

Instead of:

- "track failed factors for the next debug round"

Write:

- "the next round's actual task list must be derived from `failed_factor_ids`; add one assertion proving successful factors are not passed to coder/backtest again"

This blocks logging-only implementations.

### 3. Pin operational truth

For scripts, always specify:

- source data path
- owning writer path
- runtime module entrypoint
- required non-zero exit conditions

Do not allow a script task to be accepted without path alignment.

### 4. Separate report fields from success semantics

A structured report is not enough.
Task docs should say:

- when the command must return non-zero
- when partial failure is acceptable
- what the scheduler must treat as failed

### 5. Require one real boundary test for each risky feature

For medium/high-risk tasks, require at least one of:

- real CLI invocation
- real parser invocation
- real file round-trip
- real script smoke test
- real exit-code assertion
- real payload-shape assertion against an existing downstream result

Without this, tests often become self-confirming.

### 6. Promote seam-specific weak spots into acceptance criteria

If agents repeatedly fail at the same integration seam, write that seam directly into the task.

Examples:

- "do not invent a new JSON shape"
- "do not only log retry candidates; they must change the next round input"
- "script default library path must equal the runtime write path"

## Review Checklist

Use this checklist before accepting delivery:

- Does the new entrypoint call the real downstream consumer?
- Does the produced file format match the existing parser exactly?
- Does the caller also consume the downstream output using the real returned structure?
- Is the produced identifier format consistent with persistence and tracking?
- Does a failed execution become operational failure, not just a field in a dict?
- Does the wrapper script point at the same file the runtime writes?
- Does any new tracking state actually alter behavior?
- Do tests hit the public seam, not only mocked internals?
- Can the claimed test command be rerun as written, from the stated directory, without hidden import state?
- Is the completion report internally consistent about totals and validation?

If any answer is "no" or "unclear", the task should be graded as partial.

## Scoring Guidance

When scoring an iteration delivered by a medium-level agent, use this bias:

- 85-100: end-to-end path closed, operational semantics correct, tests challenge real seams
- 70-84: most code is solid, but one important seam or operational behavior is still soft
- 50-69: visible progress exists, but at least one key promised capability is not actually delivered
- below 50: major claims are unsupported, incompatible, or mostly self-reported

This prevents "large diff + many tests + confident report" from being over-scored.

## Closure Standard

A task is complete only if all three are true:

1. the implementation is locally coherent
2. the downstream integration is real
3. the operational failure semantics are correct

If only the first item is true, the task is still in the "looks done" state, not the "done" state.
