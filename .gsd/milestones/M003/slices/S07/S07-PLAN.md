# S07: PIT 对齐执行层 (S6/D013)

**Goal:** Eliminate look-ahead bias in factor computation by enforcing Point-in-Time (PIT) alignment on quarterly financial data loaded in the factor calculation layer.

**Demo:** When `custom_factor_calculator.py` evaluates a factor expression that references a quarterly financial field (e.g. `$roe`), the computed factor values contain no rows where `ann_date > trade_date - lag_days`.

## Must-Haves

- `pit_alignment.py` exposes `apply_pit_alignment()` that filters quarterly data to only include rows where `ann_date <= trade_date - lag_days`, keeping the most recent qualifying row per (symbol, trade_date)
- `needs_pit_alignment()` and `detect_pit_fields()` correctly identify expressions using quarterly fields by reverse-indexing the S01 data capability registry
- `custom_factor_calculator.py` injects PIT-aligned financial columns into the evaluation DataFrame when the expression uses quarterly sources
- `experiment.yaml` contains a `pit_alignment:` configuration section
- Unit tests verify all four core functions (`get_pit_sources`, `apply_pit_alignment`, `detect_pit_fields`, `needs_pit_alignment`) with mock quarterly DataFrames
- Integration test verifies no future-data leak in a `$roe`-based expression on mock Parquet data

## Proof Level

- This slice proves: **contract + integration**
- Real runtime required: no (uses mock DataFrames, no live Qlib/Parquet dependency)
- Human/UAT required: no

## Verification

- `python -m py_compile quantaalpha/factors/pit_alignment.py`
- `python -m py_compile quantaalpha/backtest/custom_factor_calculator.py`
- `python -m py_compile quantaalpha/backtest/factor_calculator.py`
- `pytest quantaalpha/tests/test_pit_alignment.py -v`
- `pytest quantaalpha/tests/test_pit_alignment_integration.py -v`
- `grep -c "pit_alignment" quantaalpha/factors/prompts/experiment.yaml` returns `>= 1`
- `grep "needs_pit_alignment\|apply_pit_alignment" quantaalpha/backtest/custom_factor_calculator.py` returns >= 2 matches
- `grep "needs_pit_alignment\|apply_pit_alignment" quantaalpha/backtest/factor_calculator.py` returns >= 1 match
- Diagnostic check: `_PIT_DIAGNOSTIC_ENABLED=true python -c "import os; os.environ['_PIT_DIAGNOSTIC_ENABLED']='true'; from quantaalpha.factors.pit_alignment import apply_pit_alignment; import pandas as pd; df=apply_pit_alignment(pd.DataFrame({'symbol':['A'],'trade_date':pd.to_datetime('2024-03-28'),'ann_date':pd.to_datetime('2024-02-10'),'roe':[0.12]}),'income_vip',45,'ann_date','trade_date','symbol'); print('PASS' if hasattr(df,'_pit_meta') else 'FAIL')"` → PASS

## Observability / Diagnostics

- Runtime signals: `pit_alignment.py` emits a DEBUG log line when PIT alignment is applied (source name, rows before/after)
- Inspection surfaces: `_PIT_DIAGNOSTIC_ENABLED` env-var (default `False`) when set to `True` causes `apply_pit_alignment()` to attach `_pit_meta` dict to returned DataFrame (rows_before, rows_after, lag_days, source)
- Failure visibility: if a quarterly Parquet file cannot be read, the calculator logs a WARNING and skips PIT alignment for that source (graceful degradation — daily-only factors still compute normally)
- Redaction constraints: no PII or secrets in this slice

## Integration Closure

- Upstream surfaces consumed: S01's `data_capability.py` (already deployed, no changes), `expr_parser.py` `parse_symbol()` (already deployed, no changes)
- New wiring introduced: `apply_pit_alignment()` called inside `calculate_factor()` / `calculate_factors_batch()` in both calculator files; reverse field→source index built from S01's registry at module init
- What remains before the milestone is truly usable end-to-end: real Parquet data loading path (D012 dual-track engine) — S07 provides the alignment enforcement mechanism; the actual Parquet→DataFrame bridge is a separate concern

## Tasks

- [x] **T01: Build `pit_alignment.py` core module and unit tests** `est:30m`
  - Why: The PIT alignment logic is a standalone capability that must be built and tested in isolation before wiring it into the calculators.
  - Files: `quantaalpha/factors/pit_alignment.py`, `quantaalpha/tests/test_pit_alignment.py`, `quantaalpha/factors/prompts/experiment.yaml`
  - Do: Write the module with all functions, add unit tests, add config section to experiment.yaml.
  - Verify: `python -m py_compile pit_alignment.py`, `pytest test_pit_alignment.py -v`, config grep
  - Done when: All 4 core functions implemented, 12+ unit tests pass, config section added

- [x] **T02: Integrate PIT alignment into calculators** `est:20m`
  - Why: The calculators are the injection point where financial data must be PIT-aligned before factor evaluation.
  - Files: `quantaalpha/backtest/custom_factor_calculator.py`, `quantaalpha/backtest/factor_calculator.py`, `quantaalpha/tests/test_pit_alignment_integration.py`
  - Do: Extend both calculator classes to detect quarterly field usage and inject aligned columns; write integration tests.
  - Verify: `python -m py_compile` on both calculators, pytest integration tests pass
  - Done when: Both calculators compile, integration tests pass with no future-data-leak assertions failing

## Files Likely Touched

- `quantaalpha/factors/pit_alignment.py` (new)
- `quantaalpha/tests/test_pit_alignment.py` (new)
- `quantaalpha/tests/test_pit_alignment_integration.py` (new)
- `quantaalpha/backtest/custom_factor_calculator.py` (modify)
- `quantaalpha/backtest/factor_calculator.py` (modify)
- `quantaalpha/factors/prompts/experiment.yaml` (modify)

---
estimated_steps: 12
estimated_files: 6
skills_used:
  - best-practices
  - lint
  - test
  - systematic-debugging
