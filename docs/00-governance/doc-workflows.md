# Documentation Workflows

## Purpose

This file defines the working flows for documentation tasks so an agent can follow the correct promotion path without reading the entire documentation system.

## Draft Workflows

### When to create a draft

Create a draft when work is still exploratory:
- comparing approaches
- writing design options
- collecting temporary analysis
- recording uncertain implementation ideas

### What belongs in a draft

- goals or questions
- options and tradeoffs
- temporary findings
- open risks
- tentative recommendations

For task-oriented drafts, also follow the minimum content expectations in `docs/00-governance/doc-standards.md#draft-docs`.

### What does not belong in a draft

- accepted implementation truth
- final acceptance criteria after implementation is settled
- module current-state description

### Draft outcomes

A draft should end in one of these states:
1. promoted into a change doc
2. promoted into another formal doc
3. archived
4. deleted if low-value and non-reusable

## Lifecycle Signals

Use these signals together to decide what a document currently is:
- document path
- document type
- status header
- whether the content has been promoted into a higher-truth doc

### Typical interpretation

- `docs/drafts/` + `draft`:
  broad exploration, options, or not-yet-module-scoped thinking
- `docs/03-changes/<module>/draft/` + `draft`:
  module-scoped task exploration that is not yet approved as a planned task
- `docs/03-changes/<module>/planned/` + `planned`:
  concrete implementation task, approved to do, but not yet started
- `docs/03-changes/<module>/in_progress/` + `in_progress`:
  a concrete implementation task, not yet fully closed
- `docs/03-changes/<module>/blocked/` + `blocked`:
  a concrete implementation task that cannot continue for now
- `docs/03-changes/<module>/implemented/` + `implemented`:
  implementation landed, but closure is not complete
- `docs/03-changes/<module>/tested/` + `tested`:
  validation is complete and task is near closure
- `docs/03-changes/<module>/accepted/` + `accepted`:
  implemented task record with closure evidence
- `docs/03-changes/<module>/archived/` + `archived` or `superseded`:
  historical task record, not current active work
- `docs/02-modules/` + `active`:
  current module truth
- any formal doc + `archived` or `superseded`:
  history only, not current truth

### Important rule

A document is not treated as current truth just because it is detailed or complete.

Current truth comes from:
- module docs
- active governance docs
- valid ADRs
- other formal truth-layer docs

Detailed drafts and completed change docs are still process material unless their knowledge has been promoted.

## Draft To Change

Use this path when exploratory work becomes a concrete implementation task.

### Promote a draft to a change doc when

- the task has a clear implementation target
- a real code/config change is planned or completed
- validation scope can be named
- the work needs traceability

### Important clarification

If a document already describes:
- a scoped implementation target
- dependencies
- validation expectations
- concrete code-facing work

then it should usually be managed as a change doc even if implementation has not started yet.

In that case:
- if it is approved but not started, move it under `docs/03-changes/<module>/planned/`
- if work has started, move it under the matching lifecycle directory
- set status to match the lifecycle directory
- keep unfinished design-only material in drafts if still useful

### When promoting, keep in the change doc

- background
- goal
- non-goals
- risk points
- validation plan
- implementation notes

### When promoting, leave behind in the draft only if still useful

- rejected alternatives
- broader exploration not needed for the implementation record
- speculative options for future work

## Change Closure

This is the default closure order after meaningful implementation work:

1. update the change doc with final result
2. attach validation evidence
3. decide whether current module truth changed
4. decide whether a long-term decision changed
5. decide whether lessons became reusable
6. archive or leave supporting draft material as reference

### A change doc should answer

- what changed
- why it changed
- what was validated
- what remains risky
- whether higher-level docs also changed

### If code and docs disagree at closure time

Use this order:
1. verify the real behavior from code and validation evidence
2. update the change doc to match what was actually implemented
3. decide whether current truth changed
4. if current truth changed, update the module doc or ADR

Do not force code to match an old draft if the validated implementation intentionally evolved.

## Change To Module

Promote change-doc knowledge into a module doc only when current truth changed.

### Update the module doc if one of these changed

- module responsibility
- external interface
- key data structure or schema assumption
- dependency relationship
- module boundary
- operational risk model
- test entry points

### Do not update the module doc for

- one-off debugging notes
- local implementation history
- rejected options
- narrow task history that does not change current truth

## Promotion Targets

When a finished task produces knowledge beyond one change doc, route it like this:

- still task-local: keep it in the change doc
- reusable across similar tasks: promote to a playbook
- long-term architecture or policy: promote to an ADR
- repeated dependency-specific usage knowledge: promote to a reference doc
- current behavior of one module: promote to a module doc

## Documentation Decision Shortcuts

### I have an unfinished idea

Use a draft.

### I have a concrete implementation task

Use or update a change doc.

### I changed the current behavior of a module

Update the module doc.

### I changed a durable project-level decision

Create or update an ADR.

### I found a reusable engineering pattern

Create or update a playbook.

### I learned a stable way this repo uses a dependency

Create or update a reference doc.
