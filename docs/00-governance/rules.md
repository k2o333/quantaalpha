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

Use this order when documents disagree:
1. `docs/00-governance/agent.md`
2. `docs/00-governance/rules.md`
3. `docs/02-modules/*.md`
4. `docs/04-decisions/*.md`
5. `docs/05-playbooks/*.md`
6. `docs/06-references/*.md`
7. `docs/07-technical/*.md`
8. `docs/03-changes/<module>/`
9. `docs/drafts/`
10. current code, when docs are stale and must be corrected

## Required Behavior

- read `agent.md` before starting work
- read the relevant module doc before changing module behavior
- identify validation scope before editing
- for high-risk integration work, identify the downstream consumer, write path, and failure surface before editing
- keep changes atomic and scoped to the task
- update docs when behavior or contract actually changes
- use module-flat change docs under `docs/03-changes/<module>/`
- store change-doc status in document metadata, not in directory names
- use the documentation validation rules in `docs/00-governance/doc-validation.md`
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
- do not create new status subdirectories under `docs/03-changes/`
- do not move change docs between directories to express status updates

## Branch Policy

### Can Work On `main`

These are usually acceptable directly on `main` when the change is clear and low risk:
- docs-only fixes
- typo fixes
- logging-only adjustments
- tiny low-risk bug fixes with obvious scope

### Must Use A Branch

These require a dedicated branch:
- new interface configs
- pagination changes
- storage or write-path changes
- dedup changes
- schema changes
- concurrency changes
- uncertain multi-step work
- cross-module changes

See `docs/00-governance/development-workflow.md` for fuller workflow details.

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
- repository-wide governance rules

## Documentation Update Rules

Update governance, module, or technical docs when one of these changes:
- behavior
- public contract
- config schema
- execution flow
- operational expectations

Record task-specific implementation context in a module-flat change doc first, then update higher-level docs if current truth changed.

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

## Completion Contract

Do not report work as complete unless you can state:
1. target module
2. target files
3. truth docs consulted
4. validation command used
5. whether human review is required
