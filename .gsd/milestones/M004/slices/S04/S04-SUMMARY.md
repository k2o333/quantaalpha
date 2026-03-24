---
id: S04
parent: M004
milestone: M004
provides:
  - data_capability.py: available_from + join_mode + auto_discover_capabilities()
  - test_data_capability_extensions.py: 26 passing tests
requires: []
affects:
  - R010 (data capability registry extension — now validated)
key_files:
  - quantaalpha/factors/data_capability.py
  - quantaalpha/tests/test_data_capability_extensions.py
key_decisions:
  - join_mode inferred from freq when not explicitly set (freq → join_mode mapping)
  - available_from=None treated as "(unknown)" in rendered output (not omitted)
  - auto_discover_capabilities() is additive: existing hardcoded dates preserved, only new fields populated
patterns_established:
  - Defensive parquet reading: try/except around polars calls, return None on failure
  - Explicit override pattern: explicit value > inferred value in normalization
observability_surfaces:
  - render_data_capabilities() output (visible in LLM prompts)
  - get_data_capabilities() registry structure
  - pytest quantaalpha/tests/test_data_capability_extensions.py
drill_down_paths:
  - tasks/T01-SUMMARY.md
  - tasks/T02-SUMMARY.md
duration: 35m
verification_result: passed
completed_at: 2026-03-24
---

# S04: 数据能力注册表扩展

**数据注册表新增 available_from + join_mode，LLM 可感知数据起始日期和连接方式。**

## What Happened

S04 extends the data capability registry from M003 S01 with two new fields that help the LLM understand data availability constraints:

1. **`available_from`** — the earliest date for which data is available. Hardcoded in `DATA_CAPABILITIES` for known datasets (price_volume: 2010-01-01, financial: 2008-01-01), dynamically discoverable via `auto_discover_capabilities()` which reads Parquet earliest row date.

2. **`join_mode`** — how to align the capability with the main time series. Inferred from `freq` when not set: daily/weekly → `same_day`, quarterly/monthly/annual → `forward_fill`. Explicit values override the inference.

The rendering output now includes both fields in the LLM prompt context, e.g.:
```
- financial: fields=$roa,...; freq=quarterly; lag_days=45;
  available_from=2008-01-01; join_mode=forward_fill; typical_uses=quality, value
```

Two tasks completed: T01 extended the module, T02 created 26 unit tests covering normalization, inference, rendering, and defensive behavior.

## Verification

- `python -m py_compile quantaalpha/factors/data_capability.py` → 0 (PASS)
- `grep -c "available_from" quantaalpha/factors/data_capability.py` → 13 (PASS)
- `grep -c "join_mode" quantaalpha/factors/data_capability.py` → 9 (PASS)
- `grep -c "auto_discover_capabilities" quantaalpha/factors/data_capability.py` → 1 (PASS)
- `pytest quantaalpha/tests/test_data_capability_extensions.py` → 26 passed in 0.19s (PASS)

## New Requirements Surfaced

(none)

## Deviations

- **No `auto_discover_capabilities()` existed** — the plan assumed S01 had already implemented this function but it did not. T01 implemented it from scratch. This was a gap between the plan's assumption and the actual S01 deliverable.

## Known Limitations

- **`available_from` is hardcoded for known datasets** — `auto_discover_capabilities()` exists but hasn't been exercised with real Parquet files. When real data directories are connected, verify the inferred dates are correct.
- **Polars is a runtime dependency** — `infer_available_from_from_parquet()` uses polars; if unavailable it returns None silently. Consider adding a fallback using pandas.

## Follow-ups

- Wire `auto_discover_capabilities()` into the data pipeline startup so LLM context reflects actual data availability

## Files Created/Modified

- `quantaalpha/factors/data_capability.py` — added `available_from`, `join_mode` (freq-inferred), `auto_discover_capabilities()`, `infer_available_from_from_parquet()`, `_FREQ_TO_JOIN_MODE` mapping
- `quantaalpha/tests/test_data_capability_extensions.py` — 26 tests across 6 test classes

## Forward Intelligence

### What the next slice should know

- `render_data_capabilities()` is the primary integration point for LLM prompts — any new fields added to the capability spec should be included there
- The `_FREQ_TO_JOIN_MODE` mapping at the top of `data_capability.py` is the canonical place to update default join modes when new freq values are added

### What's fragile

- `infer_available_from_from_parquet()` silently returns None on any exception — if polars is misconfigured or the parquet is corrupted, this won't surface in logs. Add a warning log when this matters.

### Authoritative diagnostics

```bash
python -c "from quantaalpha.factors.data_capability import render_data_capabilities; print(render_data_capabilities())"
```

### What assumptions changed

- **Assumption**: S01 already had `auto_discover_capabilities()`. **Reality**: It did not — the function was implemented in S04. The S01 deliverable was the hardcoded registry with `join_mode` already in it.
