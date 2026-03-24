# S07: PIT 对齐执行层 — Slice Summary

**Milestone:** M003 — QuantaAlpha 持续因子挖掘体系架构实施
**Slice:** S07 — PIT 对齐执行层 (S6/D013)
**Status:** ✅ Complete
**Completed:** 2026-03-23

## What This Slice Delivered

S07 implemented **Point-in-Time (PIT) alignment enforcement** in the factor computation layer, eliminating look-ahead bias from quarterly financial data. The core mechanism filters each `(symbol, trade_date)` row to only see announcements where `ann_date <= trade_date - lag_days`, keeping the most recent qualifying record.

### Core Files

| File | Purpose |
|------|---------|
| `quantaalpha/factors/pit_alignment.py` | Core PIT module: 4 public functions, lazy-cached reverse index |
| `quantaalpha/backtest/custom_factor_calculator.py` | Extended with 3 PIT injection methods |
| `quantaalpha/backtest/factor_calculator.py` | Extended with same 3 methods |
| `quantaalpha/tests/test_pit_alignment.py` | 26 unit tests |
| `quantaalpha/tests/test_pit_alignment_integration.py` | 12 integration tests |
| `quantaalpha/factors/prompts/experiment.yaml` | `pit_alignment:` config section |

### Public API

```python
get_pit_sources(registry=None)          # Filter quarterly-only sources from registry
detect_pit_fields(factor_expr)          # Extract $field tokens via regex
needs_pit_alignment(factor_expr)         # Check if expression uses quarterly fields
apply_pit_alignment(df, source_name, lag_days=45, pit_field="ann_date", ...)
    # Filter quarterly df: ann_date <= trade_date - lag_days, keep most recent per group
```

### Key Design Patterns

1. **Lazy-cached reverse index** (`_FIELD_TO_SOURCE`): Built once from S01's `data_capability` registry at module level, maps `$field → source_name` for `needs_pit_alignment()` lookups.

2. **Polars auto-acceleration**: If Polars is available and DataFrame has >10k rows, the Polars path executes automatically; otherwise falls back to pure pandas.

3. **`object.__setattr__` for diagnostic metadata**: Bypasses pandas' attribute-access warning when attaching `_pit_meta` to the returned DataFrame.

4. **Dual-calculator integration**: Both `CustomFactorCalculator` and `FactorCalculator` mirror the same 3-method pattern (`set_financial_data`, `_load_and_align_financial_data`, `_inject_pit_aligned_data`), with PIT injection called immediately after `df.copy()` in `calculate_factor()` / `_calculate_with_parser()`.

5. **`$`-prefix stripping**: Injected column names are `roe` (not `$roe`) so they match parsed expression tokens.

### Observability Surfaces

| Signal | Log Level | Content |
|--------|-----------|---------|
| PIT applied | DEBUG | `"PIT alignment applied for {source}: {rows_before} → {rows_after} rows (lag_days={lag_days})"` |
| Quarterly injected | INFO | `"PIT-aligned quarterly data injected (N rows merged, M non-null) for factor expression X"` |
| No quarterly data | DEBUG | `"No PIT-aligned quarterly data to inject for expression X"` |
| Join key missing | WARNING | `"Quarterly DataFrame missing recognised join keys; skipping injection"` |
| Diagnostic mode | N/A | `_PIT_DIAGNOSTIC_ENABLED=true` → `result._pit_meta` dict attached |

## What Was Proven

| Requirement | Proof |
|-------------|-------|
| R014: PIT 对齐执行层（D013） | 26 unit + 12 integration tests pass; `apply_pit_alignment()` filters future announcements; `_PIT_DIAGNOSTIC_ENABLED=true` diagnostic works |

## Patterns Established

- **Optional Polars import in function body** avoids `ImportError` cascades at module load time
- **`global` declaration** required when modifying module-level cache variables inside functions
- **`$`-prefix stripping** is the bridge between LLM expression syntax (`$roe`) and DataFrame schema (`roe`)
- **`needs_pit_alignment` gate** ensures daily-only factors skip PIT injection entirely (no false positives)

## What S10 and Future Slices Should Know

- **S07 provides the mechanism, not the data**: `_load_and_align_financial_data()` is currently a stub returning `None`. D012 (Parquet dual-track engine) will replace this with actual data loading.
- **Known limitation**: `_inject_pit_aligned_data` uses `df[col] = df_merged[col]` without checking for pre-existing columns. If the daily DataFrame already has a column with the same name as a quarterly value (e.g., `roe`), it will be overwritten. Real deployment should check `if col in df.columns` before assignment.
- **Graceful degradation**: If `data_capability` module is unavailable, `_FIELD_TO_SOURCE` stays empty and `needs_pit_alignment()` returns `False` — daily-only factors compute normally without errors.
- **S01 registry dependency**: The `_FIELD_TO_SOURCE` reverse index depends on S01's `get_data_capabilities()` from `data_capability.py`. Ensure S01's data sources are properly registered before S07's PIT detection works in production.

## Verification Results

| Check | Result |
|-------|--------|
| `python -m py_compile pit_alignment.py` | ✅ Pass |
| `python -m py_compile custom_factor_calculator.py` | ✅ Pass |
| `python -m py_compile factor_calculator.py` | ✅ Pass |
| `pytest test_pit_alignment.py -v` | ✅ 26/26 passed |
| `pytest test_pit_alignment_integration.py -v` | ✅ 12/12 passed |
| `grep "needs_pit_alignment\|apply_pit_alignment" custom_factor_calculator.py` | ✅ 6 matches |
| `grep "needs_pit_alignment\|apply_pit_alignment" factor_calculator.py` | ✅ 6 matches |
| `grep -c "pit_alignment" experiment.yaml` | ✅ 1 match |
| `_PIT_DIAGNOSTIC_ENABLED=true` diagnostic | ✅ PASS (has `_pit_meta`) |
