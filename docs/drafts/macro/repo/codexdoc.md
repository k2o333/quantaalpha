# AI-Agent-Oriented Documentation System Proposal

Status: draft
Created: 2026-03-21
Owner: codex
Related-to: docs/00-governance/agent.md
Related-to: docs/00-governance/rules.md
Related-to: docs/00-governance/doc-standards.md
Related-to: docs/00-governance/doc-workflows.md

---

## 1. Proposal Goal

This proposal redesigns the `docs/` system for AI coding agents as the primary reader and executor.

The target outcome is:

1. lower information entropy
2. make routing predictable with the fewest possible path branches
3. let agents locate the correct truth layer and task context quickly
4. eliminate path-based status sprawl under `docs/03-changes/`
5. establish explicit validation and behavior constraints so documents remain self-consistent

This is a proposal document, not an implementation record.

---

## 2. Current Problems

### 2.1 High-Entropy Change-Doc Paths

Current `docs/03-changes/` mixes two different concerns in one path:

- module classification
- lifecycle status

Example:

```text
docs/03-changes/quantaalpha/planned/...
docs/03-changes/quantaalpha/in_progress/...
docs/03-changes/quantaalpha/tested/...
```

This creates several problems:

- agents must guess both module and status before locating a document
- a status change requires moving the file and updating its content
- links become unstable because file paths change when status changes
- different modules can evolve inconsistent structures

### 2.2 `agent.md` Still Routes Through Status Directories

Current `agent.md` tells the agent to use `docs/03-changes/<module>/<status>/`.

That means the repository entrypoint still encodes the old mental model:

- path equals state
- state discovery depends on directory traversal

This is the opposite of a low-entropy routing model.

### 2.3 Truth Layer And Process Layer Are Not Strict Enough

Some governance docs already define source-of-truth priority, but the operating model is still noisy:

- `docs/02-modules/` is current truth
- `docs/03-changes/` is process history and task context
- `docs/drafts/` is exploratory material

The distinction exists conceptually, but the system still forces agents to inspect too many paths before acting.

### 2.4 Missing Document Self-Consistency Mechanism

There is no complete validation mechanism that can automatically check:

- path and metadata agreement
- required metadata completeness
- broken internal references
- status vocabulary correctness
- contradiction between document role and document location

Without a validator, consistency depends on manual discipline.

### 2.5 Agent Constraints Are Not Centralized Enough

Behavior restrictions exist in rules, but they are not documented as a dedicated, operational constraint contract for agents.

For agent-first repositories, this must be explicit:

- what can be modified without approval
- what must never be modified automatically
- what actions require human authorization
- what counts as completion evidence

### 2.6 Workflow Documents Do Not Yet Define A Single Low-Entropy Lifecycle

The current workflow model is document-rich but still split across several files and tied to the old status tree.

The new system should define one standard lifecycle from:

- draft
- plan
- implementation
- validation
- promotion
- archive

with clear goals, owners, deliverables, and timing fields.

---

## 3. Design Principle

The governing principle is:

**A path should express only stable classification, never transient workflow state.**

This leads to four design rules:

1. use directories only for stable semantics such as document type and module
2. store workflow state inside document metadata, not in directory names
3. make scripts, not humans, generate status views and summaries
4. keep the repository entrypoint minimal, deterministic, and machine-routable

---

## 4. Recommended Target Model

### 4.1 Recommended Structure

```text
docs/
  00-governance/
    agent.md
    rules.md
    agent-constraints.md
    doc-standards.md
    doc-workflows.md
    doc-validation.md
  01-overview/
  02-modules/
  03-changes/
    app4/
      YYYY-MM-DD-topic.md
    quantaalpha/
      YYYY-MM-DD-topic.md
    backtest/
      YYYY-MM-DD-topic.md
    common/
      YYYY-MM-DD-topic.md
  04-decisions/
  05-playbooks/
  06-references/
  07-technical/
  drafts/
```

### 4.2 What Changes

Under this model:

- `docs/03-changes/<module>/draft/` disappears
- `docs/03-changes/<module>/planned/` disappears
- `docs/03-changes/<module>/in_progress/` disappears
- all other status subdirectories disappear
- each change doc exists only once under its module root

