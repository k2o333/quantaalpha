# T02: Integrate PIT alignment into calculators

**Slice:** S07 — PIT 对齐执行层 (S6/D013)
**Milestone:** M003

## Description

Wire `pit_alignment.py` into both `custom_factor_calculator.py` and `factor_calculator.py` so that factor expressions referencing quarterly financial fields automatically load and PIT-align the corresponding Parquet data before evaluation. The integration is additive: if no quarterly fields are used, the calculators behave exactly as before.

## Steps

1. **Read the current `custom_factor_calculator.py`** to understand the full `calculate_factor()` and `calculate_factors_batch()` methods. Pay particular attention to how `data_df` is prepared and how columns are injected before `eval()`.

2. **Add a helper method `_load_and_align_financial_data(expr)`** to `CustomFactorCalculator`:

   ```python
   def _load_and_align_financial_data(self, factor_expr: str) -> pd.DataFrame | None:
       """Load and PIT-align financial Parquet data needed by factor_expr.

       Returns a DataFrame with columns [symbol, trade_date, ann_date, $field1, ...]
       or None if no quarterly data is needed.
       """
       try:
           from quantaalpha.factors.pit_alignment import needs_pit_alignment, apply_pit_alignment
       except ImportError:
           return None  # graceful degradation

       if not needs_pit_alignment(factor_expr):
           return None

       # TODO: real Parquet loading (D012 dual-track engine)
       # For now: return None to indicate quarterly data not available
       # The integration test will use a mock approach
       return None
   ```

   This method is the integration point. Its current implementation is a no-op stub that returns `None`. A follow-up slice will implement the actual Parquet loading. The integration test will directly inject mock Parquet data via a `set_financial_data()` method.

3. **Modify `calculate_factor()`** in `CustomFactorCalculator`:
   - After `df = self.data_df.copy()`, call `self._inject_pit_aligned_data(df, factor_expression)`
   - The injection method (new helper, defined in step 4) merges PIT-aligned quarterly columns into `df` if `needs_pit_alignment()` returns `True`
   - Columns are injected with their bare field names (no source prefix) so they match the `$field` syntax in expressions after `parse_symbol()` strips the `$`

4. **Add helper method `_inject_pit_aligned_data(df, factor_expr)`**:
   - Calls `_load_and_align_financial_data(factor_expr)`
   - If it returns a DataFrame with quarterly data, performs a left join on `[symbol, trade_date]` to merge quarterly columns into `df`
   - Logs INFO: `"PIT-aligned quarterly data injected ({n} rows) for factor expression"`
   - If quarterly data is not available (returns None), logs DEBUG and skips injection — no error

5. **Modify `calculate_factors_batch()`**:
   - Before computing each factor, call `_inject_pit_aligned_data(self.data_df, factor_expr)` to ensure the DataFrame is prepared for the upcoming `calculate_factor()` call
   - This is a one-time preparation before the batch loop (not per-factor) to avoid redundant checks

6. **Read `factor_calculator.py`** (in `quantaalpha/backtest/`):
   - Locate the equivalent entry points: `_calculate_with_parser()` or the method that builds the evaluation DataFrame
   - Apply the same PIT injection pattern in those methods using `needs_pit_alignment()` + `_load_and_align_financial_data()` + `_inject_pit_aligned_data()`

7. **Create integration tests in `quantaalpha/tests/test_pit_alignment_integration.py`**:

   Use a monkeypatch/mock approach so no real Parquet files or Qlib connection is needed:

   a. `test_no_future_data_leak_in_quarterly_expression`:
      - Patch `_load_and_align_financial_data()` on a `CustomFactorCalculator` instance to return a pre-built mock quarterly DataFrame:
        ```
        symbol  trade_date  ann_date   roe
        A       2024-03-28 2024-03-20  0.10   ← future data (should be filtered)
        A       2024-03-28 2024-02-10  0.12   ← should be used
        A       2024-01-30 2024-01-31  0.08   ← old data
        ```
      - Call `calculator._inject_pit_aligned_data(df, "$roe")`
      - Assert that the injected `$roe` column contains only `0.12` (not `0.10`) for the 2024-03-28 row

   b. `test_calculator_skips_injection_for_daily_only_expression`:
      - Set up a calculator with mock data (no quarterly)
      - Call with `"RANK(-1 * TS_PCTCHANGE($close, 10))"`
      - Assert `needs_pit_alignment()` returns `False`
      - Assert injection path logs DEBUG (no INFO)

   c. `test_calculator_graceful_degradation_no_quarterly_data`:
      - `CustomFactorCalculator` with `_load_and_align_financial_data()` returning `None`
      - Call `calculate_factor()` with `"$roe"` expression
      - Assert it does NOT raise an error (graceful degradation — quarterly data simply unavailable)
      - Assert it logs a WARNING about missing quarterly data

   d. `test_pit_config_loaded_from_experiment_yaml`:
      - Load the `experiment.yaml` config
      - Assert `pit_alignment.enabled == True` and `pit_alignment.default_lag_days == 45`

