# T01: Build `pit_alignment.py` core module and unit tests

**Slice:** S07 — PIT 对齐执行层 (S6/D013)
**Milestone:** M003

## Description

Build the `pit_alignment.py` module that provides Point-in-Time (PIT) alignment for quarterly financial DataFrames. This module:
1. Builds a reverse index from S01's data capability registry: `$field_name → source_name`
2. Detects whether a factor expression uses quarterly fields
3. Applies PIT filtering to a quarterly DataFrame so each `(symbol, trade_date)` only sees rows where `ann_date <= trade_date - lag_days`, keeping the most recent qualifying row

Also adds the `pit_alignment:` section to `experiment.yaml`.

## Steps

1. **Create `pit_alignment.py`** in `quantaalpha/factors/` with the following:

   a. **Imports and constants** — standard library only; `logging` for diagnostics; `polars` optional import inside functions

   b. **`_FIELD_TO_SOURCE: dict[str, str]`** — module-level reverse index built lazily at first call. Maps `$field_name → source_name` by iterating the S01 registry (`DATA_CAPABILITIES` fallback). Example: `"$roe" → "income_vip"`. Built once and cached in a module-level variable.

   c. **`get_pit_sources(registry: dict | None = None) → dict[str, dict]`** — return only sources where `freq == "quarterly"` (uses `get_data_capabilities()` from S01 as fallback). Filters the registry dict to entries with `freq == "quarterly"`.

   d. **`detect_pit_fields(factor_expr: str) → list[str]`** — extract all `$field` references from a factor expression using `re.findall(r'\$[a-zA-Z_][a-zA-Z0-9_]*', factor_expr)`. Return the list of unique field names including the `$` prefix.

   e. **`needs_pit_alignment(factor_expr: str) → bool`** — call `detect_pit_fields()` then check if any detected field maps (via `_FIELD_TO_SOURCE`) to a source in `get_pit_sources()`. Returns `True` if at least one quarterly source is referenced.

   f. **`_apply_pit_alignment_pandas(...)`** — internal Pandas implementation:
      ```
      Given df with columns: [symbol, trade_date, ann_date, +value_cols]
      1. Compute cutoff = trade_date - lag_days (pd.Timedelta)
      2. Filter: ann_date <= cutoff
      3. Sort by ann_date descending
      4. groupby(symbol, trade_date).first()
      5. Reset index so columns become [symbol, trade_date, value_col1, ...]
      6. Return filtered df
      ```

   g. **`_apply_pit_alignment_polars(...)`** — internal Polars implementation (used if Polars is available):
      ```
      Given lf (Polars LazyFrame) with columns: [symbol, trade_date, ann_date, +value_cols]
      1. filter(pl.col('ann_date') <= pl.col('trade_date') - pl.duration(days=lag_days))
      2. sort('ann_date', descending=True)
      3. group_by(['symbol', 'trade_date']).first()
      4. collect()
      ```

   h. **`apply_pit_alignment(df: pd.DataFrame, source_name: str, lag_days: int = 45, pit_field: str = "ann_date", trade_date_field: str = "trade_date", symbol_field: str = "symbol") → pd.DataFrame`** — public entry point:
      - If Polars is available and df has >10k rows, delegate to `_apply_pit_alignment_polars()`
      - Otherwise use `_apply_pit_alignment_pandas()`
      - Defensive checks: return empty df with original columns if df is empty; validate columns exist
      - Log DEBUG: `"PIT alignment applied for {source_name}: {rows_before} → {rows_after} rows"`
      - If `_PIT_DIAGNOSTIC_ENABLED` env var is `"true"`, attach `._pit_meta = {"rows_before": ..., "rows_after": ..., "lag_days": ..., "source": source_name}` to returned DataFrame

   i. **`__all__`** — `["get_pit_sources", "detect_pit_fields", "needs_pit_alignment", "apply_pit_alignment"]`

