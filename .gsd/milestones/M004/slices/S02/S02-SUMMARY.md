---
id: S02
parent: M004
milestone: M004
status: completed
provides:
  - FactorLibraryManager.select_revalidation_candidates(days, status, factor_ids) method
  - last_validated field auto-initialized on factor entry creation (ISO 8601)
  - apply_validation_result() → update_factor_status() chain auto-updates last_validated
  - 15-pass unit test suite for all filtering scenarios
requires:
  - []
affects:
  - M004-S05 (因子生命周期状态机) — consumes last_validated and select_revalidation_candidates()
  - M004-S08 (24H调度中心) — consumes select_revalidation_candidates()
key_files:
  - third_party/quantaalpha/quantaalpha/factors/library.py
  - third_party/quantaalpha/quantaalpha/factors/status_rules.py
  - third_party/quantaalpha/tests/test_revalidation_candidates.py
key_decisions:
  - last_validated initialized with datetime.now().isoformat() (ISO 8601 string, not datetime object)
  - setdefault() used for last_validated initialization — existing values are never overwritten on normalize
  - None last_validated bypasses days filter (always included in results)
patterns_established:
  - ISO 8601 timestamps stored as strings throughout the evaluation dict
  - setdefault() initialization pattern: safe for both new entries and loaded-from-disk entries
  - status filter + days filter + factor_ids filter compose as AND (all conditions must match)
observability_surfaces:
  - `manager.select_revalidation_candidates(days=21, status="active")` — direct method call, returns list
  - `manager.get_summary()` — includes last_validated per factor
  - `manager.get_audit_trail(trigger="apply_validation_result")` — shows last_validated update events
  - `pytest tests/test_revalidation_candidates.py -v` — 15 tests, all passing
drill_down_paths:
  - T01: .gsd/milestones/M004/slices/S02/tasks/T01-SUMMARY.md
  - T02: .gsd/milestones/M004/slices/S02/tasks/T02-SUMMARY.md
duration: ~35 min (T01: ~5min, T02: ~30min including test writing)
verification_result: passed
completed_at: 2026-03-24
---

# S02: 因子重验候选选择 — Complete

**Implements R008: select_revalidation_candidates(days=21) for periodic factor revalidation.**

## What Happened

S02 implemented the automatic factor revalidation candidate selection system. The core mechanism allows the system to periodically identify factors that have not been validated within a configurable time window, enabling the "温故" (review/refresh) capability in the 24H scheduling pipeline.

### T01: Core Implementation

The implementation was already mostly in place — `select_revalidation_candidates()` existed in `library.py` and `update_factor_status()` in `status_rules.py` already updated `last_validated`. The only missing piece was initialization: `_normalize_factor_entry()` had `last_validated: None` as default, which would cause new factors to always appear as overdue (or cause comparison errors). Changed to `datetime.now().isoformat()` in two places:
1. Inside the nested dict literal passed to `setdefault("evaluation", {...})`
2. In the subsequent `setdefault("last_validated", ...)` call

The `setdefault()` pattern ensures existing values (from disk) are never overwritten.

### T02: Unit Tests

Created `tests/test_revalidation_candidates.py` with 15 test cases covering:
- No days filter → all factors returned
- Days=7 filter → only overdue (age ≥ 7 days) factors
- Status filter → AND-combined with days filter
- factor_ids filter → explicit ID subset selection
- Empty result scenarios
- None last_validated behavior (bypasses days filter, always included)
- Initialization safety (ISO timestamp, no overwrite on existing)

**Key finding discovered during testing:** `last_validated=None` factors bypass the days filter entirely because the code's `if last_validated:` guard skips the date comparison for None values. This is arguably correct — unknown validation age should not exclude a factor from revalidation consideration.

## Verification

| Check | Command | Result |
|-------|---------|--------|
| Syntax | `python -m py_compile quantaalpha/factors/library.py` | ✅ PASS |
| Syntax | `python -m py_compile quantaalpha/factors/status_rules.py` | ✅ PASS |
| Method exists | `grep -c "select_revalidation_candidates" library.py` | ✅ 1 |
| Unit tests | `pytest tests/test_revalidation_candidates.py -v` | ✅ 15/15 passed |

## Design Decisions

1. **ISO 8601 string format for timestamps** — Consistent with `created_at`, `last_updated`, and other timestamps throughout the library. `datetime.fromisoformat()` handles it for comparison.

2. **None bypasses days filter** — A factor without a known `last_validated` is always considered a candidate (assumed to need validation). This means newly added factors immediately appear in the candidate list.

3. **Status filter AND-composes with days** — `status="active"` AND `days=7` means only active factors validated more than 7 days ago. No OR or union semantics.

## Downstream Contract

S05 (因子生命周期状态机) and S08 (24H调度中心) will call:
```python
candidates = manager.select_revalidation_candidates(days=21, status="active")
for candidate in candidates:
    # trigger revalidation...
```

## Files Created/Modified

| File | Change |
|------|--------|
| `quantaalpha/factors/library.py` | Modified `_normalize_factor_entry()` — `last_validated` default changed from `None` to `datetime.now().isoformat()` (2 locations) |
| `quantaalpha/factors/status_rules.py` | No changes (already correctly updates `last_validated` in `update_factor_status()`) |
| `tests/test_revalidation_candidates.py` | **NEW** — 15 test cases in 3 classes |

## Forward Intelligence

### What the next slice should know
- `select_revalidation_candidates()` is fully implemented and tested. S05 can call it directly.
- `last_validated` is a string (ISO 8601), not a datetime object. Parse with `datetime.fromisoformat()` before comparison.
- `apply_validation_result()` automatically updates `last_validated` — no manual update needed in S05/S08.
- Audit trail entries with `trigger="apply_validation_result"` are written whenever `apply_validation_result()` is called with `persist=True`.

### What's fragile
- The `if last_validated:` guard in `select_revalidation_candidates()` means None values bypass the days filter. This is intentional but could be surprising. Documented in test comments.
- No upper bound on candidate count — calling `select_revalidation_candidates(days=1)` on a large library returns all factors validated ≤ 1 day ago. If no factors are that recent, most/all factors could be returned. Caller should handle large result sets.

### Authoritative diagnostics
- `grep "select_revalidation_candidates" quantaalpha/factors/library.py` — verify method exists
- `pytest tests/test_revalidation_candidates.py -v` — run full regression suite
- `manager.get_audit_trail(trigger="apply_validation_result")` — see timestamp update history
