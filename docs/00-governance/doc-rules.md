# Documentation Rules

## Purpose

This file is the entrypoint for documentation work.

Do not read the full documentation system unless needed. Start from the workflow table below and only open the next targeted doc.

## Core Principle

Most documentation work in this repo follows a promotion path:

`draft -> change doc -> module doc / ADR / playbook / reference doc`

Not every task passes through every stage, but this is the default model for organizing evolving work.

## Documentation Workflows

| If you are doing this | Read next |
|---|---|
| creating or cleaning a draft | `docs/00-governance/doc-workflows.md#draft-workflows` |
| turning a draft into an implementation task | `docs/00-governance/doc-workflows.md#draft-to-change` |
| closing a finished task | `docs/00-governance/doc-workflows.md#change-closure` |
| deciding whether current truth changed | `docs/00-governance/doc-workflows.md#change-to-module` |
| promoting reusable lessons | `docs/00-governance/doc-workflows.md#promotion-targets` |
| drafting a controlled governance-doc task | `docs/00-governance/doc-task-template.md` |
| choosing a doc type or placement | `docs/00-governance/doc-standards.md#document-types` |
| applying naming or status headers | `docs/00-governance/doc-standards.md#naming-and-status` |
| deciding whether something is truth or history | `docs/00-governance/doc-standards.md#truth-vs-history` |

## Default Order For Documentation Closure

After meaningful implementation work, close documentation in this order:
1. update or create the change doc
2. decide whether module truth changed
3. decide whether a long-term decision changed
4. decide whether lessons should become a playbook
5. decide whether dependency-specific knowledge should become a reference doc

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
