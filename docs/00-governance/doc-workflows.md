# Documentation Workflows

## Purpose

This file defines low-entropy documentation flows so an agent can follow the correct promotion path without reading the whole documentation system.

## Core Lifecycle

The default task lifecycle is:

```text
draft -> planned -> doing -> done -> archived
```

This lifecycle is represented by document metadata, not by moving files between status directories.

## Draft Workflows

### When To Create A Draft

Create a draft when work is still exploratory:
- comparing approaches
- writing design options
- collecting temporary analysis
- recording uncertain implementation ideas

### What Belongs In A Draft

- goals or questions
- options and tradeoffs
- temporary findings
- open risks
- tentative recommendations

### What Does Not Belong In A Draft

- accepted implementation truth
- final acceptance criteria after implementation is settled
- current module-state description

### Draft Outcomes

A draft should end in one of these states:
1. promoted into a change doc
2. promoted into another formal doc
3. archived
4. deleted if low-value and non-reusable

## Lifecycle Signals

Use these signals together to decide what a document currently is:
- document family
- document path
- `doc_type`
- `status`
- whether the content has been promoted into a higher-truth doc

### Typical Interpretation

- `docs/drafts/` + `status: draft`:
  broad exploration, options, or not-yet-approved thinking
- `docs/03-changes/<module>/` + `status: planned`:
  concrete implementation task, approved to do, not yet started
- `docs/03-changes/<module>/` + `status: doing`:
  concrete implementation task, currently active
- `docs/03-changes/<module>/` + `status: done`:
  completed task record with validation evidence
- `docs/03-changes/<module>/` + `status: archived`:
  historical task record, not active work
- `docs/02-modules/` + `status: active`:
  current module truth
- any formal doc + `status: superseded`:
  replaced by a newer truth doc

### Important Rule

A document is not current truth just because it is detailed or complete.

Current truth comes from:
- module docs
- active governance docs
- valid ADRs
- other formal truth-layer docs

Detailed drafts and completed change docs are still process material unless their knowledge has been promoted.

## Draft To Change

Use this path when exploratory work becomes a concrete implementation task.

### Promote A Draft To A Change Doc When

- the task has a clear implementation target
- a real code, config, or formal-doc change is planned or completed
- validation scope can be named
- the work needs traceability

### Promotion Rule

If a document already describes:
- a scoped implementation target
- dependencies
- validation expectations
- concrete code-facing or doc-facing work

then it should usually be managed as a change doc even if implementation has not started.

Under the module-flat model:
- create or move it to `docs/03-changes/<module>/YYYY-MM-DD-topic.md`
- set `doc_type: change`
- set `status` to `planned` or `doing`

### When Promoting, Keep In The Change Doc

- background
- goal
- non-goals
- risk points
- validation plan
- implementation notes

### When Promoting, Leave Behind In The Draft Only If Still Useful

- rejected alternatives
- broader exploration not needed for the implementation record
- speculative options for future work

## Change Execution

Once a change doc becomes active, keep the path stable and update only metadata and content.

During execution, the owner should maintain:
- `updated`
- `status`
- target files or code paths
- validation notes
- remaining risks

## Change Closure

This is the default closure order after meaningful implementation work:

1. update the change doc with the actual result
2. attach validation evidence
3. decide whether current module truth changed
4. decide whether a long-term decision changed
5. decide whether lessons became reusable
6. archive only if the doc should remain as history only

### A Change Doc Should Answer

- what changed
- why it changed
- what was validated
- what remains risky
- whether higher-level docs also changed

### If Code And Docs Disagree At Closure Time

Use this order:
1. verify the real behavior from code and validation evidence
2. update the change doc to match what was actually implemented
3. decide whether current truth changed
4. if current truth changed, update the module doc or ADR

Do not force code to match an old draft if the validated implementation intentionally evolved.

## Change To Module

Promote change-doc knowledge into a module doc only when current truth changed.

### Update The Module Doc If One Of These Changed

- module responsibility
- external interface
- key data structure or schema assumption
- dependency relationship
- module boundary
- operational risk model
- test entrypoints

### Do Not Update The Module Doc For

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

### I Have An Unfinished Idea

Use a draft.

### I Have A Concrete Implementation Task

Use or update a module-flat change doc.

### I Changed The Current Behavior Of A Module

Update the module doc.

### I Changed A Durable Project-Level Decision

Create or update an ADR.

### I Found A Reusable Engineering Pattern

Create or update a playbook.

### I Learned A Stable Way This Repo Uses A Dependency

Create or update a reference doc.
