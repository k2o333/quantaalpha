---
id: T01
parent: S07
milestone: M003
provides:
  - "PIT alignment core module with get_pit_sources(), detect_pit_fields(), needs_pit_alignment(), apply_pit_alignment(); 26 unit tests"
key_files:
  - "third_party/quantaalpha/quantaalpha/factors/pit_alignment.py"
  - "third_party/quantaalpha/tests/test_pit_alignment.py"
  - "third_party/quantaalpha/quantaalpha/factors/prompts/experiment.yaml"
key_decisions:
  - "Polars is optional; pandas is required (apply_pit_alignment takes pd.DataFrame input)"
  - "Used object.__setattr__ to attach _pit_meta to avoid pandas attribute-access warning"
patterns_established:
  - "Lazy-cached module-level reverse index ($field → source_name) built from S01 registry"
observability_surfaces:
  - "DEBUG log on apply_pit_alignment: 'PIT alignment applied for {source}: {rows_before} → {rows_after} rows (lag_days={lag_days})'"
  - "_PIT_DIAGNOSTIC_ENABLED env-var → _pit_meta attached to returned DataFrame"
duration: "~15m"
verification_result: passed
completed_at: "2026-03-23"
blocker_discovered: false
---

# T01: Build `pit_alignment.py` core module and unit tests

**Implemented `quantaalpha/factors/pit_alignment.py` with 4 public functions, 26 unit tests, and `pit_alignment:` YAML config section.**

## What Happened

Built the Point-in-Time (PIT) alignment module as a self-contained unit with the following public API:

- **`get_pit_sources(registry)`** — filters a data-capability registry to quarterly-only entries, falling back to `get_data_capabilities()` from S01
- **`detect_pit_fields(factor_expr)`** — extracts all `$field` tokens via regex
- **`needs_pit_alignment(factor_expr)`** — checks whether any extracted field maps to a quarterly source via the reverse index
- **`apply_pit_alignment(df, source_name, lag_days, pit_field, trade_date_field, symbol_field)`** — filters rows so each `(symbol, trade_date)` only sees announcements where `ann_date <= trade_date - lag_days`, keeping the most recent qualifying row. Auto-selects Polars for >10k rows, pandas otherwise.

The `_FIELD_TO_SOURCE` reverse index is built lazily from S01's `data_capability` registry on first call and cached at module level. All 26 unit tests pass covering: registry filtering, field extraction, quarterly/daily detection, PIT filtering logic (edge cases: empty df, missing columns, no qualifying rows, multiple symbols, multiple value columns, custom column names), diagnostic metadata attachment, and the reverse index mapping.

Added `pit_alignment:` section to `experiment.yaml` with `enabled: true`, `default_lag_days: 45`, and a `source_overrides` block for `forecast_vip: lag_days: 15`.

## Verification

- `python -m py_compile quantaalpha/factors/pit_alignment.py` — compile OK
- `pytest quantaalpha/tests/test_pit_alignment.py -v` — 26/26 passed
- `grep -c "pit_alignment:" quantaalpha/factors/prompts/experiment.yaml` — returns 1
- `grep "needs_pit_alignment\|apply_pit_alignment" quantaalpha/factors/pit_alignment.py` — returns 12 matches (≥2 requirement satisfied)

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m py_compile quantaalpha/factors/pit_alignment.py` | 0 | ✅ pass | <1s |
| 2 | `pytest tests/test_pit_alignment.py -v` | 0 | ✅ pass (26/26) | 0.65s |
| 3 | `grep -c "pit_alignment:" quantaalpha/factors/prompts/experiment.yaml` | 0 | ✅ pass (1) | <1s |
| 4 | `grep "needs_pit_alignment\|apply_pit_alignment" quantaalpha/factors/pit_alignment.py | wc -l` | 0 | ✅ pass (12 ≥ 2) | <1s |

## Diagnostics

- **DEBUG log**: `apply_pit_alignment` emits `"PIT alignment applied for {source}: {rows_before} → {rows_after} rows (lag_days={lag_days})"` on every call.
- **`_PIT_DIAGNOSTIC_ENABLED=true`**: attaches `._pit_meta` dict (`rows_before`, `rows_after`, `lag_days`, `source`) to the returned DataFrame.
- **Graceful degradation**: if `data_capability` module is unavailable, `_FIELD_TO_SOURCE` stays empty and `needs_pit_alignment` returns `False` (no false positives, daily-only factors unaffected).

## Deviations

- Added `import pandas as pd` at module top-level rather than importing lazily inside functions. This is necessary because `apply_pit_alignment` takes `pd.DataFrame` as input — pandas is a hard dependency of this module, not optional.
- Used `object.__setattr__(result, "_pit_meta", {...})` to attach metadata to the returned DataFrame, bypassing pandas' attribute-access warning for underscore-prefixed attributes.

## Known Issues

None.

## Files Created/Modified

- `third_party/quantaalpha/quantaalpha/factors/pit_alignment.py` — New PIT alignment core module
- `third_party/quantaalpha/tests/test_pit_alignment.py` — 26 unit tests (3 get_pit_sources + 6 detect_pit_fields + 5 needs_pit_alignment + 7 apply_pit_alignment + 2 diagnostic + 2 reverse index)
- `third_party/quantaalpha/quantaalpha/factors/prompts/experiment.yaml` — Added `pit_alignment:` section
