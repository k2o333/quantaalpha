---
id: T01
parent: S03
milestone: M004
provides:
  - Tag classification constants and DEFAULT_TAGS schema
  - `_normalize_factor_entry()` tags field integration
  - 16 passing tests for tags initialization/migration/persistence
key_files:
  - third_party/quantaalpha/quantaalpha/factors/library.py
  - third_party/quantaalpha/quantaalpha/tests/test_factor_tags.py
patterns_established:
  - Migration-safe field addition: always use `isinstance` guard + `setdefault` before accessing nested keys
observability_surfaces:
  - Module-level `DEFAULT_TAGS`, `TAG_DEFINITIONS`, `CATEGORY_TAGS`, `DATA_DEPENDENCY_TAGS`, `MARKET_ENVIRONMENT_TAGS`, `TIME_HORIZON_TAGS` — inspectable at runtime
  - Diagnostic: `python -c "from quantaalpha.factors.library import DEFAULT_TAGS; import json; print(json.dumps(DEFAULT_TAGS))"`
duration: ~8min
verification_result: passed
completed_at: 2026-03-24T01:28:14+08:00
blocker_discovered: false
---

# T01: 因子条目 tags 字段定义 + library.py 集成

**Added 4-dimension tag classification constants and `tags` field to factor entries in `library.py`, with 16 passing tests.**

## What Happened

Implemented the full tag classification system in `library.py`. Added module-level tag enumeration constants (`CATEGORY_TAGS`, `DATA_DEPENDENCY_TAGS`, `MARKET_ENVIRONMENT_TAGS`, `TIME_HORIZON_TAGS`), a `TAG_DEFINITIONS` dict for validation, and a `DEFAULT_TAGS` empty-structure constant. Updated `_normalize_factor_entry()` to always include a `tags` field with all 4 dimensions present as empty lists by default, with migration-safe logic that handles existing entries (which lack the field), partial tags, `None` tags, and non-dict tags values without crashing. Created a comprehensive 16-test suite covering constant definitions, normalization behavior, JSON serializability, library upsert persistence, and legacy entry migration.

Also patched the slice plan (S03-PLAN.md) to fix verification paths (they incorrectly omitted the `third_party/quantaalpha/` prefix) and added missing `Observability / Diagnostics` section per pre-flight notes. Added `Expected Output` and `Observability Impact` sections to T01-PLAN.md.

## Verification

All 16 pytest tests pass. `py_compile` on `library.py` passes. `grep "tags" library.py` returns 8 occurrences (≥ 3 required). `py_compile` on `fewshot.py` was skipped — that file doesn't exist yet; T02 will create it.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m py_compile quantaalpha/factors/library.py` (from `third_party/quantaalpha/`) | 0 | ✅ pass | <1s |
| 2 | `grep -c "tags" quantaalpha/factors/library.py` (from `third_party/quantaalpha/`) | 0 | ✅ pass (8 ≥ 3) | <1s |
| 3 | `pytest quantaalpha/tests/test_factor_tags.py -v` | 0 | ✅ pass (16/16) | 0.46s |

## Diagnostics

- **Inspect tag schema at runtime:** `python -c "from quantaalpha.factors.library import DEFAULT_TAGS, TAG_DEFINITIONS; import json; print(json.dumps(DEFAULT_TAGS, indent=2))"`
- **Verify a factor has tags:** `manager.get_factor(factor_id)["tags"]` returns `{"category": [], "data_dependency": [], "market_environment": [], "time_horizon": []}` by default.
- **Failure state:** If `tags` is non-dict (e.g., a string), the `isinstance` guard silently falls back to `DEFAULT_TAGS` — no crash, but tag data is lost. This is logged nowhere; a future agent could add a warning log here.
- **Downstream contract:** T02's fewshot.py `relatedness` scoring reads `entry["tags"]` directly. T01 guarantees this field always exists (even as empty lists), preventing `KeyError`.

## Deviations

- Slice plan verification paths (`quantaalpha/factors/library.py`) are relative to `third_party/quantaalpha/` — not the repo root. Patched S03-PLAN.md to document this. No code deviation.
- `py_compile quantaalpha/factors/fewshot.py` was skipped because the file doesn't exist yet (T02 creates it).

## Known Issues

None. No blocking issues.

## Files Created/Modified

- `third_party/quantaalpha/quantaalpha/factors/library.py` — Added tag constants (CATEGORY_TAGS, DATA_DEPENDENCY_TAGS, MARKET_ENVIRONMENT_TAGS, TIME_HORIZON_TAGS, TAG_DEFINITIONS, DEFAULT_TAGS); added `tags` field to `_normalize_factor_entry()` with migration-safe defaults
- `third_party/quantaalpha/quantaalpha/tests/test_factor_tags.py` — New file: 16 tests covering all tag-related behavior
- `third_party/quantaalpha/quantaalpha/tests/__init__.py` — New file: package marker
- `.gsd/milestones/M004/slices/S03/S03-PLAN.md` — Fixed verification paths (added `third_party/quantaalpha/` prefix), added `Observability / Diagnostics` section
- `.gsd/milestones/M004/slices/S03/tasks/T01-PLAN.md` — Added `## Expected Output` and `## Observability Impact` sections
