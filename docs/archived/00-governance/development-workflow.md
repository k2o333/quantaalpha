# aspipe_v4 Development Workflow

Status: active
Owner: quan
Created: 2026-03-15
Updated: 2026-03-21
Outcome: accepted
Related-to: `./rules.md`
Related-to: `./doc-rules.md`

## Purpose

This document defines the practical development workflow for `aspipe_v4`.

It is designed for:
- single-maintainer development
- incremental iteration
- atomic commits
- AI-assisted implementation under explicit constraints

This file focuses on:
- branch usage
- implementation flow
- validation expectations
- handoff and review points

Stable repository-wide rules live in `docs/00-governance/rules.md` and are not duplicated here.

## Working Model

Use the model:

`main` stays usable, uncertain work uses a branch.

Principles:
1. `main` should remain in a usable state.
2. uncertain or experimental changes should use a branch.
3. every meaningful change should be packaged as an atomic commit.
4. AI tools must not act before reading the relevant governance and module context.
5. human maintainers retain final merge authority.
6. documentation should reduce execution ambiguity, not create noise.

## Branch Strategy

### Working On `main`

Use `main` only for low-risk, well-bounded changes such as:
- docs-only fixes
- typo fixes
- tiny obvious bug fixes
- logging-only adjustments

### Using A Branch

Use a branch when:
- implementation is uncertain
- multiple iterations are expected
- rollback risk is non-trivial
- cross-module changes are involved
- the task is explicitly marked high-risk in `rules.md`

Suggested names:
- `feature/<topic>`
- `fix/<topic>`
- `refactor/<topic>`
- `experiment/<topic>`

## Task Execution Flow

Recommended execution flow:
1. read `agent.md`, `rules.md`, and the relevant module doc
2. identify whether current truth or task context is needed
3. if task context is needed, use a module-flat change doc under `docs/03-changes/<module>/`
4. identify target files, validation, and review boundary
5. implement the scoped change
6. run the required validation
7. update the change doc if the task is meaningful enough to track
8. update higher-truth docs only if current truth changed
9. stop for human review when required

## Task State Model

The default task lifecycle is:

`draft -> planned -> doing -> done -> archived`

Task state should be expressed in document metadata, commit history, or branch context.

Do not express task state by creating or relying on status directories under `docs/03-changes/`.

## Validation Practice

Validation strategy by risk level is defined in `docs/00-governance/rules.md`.

This workflow adds these operating rules:
- keep validation commands reproducible
- include working directory and interpreter when that matters
- do not claim success from partial or non-reproducible evidence
- for seam-sensitive changes, verify both input and output contracts
- for script, scheduler, or path-sensitive tasks, verify default paths against real write paths

## AI And Human Boundary

AI can:
- read docs and code
- propose and implement scoped changes
- run local validation
- update change docs and supporting docs within task scope
- summarize risks and remaining gaps

AI must stop for human review when the task crosses the boundary defined in `rules.md`.

## Documentation Expectations

After meaningful implementation work:
1. keep or create a change doc trail
2. update the module doc if current behavior changed
3. update an ADR, playbook, or reference doc only if the knowledge became durable

Use `docs/00-governance/doc-rules.md` for routing and `docs/00-governance/doc-workflows.md` for promotion logic.

## Temporary Files

Place temporary files under `.tmp/`.

Move durable content into formal docs when it becomes useful.

## Conflict Rule

If this document conflicts with `rules.md`, follow `rules.md`.
