---
doc_type: change
module: quantaalpha
status: planned
owner: quan
created: 2026-03-21
updated: 2026-03-21
summary: Quantaalpha flat migration next-round cleanup checklist
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

## Done Criteria

- no source-of-truth quantaalpha change doc remains in a legacy `planned/`, `in_progress/`, or `blocked/` path
- remaining files under legacy paths are explicitly classified as non-source-of-truth operational artifacts or index pages
- high-value references no longer depend on old active legacy paths
- validation output is reported accurately with scope and residual issues
