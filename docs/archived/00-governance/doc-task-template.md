# Documentation Change Task Template

## Purpose

Use this template when you need an AI agent to modify governance or documentation files in a controlled way.

This template is especially useful for:
- `docs/00-governance/agent.md`
- `docs/00-governance/rules.md`
- `docs/00-governance/doc-rules.md`
- `docs/00-governance/doc-workflows.md`
- `docs/00-governance/development-workflow.md`
- other short, high-authority docs where over-editing is risky

## When To Use This Template

Use this template when:
- the task is about documentation, not code behavior
- the target docs define routing, rules, workflow, or current truth
- a normal agent might confuse "added wording" with "finished cleanup"
- review quality depends on checking exact file shape, not only intent

Do not use this template when:
- the task is still broad exploration
- you do not yet know the target files
- the work is mainly code or config implementation

In those cases, start with a draft or a change doc first.

## How To Use

Copy the sections below into a draft or change doc and fill in the placeholders.

If the task is governance-heavy, keep the instructions concrete and section-scoped.

## Template

### Background

Describe the current problem in 2-5 sentences.

Include:
- which docs are currently misaligned
- why the issue matters
- why this is a documentation task rather than a code task

### Goal

State the intended result in one short paragraph.

Prefer:
- "align `agent.md` routing with the module-flat change-doc model"
- "remove duplicated rule lists from `development-workflow.md`"

Avoid:
- "improve docs"
- "make things clearer"

### Non-Goals

List what must not happen.

Typical examples:
- do not redesign the whole documentation system
- do not edit module docs unless this task explicitly requires it
- do not create new governance files unless named below
- do not treat drafts as source of truth

### Target Scope

Fill in:
- task type
- target doc families
- primary target files
- allowed output files
- files or doc families that must not be edited

For governance-doc tasks, always name exact files.

### Draft Placement

If the task itself is being written as a draft before implementation, decide the placement explicitly.

Use:
- `docs/03-changes/<module>/YYYY-MM-DD-topic.md` when the task is already scoped to one module or one known bucket such as `common/`
- `docs/drafts/` when the work is still broad exploration, comparison, or not yet clearly attached to a module

Do not leave placement implicit.

If you expect a normal agent to continue the work later, state the intended draft location directly in the task.

### Required Read Order

List the files to read before editing.

Recommended pattern:
1. `docs/00-governance/agent.md`
2. `docs/00-governance/rules.md`
3. relevant ADR or module doc
4. target governance docs
5. supporting standards doc if needed

If reading order matters, say so explicitly.

### Pre-Edit Checklist

Require the agent to identify:
- target files
- exact sections to change
- validation method
- whether human review is required under `rules.md`

### Execution Rules

Write short, hard rules here.

Good examples:
- keep `agent.md` short
- do not add new subsections unless this task explicitly says so
- replace repeated rule lists instead of prefixing them with a reference
- do not mark a file as changed if it was only reviewed
- if unresolved duplication remains, report partial completion

### Exact Edit Plan

Break the task down by file.

For each file, specify:
- which sections may be edited
- what must change
- what must not be added
- what the final section should look like

Use shape constraints when needed.

Examples:
- "change only `## Fast Routing` and `## Do Not Assume`"
- "section 4.2 may contain one reference sentence plus at most two project-specific bullets"
- "do not add a new explanatory subsection under `## Fast Routing`"

### Acceptance Checks

Use file-based checks, not vague quality statements.

Good examples:
- `agent.md` routes change-doc lookup to `docs/03-changes/<module>/`
- no governance file still defines status subdirectories as the target standard
- metadata examples use the standard status vocabulary
- section `4.2` has at most two bullets

Avoid:
- "docs are clearer"
- "workflow is improved"

### Validation

State how the agent should verify the result.

Typical checks:
- compare final file contents against `rules.md`
- compare routing against actual directory layout
- inspect whether repeated rule lists were deleted or merely prefixed
- count bullets in constrained sections

### Required Review Step

Require a review pass that checks final file contents directly.

Reviewer instructions should verify:
- only allowed files were edited
- hard acceptance checks actually pass
- no known weak spot was over-claimed as complete

### Report Requirements

Require these sections:
- `Status`
- `Files Changed`
- `Files Reviewed But Not Changed`
- `What Was Actually Changed`
- `Acceptance Checks`
- `Review Findings`
- `Residual Gaps`

Require these report rules:
- do not over-claim completion
- use `partial` or `not complete` when a check is not fully satisfied
- do not write `Residual Gaps: None` unless weak spots were explicitly checked

### Draft Lifecycle After Execution

If the task started from a draft, state what must happen to that draft after real work begins or finishes.

Recommended rule:
- if implementation actually starts, do not leave the task only in `draft/` without explanation

Preferred outcomes:
- create or move the document to `docs/03-changes/<module>/YYYY-MM-DD-topic.md` if it becomes a real tracked task
- set `status: planned` if approved but not started
- set `status: doing` if active work has started
- set `status: done` or `status: archived` when the task is truly closed

If you intentionally leave the document in `docs/drafts/`, require the report to say why.

Useful hard rule:
- if a task was actually executed, do not leave the file in `docs/drafts/` with `status: draft` unless the report explicitly justifies that exception

### Closure Standard

Define success as concrete conditions.

Example:
- edits stayed within allowed files
- hard acceptance checks pass
- reviewer did not find unresolved contradictions reported as finished
- report accurately distinguishes changed files from reviewed-only files

## Governance-Doc Starter Pattern

Use this pattern when the task specifically targets governance docs such as `agent.md`, `rules.md`, `doc-rules.md`, or `development-workflow.md`.

### Recommended Defaults

- keep entrypoint docs short
- prefer routing-table edits over adding prose
- remove repeated rule lists instead of restating them
- push durable rules back to `rules.md`
- keep workflow docs process-first
- treat reports as audit records, not victory messages

### Known Weak Spots

Normal agents often fail in these ways:
- adding a new mini-manual section to a short entrypoint
- leaving the old rule list in place and adding a `follow rules.md` sentence above it
- reporting `pass` when one structural section still fails
- treating a review summary as proof instead of checking the actual file

When these risks apply, write explicit "not allowed" lines and shape constraints.