Example:

```text
docs/03-changes/quantaalpha/2026-03-21-factor-validation-fix.md
```

The file never moves because of a state update.

### 4.3 Why This Is Lower Entropy

The agent only needs two routing decisions:

1. what document layer is needed
2. what module is involved

The agent no longer needs to guess a third dimension, status, from the filesystem.

That reduces:

- path branching
- lookup variance
- move operations
- stale references
- state duplication between path and header

---

## 5. Document Layer Model

### 5.1 Layer Definitions

The repository should document and enforce these layers:

| Layer | Purpose | Is it current truth |
|---|---|---|
| `00-governance/` | rules, routing, standards, constraints, validation rules | yes |
| `01-overview/` | system-level map and major boundaries | yes |
| `02-modules/` | current valid state of each module | yes |
| `03-changes/` | task-scoped implementation context and closure evidence | no, unless promoted |
| `04-decisions/` | durable architectural or policy decisions | yes |
| `05-playbooks/` | reusable patterns, procedures, lessons | yes |
| `06-references/` | repo-specific external dependency usage guidance | yes |
| `07-technical/` | deep execution flow and implementation detail | supporting truth |
| `drafts/` | exploration, temporary analysis, unapproved ideas | no |

### 5.2 Routing Rule For Agents

The agent should always answer this sequence:

1. do I need current truth or process context
2. if current truth, go to governance, overview, module, decision, playbook, or reference docs
3. if task context, go to `docs/03-changes/<module>/`
4. if only exploratory material exists, use `docs/drafts/` as non-authoritative context

This sequence should be encoded directly into `agent.md`.

---

## 6. `agent.md` Redesign

### 6.1 Target Role Of `agent.md`

`agent.md` should become a short routing controller, not a broad narrative file.

Its job is only to answer:

- where to start
- which truth layer to read next
- which script to run for change-doc discovery
- when to stop for review

### 6.2 Recommended `agent.md` Structure

Recommended sections:

1. Read Order
2. Truth Priority
3. Fast Routing Table
4. Code Entrypoints
5. Validation Entrypoints
6. Required Stop Conditions

### 6.3 Recommended Routing Language

The key routing change is:

- remove references to `docs/03-changes/<module>/<status>/`
- replace them with `docs/03-changes/<module>/`
- direct the agent to a status-query script for filtering

Recommended routing semantics:

- current module behavior: `docs/02-modules/<module>.md`
- task implementation context: `docs/03-changes/<module>/`
- task status lookup: `scripts/doc_index.py`
- durable decision rationale: `docs/04-decisions/`
- repeatable procedure: `docs/05-playbooks/`

### 6.4 Why This Improves Precision

This design reduces search error in two ways:

- the entrypoint points to one canonical module directory, not multiple state directories
- the entrypoint distinguishes truth docs from process docs explicitly

For an AI agent, deterministic routing matters more than human-friendly prose.

---

## 7. Change Doc Standard

### 7.1 One File Per Task

Each task-oriented change document should exist exactly once:

```text
docs/03-changes/<module>/YYYY-MM-DD-topic.md
```

### 7.2 Required Metadata

Each change doc should start with structured metadata:

```yaml
---
doc_type: change
module: quantaalpha
status: planned
owner: quan
created: 2026-03-21
updated: 2026-03-21
summary: fix factor validation flow mismatch
code_paths:
  - third_party/quantaalpha/
doc_refs:
  - docs/02-modules/quantaalpha.md
validation:
  - /root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests -v
review_required: true
archive: false
---
```

### 7.3 Required Content Sections

Minimum sections:

1. Background
2. Goal
3. Scope
4. Non-Goals
5. Target Files Or Components
6. Implementation Plan Or Result
7. Validation
8. Risks Or Follow-up

### 7.4 Status Vocabulary

The recommended status set is:

- `draft`
- `planned`
- `doing`
- `done`
- `archived`

Optional support fields:

- `blocked_by`
- `outcome`
- `superseded_by`

### 7.5 Why Statuses Should Be Fewer

The old model uses too many lifecycle distinctions for the routing value they provide.

For AI agents, the useful question is usually:

- not ready
- approved
- active
- finished
- historical

Therefore:

- `implemented`, `tested`, and `accepted` should not each own a directory
- finer-grained closure detail should live in metadata or section content

Example:

```yaml
status: done
validation_state: passed
review_state: accepted
```

This keeps the path stable while preserving detail.

---

## 8. Status Discovery Without A Manually Maintained Table

### 8.1 Principle

A manually maintained global table should not be the primary fact store.

The source of truth should be:

- each document's own metadata

The table should be:

- a generated view

### 8.2 Recommended Script

Add a fixed script such as:

```text
scripts/doc_index.py
```

Suggested commands:

```bash
python scripts/doc_index.py list --type change --module quantaalpha --status planned
python scripts/doc_index.py list --type change --status doing
python scripts/doc_index.py summary
python scripts/doc_index.py stale --days 7
python scripts/doc_index.py validate
```

### 8.3 Script Responsibilities

The script should:

- scan `docs/`
- parse document metadata
- filter by type, module, owner, and status
- generate summaries
- identify stale docs
- validate metadata completeness
- validate path and metadata agreement
- optionally emit machine-readable JSON

### 8.4 Optional Generated Table

If a human-readable table is useful, it should be generated to a stable file such as:

```text
docs/00-governance/generated-doc-index.md
```

But that file must be explicitly marked as generated output, not source truth.

---

## 9. Document Validation Mechanism

### 9.1 Validation Goal

The system must ensure all documentation is:

- self-consistent
- structurally valid
- non-contradictory at the metadata level
- internally navigable
- aligned with truth-layer rules

### 9.2 Validation Scope

The validator should check at least:

1. required metadata fields exist
2. metadata values are from the allowed vocabulary
3. `module` matches directory placement for change docs
4. `doc_type` matches directory family
5. `status` is legal for that document type
6. referenced local docs exist
7. forbidden path patterns are absent
8. duplicate task files with conflicting metadata are flagged
9. generated files are not edited manually

### 9.3 Cross-Document Consistency Checks

The validator should also support higher-value checks:

1. a `doc_refs` target exists
2. an archived doc does not claim to be current truth
3. a module doc is not marked as draft
4. a draft is not cited as authoritative truth in governance docs
5. a change doc with `status: done` includes validation evidence

### 9.4 Contradiction Policy

If the validator finds contradictions, the rule should be:

1. governance path and metadata violations fail validation immediately
2. truth-layer contradictions are warnings or failures based on severity
3. historical wording conflicts should be marked for manual review

### 9.5 Recommended Governance Files

Add or revise:

- `docs/00-governance/doc-validation.md`
- `scripts/doc_index.py`
- optional `tests` for document validation logic

---

## 10. Agent Behavior Constraints

### 10.1 Need For A Dedicated Constraint File

Rules currently exist, but the new system should define one dedicated contract:

```text
docs/00-governance/agent-constraints.md
```

This file should be short, imperative, and machine-oriented.

### 10.2 Mandatory Constraints

The constraint set should explicitly include:

1. do not modify files outside explicit task scope
2. do not create new formal docs unless the task or workflow requires them
3. do not modify system configuration, runtime environments, or interpreters without authorization
4. do not edit protected third-party paths unless explicitly required
5. do not treat `docs/drafts/` as current truth
6. do not update generated files manually unless the workflow says to regenerate them
7. do not claim completion without running the required validation
8. do not silently rewrite or relocate documents outside the migration plan
9. do not change file naming conventions or metadata schema ad hoc
10. stop for human review before high-risk or cross-module changes

### 10.3 Authorization Boundaries

The system should distinguish:

Allowed without special approval:

- scoped doc edits
- scoped code edits inside approved task boundaries
- metadata updates
- validation execution

Require explicit human approval:

- modifying system config
- changing environment setup
- changing storage paths or data write semantics
- bulk moving or deleting docs
- modifying protected third-party areas
- changing repository-wide governance rules

### 10.4 Completion Contract

An agent should not report work as complete unless it can state:

1. target module
2. target files
3. truth docs consulted
4. validation command used
5. whether human review is required

This should be documented in `rules.md` and linked from `agent.md`.

---

## 11. End-To-End Workflow Design

### 11.1 Workflow Objective

The workflow should define a clean path from idea to archive with explicit handoffs and artifacts.