2. **Add unit tests in `quantaalpha/tests/test_pit_alignment.py`**:

   Test the following scenarios using `pandas.DataFrame` mock data (no real Parquet files):

   a. `test_get_pit_sources_returns_only_quarterly` — call `get_pit_sources()` with a mixed registry and assert all returned sources have `freq == "quarterly"`

   b. `test_detect_pit_fields_single_field` — `detect_pit_fields("$roe / $revenue")` → `["$roe", "$revenue"]`

   c. `test_detect_pit_fields_no_fields` — `detect_pit_fields("RANK($close / $open)")` → `["$close", "$open"]` (daily-only fields)

   d. `test_needs_pit_alignment_quarterly` — `needs_pit_alignment("$roe")` → `True` (roe is quarterly in the fallback registry)

   e. `test_needs_pit_alignment_daily` — `needs_pit_alignment("RANK(-1 * TS_PCTCHANGE($close, 10))")` → `False`

   f. `test_apply_pit_alignment_filters_correctly` — create a mock quarterly df:
      ```
      symbol  trade_date  ann_date  roe
      A       2024-03-28  2024-03-20  0.10   ← ann_date <= 2024-03-28 - 45d = 2024-02-12 → NO
      A       2024-03-28  2024-02-10  0.12   ← ann_date <= 2024-02-12 → YES (kept, most recent)
      A       2024-03-28  2024-01-30  0.08   ← ann_date <= 2024-02-12 → YES (dropped)
      ```
      After PIT with lag_days=45, assert exactly 1 row for (A, 2024-03-28) with `roe=0.12`

   g. `test_apply_pit_alignment_keeps_most_recent` — when multiple rows qualify, the one with max ann_date is kept

   h. `test_apply_pit_alignment_empty_df` — call on empty df, assert returns empty df with same columns

   i. `test_apply_pit_alignment_missing_columns` — call with non-existent column, assert raises `KeyError`

   j. `test_apply_pit_alignment_no_qualifying_rows` — if no rows satisfy `ann_date <= cutoff`, return empty df (not an error)

   k. `test_pit_alignment_diagnostic_metadata` — with `_PIT_DIAGNOSTIC_ENABLED=true`, assert returned df has `._pit_meta` attribute

   l. `test_needs_pit_alignment_mixed_expression` — `"$roe + RANK($close)"` → `True` (roe is quarterly, even though close is not)

3. **Add `pit_alignment:` section to `quantaalpha/factors/prompts/experiment.yaml`**:

   Append at the end of the YAML file:
   ```yaml
   pit_alignment:
     enabled: true
     default_lag_days: 45
     # Per-source lag overrides (optional)
     source_overrides:
       forecast_vip:
         lag_days: 15
   ```

## Must-Haves

- [ ] `pit_alignment.py` has all 4 public functions: `get_pit_sources`, `detect_pit_fields`, `needs_pit_alignment`, `apply_pit_alignment`
- [ ] `_FIELD_TO_SOURCE` reverse index correctly maps `$roe → income_vip` using S01 registry
- [ ] `apply_pit_alignment()` uses Pandas for ≤10k rows, Polars for >10k rows (Polars is optional)
- [ ] Defensive checks: empty df, missing columns, no qualifying rows — all handled gracefully
- [ ] `_PIT_DIAGNOSTIC_ENABLED` env-var triggers `._pit_meta` attachment
- [ ] 12+ unit tests covering all functions and edge cases
- [ ] `experiment.yaml` has `pit_alignment:` section with `enabled`, `default_lag_days`

## Verification

```bash
cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M003/third_party/quantaalpha
python -m py_compile quantaalpha/factors/pit_alignment.py
pytest quantaalpha/tests/test_pit_alignment.py -v
grep -c "pit_alignment:" quantaalpha/factors/prompts/experiment.yaml
# must return >= 1
```

## Inputs

- `third_party/quantaalpha/quantaalpha/factors/data_capability.py` — S01 registry (used to build `_FIELD_TO_SOURCE` reverse index)
- `third_party/quantaalpha/quantaalpha/factors/prompts/experiment.yaml` — config file to extend

## Expected Output

- `third_party/quantaalpha/quantaalpha/factors/pit_alignment.py` — new PIT alignment module
- `third_party/quantaalpha/tests/test_pit_alignment.py` — unit tests (12+ test cases)
- `third_party/quantaalpha/quantaalpha/factors/prompts/experiment.yaml` — `pit_alignment:` section added
