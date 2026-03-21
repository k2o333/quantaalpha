# Documentation Validation

## Purpose

This file defines the minimum validation model for repository documentation.

The goal is to keep documents self-consistent, machine-routable, and aligned with truth-layer rules.

## Validation Principles

1. document paths should express stable classification only
2. workflow state should live in metadata, not path names
3. every formal doc should be classifiable by family and role
4. generated views are not the source of truth
5. contradictions should be surfaced early

## Required Validation Checks

The documentation validator should check at least:
1. required metadata fields exist when mandated by doc type
2. `doc_type` uses the standard vocabulary
3. `status` uses the standard vocabulary
4. `module` matches directory placement for change docs
5. local document references point to existing files
6. no new change docs are created in legacy status subdirectories
7. archived docs are not marked as current truth
8. change docs with `status: done` include validation evidence

## Preferred Validation Tool

Use a fixed repository script such as:

```text
scripts/doc_index.py
```

Suggested responsibilities:
- scan `docs/`
- parse metadata
- list docs by type, module, owner, and status
- generate summary views
- identify stale docs
- run structural validation checks

Suggested commands:

```bash
python scripts/doc_index.py list --type change --module quantaalpha --status planned
python scripts/doc_index.py summary
python scripts/doc_index.py stale --days 7
python scripts/doc_index.py validate
```

## Validation Severity

Treat these as failures:
- invalid metadata vocabulary
- path and metadata mismatch
- missing required metadata for change docs
- broken mandatory local references
- new docs created in forbidden legacy path patterns

Treat these as warnings unless the task says otherwise:
- stale change docs
- incomplete optional metadata
- historical docs with weak summaries

## Manual Review Checks

For governance-doc changes, manual review should confirm:
- routing still matches the real directory model
- truth-vs-history rules are consistent across governance files
- no file reintroduces path-based status semantics as the target standard

## Generated Views

If a human-readable status table is useful, generate it from document metadata.

Do not use a manually maintained global table as primary source truth.
