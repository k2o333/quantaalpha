---
doc_type: change
module: quantaalpha
status: done
owner: quan
created: 2026-03-21
updated: 2026-03-21
summary: Quantaalpha flat migration next-round cleanup checklist
validation:
  - python3 scripts/doc_index.py list --type change --module quantaalpha --status planned --json
  - python3 scripts/doc_index.py validate
---

# Quantaalpha Flat Migration Follow-ups

## Purpose

This checklist captures the next cleanup pass after the active legacy change-doc migration in `docs/03-changes/quantaalpha/`.

Per `docs/00-governance/agent.md`, this belongs in `docs/03-changes/quantaalpha/` because it is a concrete module-scoped follow-up task, not a reusable cross-repo playbook.

## Checklist

- confirm all 11 migrated flat docs still have valid metadata and correct `status: planned`
- decide whether `.task.md` files under `planned/parr2/` and `planned/parrelell/` should remain operational artifacts or be reclassified into another doc family
- decide whether `planned/README.md` and `planned/parr2/README.md` should stay as legacy index pages or be replaced by flat-path index docs
- clean remaining high-value legacy links in `docs/02-modules/`, `docs/04-decisions/`, and `docs/05-playbooks/` that still point to old `planned/` paths
- document handling rules for `.prompt.txt`, `batch.status.json`, and `run_parallel_commands.txt` so agents do not treat them as change docs
- run `python3 scripts/doc_index.py list --type change --module quantaalpha --status planned --json`
- run `python3 scripts/doc_index.py validate`
- report residual issues separately for `quantaalpha` and `app4` instead of mixing them into one completion claim

## Execution Summary

### Item 1: Confirm all 11 flat docs
All 11 flat change docs in `docs/03-changes/quantaalpha/` have valid metadata and `status: planned`. No issues found.

### Item 2: .task.md files under `planned/parr2/` and `planned/parrelell/`
Decision: classify as operational artifacts. Added `classification: operational_artifact` and `doc_type: operational_artifact` to frontmatter of all 16 `.task.md` files across `planned/parr2/dev/`, `planned/parr2/test/`, `planned/parrelell/dev/`, and `planned/parrelell/review/`. Also updated `source_doc` / `source_slice_doc` fields to mark legacy `planned/` path references as historical only (see Task 2 below).

### Item 3: `planned/README.md` and `planned/parr2/README.md`
Decision: keep as non-source-of-truth index pages. Added frontmatter with `doc_type: operational_artifact` and `classification: non_source_of_truth_index`, plus classification headers in body, to both files.

### Item 4: Legacy links in `docs/02-modules/`, `docs/04-decisions/`, `docs/05-playbooks/`
- `docs/04-decisions/ADR-002-agent-oriented-documentation-system.md`: Added historical note marking the status-dir structure as superseded by the flat model, updated path examples and migration reference.
- `docs/05-playbooks/planned-doc-hardening-playbook.md` line 25: Updated reference from `planned/` path to flat path with `status: planned` in metadata.
- `docs/05-playbooks/03-changes-flat-migration-playbook.md` line 247: No change needed (already documents the bad pattern to avoid).

### Item 5: Handling rules for `.prompt.txt`, `batch.status.json`, `run_parallel_commands.txt`
Added "Operational Artifacts" section to `docs/00-governance/doc-rules.md` explicitly classifying these file types as non-source-of-truth operational artifacts.

### Item 6: `doc_index.py list` (quantaalpha planned)
After fix-pass: **11 documents found**, all flat-path change docs with valid metadata. README files and .task.md files are excluded because they carry `doc_type: operational_artifact`. (Initial run returned 29 because .task.md files still lacked `doc_type: operational_artifact`.)

### Item 7: `doc_index.py validate`
**quantaalpha: 0 issues** (after fix-pass; initial run reported 1 issue: `done change doc missing validation` on this very doc — fixed by adding `validation` field)
**app4: 26 issues** — all are `missing status` on legacy change docs under `docs/03-changes/app4/`. Outside quantaalpha scope.

## Done Criteria

- no source-of-truth quantaalpha change doc remains in a legacy `planned/`, `in_progress/`, or `blocked/` path
- remaining files under legacy paths are explicitly classified as non-source-of-truth operational artifacts or index pages
- high-value references no longer depend on old active legacy paths
- validation output is reported accurately with scope and residual issues
