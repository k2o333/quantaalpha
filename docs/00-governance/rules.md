# aspipe_v4 Rules

## Purpose

This file defines mandatory engineering rules for all human and AI contributors.

Use `docs/00-governance/agent.md` as the repository entrypoint, then return here for constraints.

## Scope

These rules apply to:
- code changes
- config changes
- tests and validation
- documentation updates
- branch and review workflow

## Source Of Truth Priority

Use this priority order when documents disagree:
1. `docs/00-governance/agent.md`
2. `docs/00-governance/rules.md`
3. `docs/02-modules/*.md`
4. `docs/07-technical/*.md`
5. accepted change docs under `docs/03-changes/`
6. drafts and exploratory notes under `docs/drafts/`
7. current code, when docs are stale and must be corrected

## Required Behavior

- read `agent.md` before starting work
- read the relevant module doc before changing module behavior
- identify validation scope before editing
- for high-risk integration work, identify the downstream consumer, write path, and failure surface before editing
- keep changes atomic and scoped to the task
- update docs when behavior or contract actually changes
- stop for human review on high-risk changes

## Forbidden Behavior

- do not treat `docs/drafts/` as current truth
- do not edit code before locating the correct module context
- do not widen scope into unrelated modules
- do not treat passing tests as automatic approval
- do not report tracking, logging, summaries, or audit records as a completed behavior change unless they are actually consumed by control flow
- do not treat an integration as complete after checking only the input side; output contracts must also be verified
- do not merge uncertain or experimental work into `main` by default
- do not leave disposable artifacts in source directories

## Branch Policy

### Can work on `main`

These are usually acceptable directly on `main` when the change is clear and low risk:
- docs-only fixes
- typo fixes
- logging-only adjustments
- tiny low-risk bug fixes with obvious scope

### Must use a branch

These require a dedicated branch:
- new interface configs
- pagination changes
- storage or write-path changes
- dedup changes
- schema changes
- concurrency changes
- uncertain multi-step work
- cross-module changes

See `docs/00-governance/development-workflow.md` for the fuller workflow.

## Validation Policy

### Low Risk

Examples:
- docs
- comments
- logging-only changes

Expectation:
- sanity check

### Medium Risk

Examples:
- targeted bug fixes
- local config adjustments
- narrow behavior changes

Expectation:
- targeted tests or smoke commands
- validation claims should include the exact command, working directory, and interpreter when reproducibility is non-obvious

### High Risk

Examples:
- pagination
- storage and write path
- dedup
- schema semantics
- update semantics
- concurrency or worker model

Expectation:
- strong validation
- verify both input and output contracts at system seams
- verify script or scheduler defaults against the real write path or source-of-truth path
- make test-pass claims reproducible with the exact command and working directory
- explicit rollback thinking
- human review before acceptance

## Human Review Required

Stop and wait for human review when a task changes:
- storage model or write semantics
- schema meaning or key fields
- concurrency model
- cross-module behavior
- core update semantics
- large refactors with unclear rollback

## Documentation Update Rules

Update governance, module, or technical docs when one of these changes:
- behavior
- public contract
- config schema
- execution flow
- operational expectations

Record task-specific implementation context in change docs first, then update higher-level docs if the current truth changed.

## Temporary Files

Put temporary artifacts under `.tmp/`.

Examples:
- debug output
- temporary test data
- one-off scripts
- experiment notes that are not formal docs

## Non-Default Edit Targets

Do not modify these unless the task explicitly requires it:
- `third_party/vnpy/`
- `third_party/glue/`
