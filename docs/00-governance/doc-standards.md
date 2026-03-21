# Documentation Standards

## Purpose

This file defines stable documentation standards: document types, placement, naming, metadata, and truth-vs-history rules.

## Document Types

### Governance Docs

Use for repo-wide rules, workflows, validation rules, and agent constraints.

### Overview Docs

Use for whole-system structure and subsystem boundaries.

### Module Docs

Use for the current valid state of one module.

### Change Docs

Use for one concrete implementation task or one completed task record.

### Draft Docs

Use for exploration, comparisons, temporary analysis, and unapproved thinking.

### Decision Docs / ADRs

Use for important long-term decisions.

### Playbooks

Use for repeatable engineering patterns, failure modes, and reusable lessons.

### Reference Docs

Use for repo-specific guidance on heavily used frameworks, libraries, or upstream repositories.

### Technical Docs

Use for detailed call chains, execution flows, and deeper implementation diagrams.

## Placement

Formal docs belong under `docs/`.

Recommended structure:

```text
docs/
  00-governance/
  01-overview/
  02-modules/
  03-changes/
    app4/
    quantaalpha/
    backtest/
    common/
  04-decisions/
  05-playbooks/
  06-references/
  07-technical/
  drafts/
```

### Change-Doc Structure

The target structure for change docs is module-flat:

```text
docs/03-changes/<module>/YYYY-MM-DD-topic.md
```

Recommended module buckets:
- `app4/`
- `quantaalpha/`
- `backtest/`
- `common/` for cross-module changes

Extension rules:
- other module buckets such as `vnpy/` may exist as reserved structure
- new buckets should represent stable module classification, not workflow state
- do not create status subdirectories under a module bucket

Rules:
- every change doc exists once under the module root
- the filesystem path identifies document family and module only
- workflow state belongs in document metadata
- legacy status directories may remain temporarily during migration
- do not create new docs using the legacy path-managed status structure

### Module-Local README

A local `README.md` is allowed for setup, local commands, and code-adjacent notes, but it is not the primary source of truth for module behavior.

## Truth Vs History

### Current Truth

These are the default truth sources:
- governance docs
- overview docs
- module docs
- currently valid ADRs
- current playbooks
- current reference docs
- technical docs when they describe active execution detail

### History Or Process Material

These are not default truth sources:
- drafts
- completed change docs
- superseded ADRs
- obsolete references
- archived docs

## Naming

### General Naming

- use lowercase file names
- separate words with `-`
- avoid vague names like `final`, `latest`, `new`, `v2`

### Change Docs

Format:

```text
docs/03-changes/<module>/YYYY-MM-DD-topic.md
```

Use `common/` for cross-module changes.

### Draft Docs

Format:

```text
YYYY-MM-DD-topic-type.md
```

### ADRs

Format:

```text
ADR-XXX-topic.md
```

### Reference Docs

Format:

```text
<framework-or-repo>-reference.md
```

## Required Metadata

Use metadata headers for drafts, change docs, references, and archived docs.

Recommended YAML frontmatter:

```yaml
---
doc_type: change | draft | governance | module | decision | playbook | reference | technical | overview
module: app4 | quantaalpha | backtest | common
status: draft | planned | doing | done | archived | active | superseded
owner: <name>
created: YYYY-MM-DD
updated: YYYY-MM-DD
summary: <one line purpose>
---
```

Optional fields:

```yaml
code_paths:
  - <path>
doc_refs:
  - <path>
validation:
  - <command>
review_required: true | false
blocked_by: <text>
outcome: pending | accepted | rejected | superseded
superseded_by: <path>
archive: true | false
```

### Metadata Rules

- `doc_type` must agree with document family
- `module` is required for change docs and optional elsewhere
- `status` must use the standard vocabulary
- `updated` should change when status or substance changes
- `summary` should make routing easier, not repeat the file name

## Status Meanings

- `draft`: exploratory, not yet approved as implementation work
- `planned`: concrete task exists and is approved to start
- `doing`: implementation or migration work is underway
- `done`: required implementation and validation are complete
- `archived`: kept for history only
- `active`: current-truth document in active use
- `superseded`: replaced by a newer document or rule

Fine-grained closure details should live in optional fields such as:
- `review_required`
- `outcome`
- `blocked_by`

Do not create extra directory levels to represent these distinctions.

## Path And Metadata Agreement

Preferred combinations:
- `docs/drafts/` + `doc_type: draft`
- `docs/03-changes/<module>/` + `doc_type: change`
- `docs/02-modules/` + `doc_type: module`
- `docs/04-decisions/` + `doc_type: decision`

If a draft already reads like a concrete implementation task, promote it into a module-flat change doc instead of leaving it in `docs/drafts/`.

## Minimum Enforcement

Keep these rules stable:
1. formal docs live under `docs/`
2. module docs describe current state only
3. meaningful changes should have change docs
4. drafts stay isolated from formal truth
5. reusable knowledge is promoted out of task-local docs when it becomes stable
6. change-doc state is encoded in metadata, not path names