### 11.2 Recommended Lifecycle

```text
draft -> planned -> doing -> done -> archived
```

### 11.3 Stage Definition

| Stage | Goal | Responsible party | Main deliverable | Timing signal |
|---|---|---|---|---|
| `draft` | explore a problem or option | human or agent | exploratory doc or initial change doc | created date |
| `planned` | define approved work item | human approves, agent prepares | scoped change doc with validation plan | updated date |
| `doing` | execute the approved task | agent or developer | code/doc/config changes plus progress updates | updated date |
| `done` | close with evidence | agent plus reviewer if needed | final change doc with validation and outcome | validation timestamp |
| `archived` | keep as history only | human or agent under rule | historical record | archive date |

### 11.4 Workflow Artifacts

For each task, the workflow should define:

1. source trigger
2. primary doc
3. code target
4. validation target
5. closure decision
6. promotion target if truth changed

### 11.5 Promotion Rules

At `done`, the owner must decide whether knowledge should also move to:

- `02-modules/` if current behavior changed
- `04-decisions/` if durable architecture or policy changed
- `05-playbooks/` if the lesson is reusable
- `06-references/` if external dependency usage guidance changed

This is how the system prevents change docs from becoming accidental truth.

### 11.6 Archive Rules

A document should move to `archived` status only when:

1. the task is no longer active
2. any required truth promotion is complete
3. follow-up tasks are either linked or split into new docs
4. its historical role is explicit

The file path does not change when archived. Only metadata changes.

---

## 12. Migration Strategy

### 12.1 Recommended Strategy

Use a phased migration, not a one-shot bulk rewrite.

Phase 1:

- approve the new model
- rewrite governance docs to define the model
- add the index and validation script

Phase 2:

- update `agent.md`
- start creating all new change docs in flat module directories
- keep old status directories readable during transition

Phase 3:

- gradually migrate active old change docs when they are touched
- normalize metadata to the new schema

Phase 4:

- remove empty lifecycle directories
- freeze and archive remaining legacy structure if needed

### 12.2 Migration Rule

Do not migrate every old file immediately.

Prefer:

- migrate when the document is touched
- migrate when the task reopens
- migrate when links or workflow tooling require normalization

This keeps risk and churn low.

---

## 13. Proposed Governance File Changes

### 13.1 Files To Revise

- `docs/00-governance/agent.md`
- `docs/00-governance/rules.md`
- `docs/00-governance/doc-standards.md`
- `docs/00-governance/doc-workflows.md`

### 13.2 Files To Add

- `docs/00-governance/agent-constraints.md`
- `docs/00-governance/doc-validation.md`
- `scripts/doc_index.py`

### 13.3 Files To De-Emphasize

The following should remain non-authoritative:

- `docs/drafts/`
- legacy status subdirectories under `docs/03-changes/`
- manually edited status summary tables

---

## 14. Why This Proposal Is Better For AI Agents

This proposal is optimized for machine routing, not just human browsing.

The new model improves agent performance because:

1. paths become stable identifiers
2. state is machine-readable metadata, not implicit directory meaning
3. routing rules become deterministic
4. truth layers are separated from process layers
5. validation can enforce consistency automatically

In practical terms, an agent can answer:

- where is current truth
- where is task context
- what is the current state of this task
- what validation is required

without scanning multiple parallel directory trees.

That is the core entropy reduction.

---

## 15. Recommendation

Adopt the module-flat change-doc model as the target standard for `docs/03-changes/`.

Specifically:

1. flatten each module under `docs/03-changes/`
2. store task status in document metadata only
3. rewrite `agent.md` as a deterministic router
4. add a fixed indexing and validation script
5. create a dedicated agent constraint document
6. redefine workflow around one stable lifecycle and promotion model

This is the most balanced design for the current repository because it:

- significantly lowers entropy
- reduces state duplication
- improves document lookup speed
- keeps module boundaries visible
- avoids over-centralizing all change docs into one global directory

---

## 16. Suggested Next Step

If this proposal is accepted, the next implementation step should be:

1. revise governance docs to define the new model
2. create `scripts/doc_index.py`
3. update `agent.md` routing
4. begin gradual migration of active change docs

