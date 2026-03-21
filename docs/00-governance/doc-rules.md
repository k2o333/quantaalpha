# Documentation Rules

## Purpose

This file is the entrypoint for documentation work.

Do not read the full documentation system unless needed. Start from the routing table below and only open the next targeted doc.

## Core Principle

Most documentation work in this repo follows a promotion path:

`draft -> change doc -> module doc / ADR / playbook / reference doc`

Not every task passes through every stage, but this is the default model for organizing evolving work.

Under the current standard:
- change docs are module-flat
- task status lives in metadata
- manually maintained status tables are not source truth

## Documentation Workflows

| If you are doing this | Read next |
|---|---|
| creating or cleaning a draft | `docs/00-governance/doc-workflows.md#draft-workflows` |
| turning a draft into an implementation task | `docs/00-governance/doc-workflows.md#draft-to-change` |
| executing or closing a change doc | `docs/00-governance/doc-workflows.md#change-execution` |
| closing a finished task | `docs/00-governance/doc-workflows.md#change-closure` |
| deciding whether current truth changed | `docs/00-governance/doc-workflows.md#change-to-module` |
| promoting reusable lessons | `docs/00-governance/doc-workflows.md#promotion-targets` |
| drafting a controlled governance-doc task | `docs/00-governance/doc-task-template.md` |
| choosing a doc type or placement | `docs/00-governance/doc-standards.md#document-types` |
| applying naming or metadata headers | `docs/00-governance/doc-standards.md#required-metadata` |
| deciding whether something is truth or history | `docs/00-governance/doc-standards.md#truth-vs-history` |
| validating documentation consistency | `docs/00-governance/doc-validation.md` |

## Default Order For Documentation Closure

After meaningful implementation work, close documentation in this order:
1. update or create the change doc
2. decide whether module truth changed
3. decide whether a long-term decision changed
4. decide whether lessons should become a playbook
5. decide whether dependency-specific knowledge should become a reference doc

## Operational Artifacts (Non-Change-Doc Files)

The following file types under `docs/03-changes/` are **operational artifacts**, not change docs. Agents must not treat them as source of truth or route them as task context.

| File type | Purpose | Classification |
|---|---|---|
| `*.task.md` | Multi-stage agent execution task descriptor | `classification: operational_artifact` in frontmatter |
| `*.prompt.txt` | Agent prompt input for batch execution | operational artifact; not source of truth |
| `batch.status.json` | Batch run status tracking | operational artifact; not source of truth |
| `run_parallel_commands.txt` | Parallel execution command list | operational artifact; not source of truth |
| `planned/README.md` | Legacy task-grouping index | non-source-of-truth index page |

Source-of-truth task content lives in `docs/03-changes/<module>/YYYY-MM-DD-topic.md` with `doc_type: change` in metadata.

## Minimal Rules

- drafts are not source of truth
- module docs describe current valid state only
- meaningful implementation work should leave a change doc trail
- higher-level docs are updated only when current truth actually changed
- reusable knowledge is promoted out of task-local docs when it becomes stable

## Read Less, Route Better

If the task is obvious, read only:
- this file
- one section in `doc-workflows.md`
- one section in `doc-standards.md` if naming or placement is needed
- `doc-validation.md` if metadata or consistency checks matter
