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

### Change doc structure

The target structure for change docs is:

```text
docs/03-changes/<module>/draft/YYYY-MM-DD-topic.md
docs/03-changes/<module>/planned/YYYY-MM-DD-topic.md
docs/03-changes/<module>/in_progress/YYYY-MM-DD-topic.md
docs/03-changes/<module>/blocked/YYYY-MM-DD-topic.md
docs/03-changes/<module>/implemented/YYYY-MM-DD-topic.md
docs/03-changes/<module>/tested/YYYY-MM-DD-topic.md
docs/03-changes/<module>/accepted/YYYY-MM-DD-topic.md
docs/03-changes/<module>/archived/YYYY-MM-DD-topic.md
```

Recommended module buckets:
- `app4/`
- `quantaalpha/`
- `backtest/`
- `common/` for cross-module changes

Extension rules:
- other module buckets (e.g., `vnpy/`) may be kept as reserved structures
- new module buckets should maintain consistent lifecycle directory structure
- reserved empty directories do not require immediate population

Rules:
- every module should have lifecycle subdirectories for task docs
- module-scoped exploratory task docs should use `docs/03-changes/<module>/draft/`
- approved but not-yet-started tasks should use `docs/03-changes/<module>/planned/`
- active implementation task docs should use `docs/03-changes/<module>/in_progress/` or `blocked/`
- implemented or completed task docs should use `implemented/`, `tested/`, `accepted/`, or `archived/`
- old year-based directories may remain temporarily as legacy history
- legacy change docs may be migrated gradually when useful
- do not create new year-flat directories as the preferred structure

### Root-level exception

`docs/03-changes/<module>/` root should only contain non-single-task documents such as:
- checklist docs
- index docs
- task collection summaries
- module-level change overviews

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
docs/03-changes/<module>/draft/YYYY-MM-DD-topic.md
docs/03-changes/<module>/planned/YYYY-MM-DD-topic.md
docs/03-changes/<module>/in_progress/YYYY-MM-DD-topic.md
docs/03-changes/<module>/blocked/YYYY-MM-DD-topic.md
docs/03-changes/<module>/implemented/YYYY-MM-DD-topic.md
docs/03-changes/<module>/tested/YYYY-MM-DD-topic.md
docs/03-changes/<module>/accepted/YYYY-MM-DD-topic.md
docs/03-changes/<module>/archived/YYYY-MM-DD-topic.md
```

Use `common/` for cross-module changes.

Preferred modules:
- `app4`
- `quantaalpha`
- `backtest`
- `common`

Interpretation:
- `draft/` means module-scoped but still exploratory
- `planned/` means approved and queued, but not started
- `in_progress/` means implementation is underway
- `blocked/` means a real task is paused by a blocker
- `implemented/` means implementation landed but final closure is not complete
- `tested/` means required validation is complete
- `accepted/` means the task record is accepted as closed
- `archived/` means historical, superseded, or no longer current

### Draft docs

Format:

```text
YYYY-MM-DD-topic-type.md
```

Task-oriented drafts should also include enough implementation guidance to act as a fallback routing aid.

Recommended minimum sections for task-oriented drafts:
- `Background`
- `Goal`
- `Non-Goals`
- `Target Scope` or equivalent
- `Proposed Approach` or equivalent
- `Validation`

Minimum content expectations:
- state what kind of task this is: code change, documentation change, config change, or mixed
- identify the likely target module or target documents
- name the files, directories, or doc families that should be checked first
- describe the intended action at a practical level so another agent can understand what should be done even without reading every routed document first
- name the expected validation or closure check

Important boundary:
- a draft is still not the source of truth
- a draft should provide directional "how to proceed" guidance as a second layer of safety
- stable rules, final process definitions, and current-state truth still belong in governance docs, module docs, ADRs, or other formal docs

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
Status: draft | planned | in_progress | blocked | implemented | tested | accepted | archived | active | superseded
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

### Status meanings

- `draft`: exploratory, not yet committed as an implementation task
- `planned`: a concrete task exists, but implementation has not started
- `in_progress`: implementation or migration work is underway
- `blocked`: the task is real but cannot continue yet
- `implemented`: code or docs landed, but closure is not complete
- `tested`: required validation is complete
- `accepted`: accepted as completed task record
- `active`: current truth document in active use
- `archived`: kept for history only
- `superseded`: replaced by a newer document or rule

### Path and status should agree

Preferred combinations:
- `docs/drafts/` + `draft`
- `docs/03-changes/<module>/draft/` + `draft`
- `docs/03-changes/<module>/planned/` + `planned`
- `docs/03-changes/<module>/in_progress/` + `in_progress`
- `docs/03-changes/<module>/blocked/` + `blocked`
- `docs/03-changes/<module>/implemented/` + `implemented`
- `docs/03-changes/<module>/tested/` + `tested`
- `docs/03-changes/<module>/accepted/` + `accepted`
- `docs/03-changes/<module>/archived/` + `archived` or `superseded`
- `docs/02-modules/` + `active`

If a draft already reads like a concrete implementation task, promote it to a module-specific change doc instead of leaving it in `docs/drafts/`.

## Minimum Enforcement

Keep these rules stable:
1. formal docs live under `docs/`
2. module docs describe current state only
3. meaningful changes should have change docs
4. drafts stay isolated from formal truth
5. reusable knowledge is promoted out of task-local docs when it becomes stable