## Must-Haves

- [ ] `CustomFactorCalculator` has `_load_and_align_financial_data()` and `_inject_pit_aligned_data()` methods
- [ ] `calculate_factor()` calls `_inject_pit_aligned_data()` before evaluating the expression
- [ ] `calculate_factors_batch()` prepares PIT data before the batch loop
- [ ] `FactorCalculator` in `factor_calculator.py` has the same injection pattern applied to its expression evaluation path
- [ ] Integration test verifies no future-data leak: `$roe` with `ann_date=2024-03-20` must not appear for `trade_date=2024-03-28` with `lag_days=45`
- [ ] Graceful degradation: if quarterly data is unavailable, calculators continue to work (no crash)
- [ ] Both calculators compile without errors

## Verification

```bash
cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M003/third_party/quantaalpha
python -m py_compile quantaalpha/backtest/custom_factor_calculator.py
python -m py_compile quantaalpha/backtest/factor_calculator.py
pytest quantaalpha/tests/test_pit_alignment_integration.py -v
grep -c "needs_pit_alignment\|apply_pit_alignment" quantaalpha/backtest/custom_factor_calculator.py
# must return >= 2
grep -c "needs_pit_alignment\|apply_pit_alignment" quantaalpha/backtest/factor_calculator.py
# must return >= 1
```

## Observability Impact

This task introduces the following observable signals:

| Signal | Source | What changes |
|--------|--------|-------------|
| **INFO log** | `CustomFactorCalculator._inject_pit_aligned_data` / `FactorCalculator._inject_pit_aligned_data` | Emitted when quarterly data is successfully merged; includes merged row count and non-null count |
| **DEBUG log** | `_inject_pit_aligned_data` | Emitted when no quarterly data is available or when injection is skipped for daily-only expressions |
| **`_PIT_DIAGNOSTIC_ENABLED=true`** | Environment variable | Causes `apply_pit_alignment()` to attach `._pit_meta` dict (`rows_before`, `rows_after`, `lag_days`, `source`) to returned DataFrame; inspectable at runtime |
| **Failure path** | `_load_and_align_financial_data()` | Returns `None` when quarterly Parquet data unavailable → `_inject_pit_aligned_data` logs DEBUG and skips; calculator continues without crashing |

**Failure visibility:** If `_load_and_align_financial_data()` returns `None` (quarterly data unavailable), the calculators log a DEBUG message and proceed normally — no exception propagates. Daily-only factor computation is unaffected.

**How a future agent inspects:** Set `_PIT_DIAGNOSTIC_ENABLED=true` and examine `result._pit_meta` on any returned DataFrame from a quarterly factor expression to confirm rows_before > rows_after (PIT filter was active).

**No PII or secrets:** No user data, credentials, or PII are emitted in any log line added by this task.

## Inputs

- `third_party/quantaalpha/quantaalpha/factors/pit_alignment.py` — output of T01
- `third_party/quantaalpha/quantaalpha/backtest/custom_factor_calculator.py` — calculator to extend
- `third_party/quantaalpha/quantaalpha/backtest/factor_calculator.py` — parallel calculator to extend
- `third_party/quantaalpha/quantaalpha/tests/test_data_capability_registry.py` — S01 test pattern to follow

## Expected Output

- `third_party/quantaalpha/quantaalpha/backtest/custom_factor_calculator.py` — PIT injection added
- `third_party/quantaalpha/quantaalpha/backtest/factor_calculator.py` — PIT injection added
- `third_party/quantaalpha/tests/test_pit_alignment_integration.py` — integration tests (4 test cases)
