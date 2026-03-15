# Documentation Standards

## Purpose

This file defines stable documentation standards: document types, placement, naming, status headers, and truth-vs-history rules.

## Document Types

### Governance Docs

Use for repo-wide rules, workflows, and conventions.

### Overview Docs

Use for whole-system structure and subsystem boundaries.

### Module Docs

Use for the current valid state of one module.

### Change Docs

Use for one concrete implementation task or change.

### Draft Docs

Use for exploration, comparisons, and temporary thinking.

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
  04-decisions/
  05-playbooks/
  06-references/
  07-technical/
  drafts/
```

### Module-local README

A local `README.md` is allowed for setup, local commands, and code-adjacent notes, but it is not the primary source of truth for module behavior.

## Truth Vs History

### Current truth

These are default truth sources:
- governance docs
- overview docs
- module docs
- currently valid ADRs
- current playbooks
- current reference docs

### History or process material

These are not default truth sources:
- drafts
- completed change docs
- superseded ADRs
- obsolete references
- archived docs

## Naming And Status

### General naming

- use lowercase file names
- separate words with `-`
- avoid vague names like `final`, `latest`, `new`, `v2`

### Change docs

Format:

```text
docs/03-changes/<module>/YYYY-MM-DD-topic.md
```

Use `common/` for cross-module changes.

### Draft docs

Format:

```text
YYYY-MM-DD-topic-type.md
```

### ADRs

Format:

```text
ADR-XXX-topic.md
```

### Reference docs

Format:

```text
<framework-or-repo>-reference.md
```

### Recommended status header

Use status headers for drafts, change docs, references, and archived docs.

Recommended fields:

```md
Status: draft | validated | in_progress | implemented | tested | accepted | archived | active | superseded
Owner: <name>
Created: YYYY-MM-DD
Outcome: pending | accepted | rejected | superseded
```

Optional fields:

```md
Version: <version or range>
Superseded-by: <path>
Related-to: <path>
Updated: YYYY-MM-DD
```

## Minimum Enforcement

Keep these rules stable:
1. formal docs live under `docs/`
2. module docs describe current state only
3. meaningful changes should have change docs
4. drafts stay isolated from formal truth
5. reusable knowledge is promoted out of task-local docs when it becomes stable
