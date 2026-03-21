# 03-Changes Flat Migration Playbook

## Background

This playbook defines how to migrate active change docs from the legacy path-managed status structure:

```text
docs/03-changes/<module>/<status>/...
```

to the new module-flat structure:

```text
docs/03-changes/<module>/YYYY-MM-DD-topic.md
```

Under the current standard:

- path expresses document family and module only
- status lives in document metadata
- the same task doc should not move again after migration

Use this playbook when a real active or recently used change doc still lives in a legacy status directory and needs to be normalized.

## When To Use This Playbook

Use this playbook when:

- a change doc under `docs/03-changes/<module>/<status>/` is still being used
- a module doc or playbook still links to a legacy-status-path change doc
- a task is reopened and its doc should be brought into the new standard
- an agent needs to migrate a touched doc while doing related work

Do not use this playbook for:

- bulk migration of the entire `docs/03-changes/` tree in one pass
- historical cleanup of low-value archived materials
- broad redesign of task content

## Core Rule

Migrate only the documents you are actively touching or explicitly assigned to migrate.

Do not perform a repository-wide mass move unless a separate human-approved migration task exists.

## Migration Target

For each migrated task, the target file shape is:

```text
docs/03-changes/<module>/YYYY-MM-DD-topic.md
```

The target file should include metadata like:

```yaml
---
doc_type: change
module: quantaalpha
status: planned
owner: quan
created: 2026-03-21
updated: 2026-03-21
summary: one-line routing summary
---
```

Optional fields may include:

- `code_paths`
- `doc_refs`
- `validation`
- `review_required`
- `blocked_by`
- `outcome`

## Migration Decision Order

Before editing, identify:

1. target module
2. source file
3. target flat path
4. current effective status
5. documents that link to the source file

If any of these is unclear, stop and clarify before moving the file.

## Step-By-Step Procedure

### 1. Confirm The Source Doc Should Really Be Migrated

A legacy doc is a migration candidate if any of these is true:

- it is referenced by a module doc, ADR, playbook, or active task
- it is still used as task context by humans or agents
- its task is not purely historical

If the doc is low-value history only, prefer leaving it in place temporarily rather than creating churn.

### 2. Determine The Canonical Module

Map the doc into one stable module bucket:

- `app4`
- `quantaalpha`
- `backtest`
- `common`

Do not invent a status-driven or one-off bucket during migration.

### 3. Determine The Canonical Target Name

Use the existing file name if it already matches:

```text
YYYY-MM-DD-topic.md
```

Only rename when the existing name is clearly non-standard, ambiguous, or collides with another migrated file.

### 4. Map Legacy Status To New Status

Use this mapping:

| Legacy status | New status | Notes |
|---|---|---|
| `draft` | `draft` | keep exploratory state |
| `planned` | `planned` | approved, not started |
| `in_progress` | `doing` | active execution |
| `blocked` | `doing` | also add `blocked_by` when possible |
| `implemented` | `done` | only if implementation is already real |
| `tested` | `done` | add validation evidence if available |
| `accepted` | `done` | preserve closure details in metadata or body |
| `archived` | `archived` | history only |

Do not create new directory levels to preserve old status granularity.

If finer closure detail matters, keep it inside metadata or body text, for example:

```yaml
status: done
outcome: accepted
```

### 5. Normalize Metadata

Add or normalize these fields:

- `doc_type: change`
- `module`
- `status`
- `owner` if known
- `created` if known
- `updated`
- `summary`

Preserve useful legacy fields if they still add value, but do not let them replace the new standard fields.

### 6. Keep The Task Content, Do Not Rewrite It Unnecessarily

The migration goal is structural normalization, not editorial improvement.

Keep:

- background
- scope
- implementation notes
- validation notes
- closure evidence

Only change the body when:

- wording still depends on old path semantics
- the doc clearly contradicts current governance rules
- the doc needs a minimal note explaining the migration

### 7. Move The File Once

Move the source doc to:

```text
docs/03-changes/<module>/YYYY-MM-DD-topic.md
```

After that:

- future status changes happen in metadata only
- do not move the file again just because `status` changes

### 8. Update Direct References

Update any high-value direct references that still point to the old path, especially in:

- `docs/02-modules/`
- `docs/04-decisions/`
- `docs/05-playbooks/`
- active docs under `docs/03-changes/`

Do not attempt to clean every historical draft or report in the same pass unless explicitly assigned.

### 9. Validate The Migrated Doc

At minimum, run:

```bash
python3 scripts/doc_index.py validate
```

Also use targeted inspection when needed:

```bash
python3 scripts/doc_index.py list --type change --module quantaalpha --status planned --json
```

Validation should confirm:

- the migrated file is now discovered at the flat path
- the new metadata is parseable
- the new status is recognized
- the file no longer depends on legacy path semantics

## What Counts As Complete

A migration is complete only when all of these are true:

1. the doc exists at the flat module path
2. the doc has standard change-doc metadata
3. the effective status is represented in metadata
4. high-value references to the old path are updated
5. `scripts/doc_index.py validate` does not report a migration-created structural issue

## What Does Not Count As Complete

- moving the file without adding metadata
- changing the path but keeping old status semantics only in prose
- updating metadata but leaving the canonical path unchanged
- bulk-editing historical references with no clear task boundary
- reporting migration complete without validation

## Common Mistakes

### 1. Recreating Status Directories In Another Form

Bad examples:

- `docs/03-changes/quantaalpha/status-planned/...`
- `docs/03-changes/quantaalpha/planned-2026-03/...`

The new path model is module-flat. Do not rebuild path-based status indirectly.

### 2. Keeping Two Live Copies Of The Same Task

Do not leave:

- one file in the old status directory
- one file in the new flat directory

unless the old file is explicitly turned into a redirect note during a controlled transition.

### 3. Treating Legacy `tested` Or `accepted` As A Required Path Concept

Those old states can be preserved as metadata detail, but they do not justify keeping the file in a status directory.

### 4. Over-Migrating

If the task is only to normalize one active doc, do not turn it into a full-tree cleanup project.

### 5. Losing Validation Evidence

When migrating a `tested` or `accepted` legacy doc, preserve useful validation commands and closure notes.

Do not simplify the doc so much that the task record loses audit value.

## Suggested Minimal Report

For each migrated doc, report:

1. source path
2. target path
3. old effective status
4. new metadata status
5. references updated
6. validation command run

## Escalation Rule

Stop for human review if the migration would require:

- merging two competing task docs
- deleting a doc with unclear historical value
- changing module ownership of a contentious doc
- rewriting large sections of task content to resolve contradictions

## Relationship To Governance

This playbook implements the standards defined by:

- `docs/00-governance/agent.md`
- `docs/00-governance/rules.md`
- `docs/00-governance/doc-standards.md`
- `docs/00-governance/doc-workflows.md`
- `docs/00-governance/doc-validation.md`

If this playbook conflicts with governance docs, follow governance docs.
