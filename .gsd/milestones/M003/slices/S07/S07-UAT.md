# S07: PIT 对齐执行层 — UAT Script

**Milestone:** M003
**Slice:** S07 — PIT 对齐执行层 (S6/D013)
**Test Environment:** `third_party/quantaalpha/`
**Preconditions:** Python 3.13+, pytest, pandas installed in current environment

## Pre-flight: Environment Check

```bash
# Verify working directory
pwd  # Should end with .../.gsd/worktrees/M003

# Verify test environment
cd third_party/quantaalpha
python -c "import pandas; print('pandas', pandas.__version__)"
python -c "import pytest; print('pytest', pytest.__version__)"
```

## Test Suite Execution

### TC01: Core Module Syntax Compilation

**Objective:** Verify all PIT alignment modules compile without syntax errors.

```bash
cd third_party/quantaalpha

python -m py_compile quantaalpha/factors/pit_alignment.py
# Expected: exit code 0, no output

python -m py_compile quantaalpha/backtest/custom_factor_calculator.py
# Expected: exit code 0, no output

python -m py_compile quantaalpha/backtest/factor_calculator.py
# Expected: exit code 0, no output
```

**Pass criteria:** All three commands exit with code 0.

---

### TC02: Unit Tests — PIT Alignment Core

**Objective:** Verify all 26 unit tests pass covering the 4 core functions.

```bash
cd third_party/quantaalpha
python -m pytest tests/test_pit_alignment.py -v --tb=short
```

**Expected output:**
```
tests/test_pit_alignment.py::TestGetPitSources::test_returns_only_quarterly PASSED
tests/test_pit_alignment.py::TestGetPitSources::test_empty_registry_returns_empty_dict PASSED
tests/test_pit_alignment.py::TestGetPitSources::test_falls_back_to_module_registry_when_none PASSED
tests/test_pit_alignment.py::TestDetectPitFields::test_single_field PASSED
tests/test_pit_alignment.py::TestDetectPitFields::test_no_duplicates PASSED
tests/test_pit_alignment.py::TestDetectPitFields::test_no_fields PASSED
tests/test_pit_alignment.py::TestDetectPitFields::test_empty_string PASSED
tests/test_pit_alignment.py::TestDetectPitFields::test_unquoted_field_like_text_ignored PASSED
tests/test_pit_alignment.py::TestDetectPitFields::test_numeric_suffix PASSED
tests/test_pit_alignment.py::TestNeedsPitAlignment::test_quarterly_expression PASSED
tests/test_pit_alignment.py::TestNeedsPitAlignment::test_daily_expression PASSED
tests/test_pit_alignment.py::TestNeedsPitAlignment::test_mixed_expression PASSED
tests/test_pit_alignment.py::TestNeedsPitAlignment::test_empty_expression PASSED
tests/test_pit_alignment.py::TestNeedsPitAlignment::test_unknown_field_stays_false PASSED
tests/test_pit_alignment.py::TestApplyPitAlignment::test_filters_correctly PASSED
tests/test_pit_alignment.py::TestApplyPitAlignment::test_keeps_most_recent PASSED
tests/test_pit_alignment.py::TestApplyPitAlignment::test_empty_df_returns_empty_with_same_columns PASSED
tests/test_pit_alignment.py::TestApplyPitAlignment::test_missing_column_raises_keyerror PASSED
tests/test_pit_alignment.py::TestApplyPitAlignment::test_no_qualifying_rows_returns_empty PASSED
tests/test_pit_alignment.py::TestApplyPitAlignment::test_multiple_symbols PASSED
tests/test_pit_alignment.py::TestApplyPitAlignment::test_multiple_value_columns PASSED
tests/test_pit_alignment.py::TestApplyPitAlignment::test_custom_column_names PASSED
tests/test_pit_alignment.py::TestDiagnosticMetadata::test_pit_meta_attached_when_enabled PASSED
tests/test_pit_alignment.py::TestDiagnosticMetadata::test_no_pit_meta_by_default PASSED
tests/test_pit_alignment.py::TestFieldToSourceReverseIndex::test_roe_maps_to_income_vip PASSED
tests/test_pit_alignment.py::TestFieldToSourceReverseIndex::test_close_maps_to_price_volume PASSED
============================== 26 passed in ~0.6s ==============================
```

**Pass criteria:** 26/26 tests pass.

---

### TC03: Integration Tests — Calculator Wiring

**Objective:** Verify 12 integration tests pass covering calculator injection and config.

```bash
cd third_party/quantaalpha
python -m pytest tests/test_pit_alignment_integration.py -v --tb=short
```

**Expected output:**
```
tests/test_pit_alignment_integration.py::TestNoFutureDataLeak::test_inject_aligned_data_filters_future_announcements PASSED
tests/test_pit_alignment_integration.py::TestNoFutureDataLeak::test_roe_column_stripped_of_dollar_sign PASSED
tests/test_pit_alignment_integration.py::TestDailyOnlyExpression::test_needs_pit_alignment_returns_false_for_daily_expression PASSED
tests/test_pit_alignment_integration.py::TestDailyOnlyExpression::test_inject_pit_aligned_data_logs_debug_for_daily_expression PASSED
tests/test_pit_alignment_integration.py::TestGracefulDegradation::test_calculate_factor_with_unavailable_quarterly_data_does_not_raise PASSED
tests/test_pit_alignment_integration.py::TestGracefulDegradation::test_factor_calculator_handles_missing_quarterly_data PASSED
tests/test_pit_alignment_integration.py::TestPitConfigFromExperimentYaml::test_experiment_yaml_contains_pit_alignment_enabled PASSED
tests/test_pit_alignment_integration.py::TestPitConfigFromExperimentYaml::test_experiment_yaml_default_lag_days_is_45 PASSED
tests/test_pit_alignment_integration.py::TestPitConfigFromExperimentYaml::test_experiment_yaml_has_pit_alignment_section PASSED
tests/test_pit_alignment_integration.py::TestCalculatorMethodsPresent::test_custom_factor_calculator_has_load_and_inject_methods PASSED
tests/test_pit_alignment_integration.py::TestCalculatorMethodsPresent::test_factor_calculator_has_load_and_inject_methods PASSED
tests/test_pit_alignment_integration.py::TestCalculatorMethodsPresent::test_pit_alignment_methods_called_in_calculate_factor PASSED
============================== 12 passed in ~0.7s ==============================
```

**Pass criteria:** 12/12 tests pass.

---

### TC04: Diagnostic Metadata — `_PIT_DIAGNOSTIC_ENABLED`

**Objective:** Verify that setting `_PIT_DIAGNOSTIC_ENABLED=true` causes `apply_pit_alignment()` to attach `_pit_meta` to the returned DataFrame.

```bash
cd third_party/quantaalpha
_PIT_DIAGNOSTIC_ENABLED=true python -c "
import os
os.environ['_PIT_DIAGNOSTIC_ENABLED'] = 'true'
from quantaalpha.factors.pit_alignment import apply_pit_alignment
import pandas as pd

df = apply_pit_alignment(
    pd.DataFrame({
        'symbol': ['A'],
        'trade_date': pd.to_datetime('2024-03-28'),
        'ann_date': pd.to_datetime('2024-02-10'),
        'roe': [0.12]
    }),
    'income_vip', 45, 'ann_date', 'trade_date', 'symbol'
)

if hasattr(df, '_pit_meta'):
    print('PASS: _pit_meta attached')
    print('Metadata:', df._pit_meta)
else:
    print('FAIL: _pit_meta not attached')
"
```

**Expected output:**
```
PASS: _pit_meta attached
Metadata: {'rows_before': 1, 'rows_after': 1, 'lag_days': 45, 'source': 'income_vip'}
```

**Pass criteria:** `_pit_meta` is attached with correct keys.

---

### TC05: Grep Verification — Integration Points

**Objective:** Verify PIT functions are referenced in both calculator files and config.

```bash
cd third_party/quantaalpha

# TC05a: custom_factor_calculator.py should reference needs_pit_alignment/apply_pit_alignment
grep -c "needs_pit_alignment\|apply_pit_alignment" quantaalpha/backtest/custom_factor_calculator.py
# Expected: >= 2

# TC05b: factor_calculator.py should reference needs_pit_alignment/apply_pit_alignment
grep -c "needs_pit_alignment\|apply_pit_alignment" quantaalpha/backtest/factor_calculator.py
# Expected: >= 1

# TC05c: experiment.yaml should have pit_alignment section
grep -c "pit_alignment" quantaalpha/factors/prompts/experiment.yaml
# Expected: >= 1
```

**Pass criteria:** All three grep counts meet or exceed the minimum thresholds.

---

### TC06: Config Section — experiment.yaml

**Objective:** Verify the `pit_alignment:` configuration section exists and has correct values.

```bash
cd third_party/quantaalpha
python -c "
import yaml

with open('quantaalpha/factors/prompts/experiment.yaml') as f:
    cfg = yaml.safe_load(f)

pit = cfg.get('pit_alignment', {})
assert pit.get('enabled') == True, 'pit_alignment.enabled should be True'
assert pit.get('default_lag_days') == 45, 'pit_alignment.default_lag_days should be 45'
assert 'source_overrides' in pit, 'pit_alignment should have source_overrides'
print('PASS: experiment.yaml pit_alignment section is correct')
"
```

**Pass criteria:** All assertions pass.

---

## Edge Case Tests (Manual Verification)

### EC01: Empty DataFrame Handling

```bash
cd third_party/quantaalpha
python -c "
from quantaalpha.factors.pit_alignment import apply_pit_alignment
import pandas as pd

# Empty input should return empty DataFrame with same columns
df = apply_pit_alignment(
    pd.DataFrame({'symbol': [], 'trade_date': [], 'ann_date': [], 'roe': []}),
    'income_vip', 45, 'ann_date', 'trade_date', 'symbol'
)
assert df.empty, 'Empty input should return empty DataFrame'
assert list(df.columns) == ['symbol', 'trade_date', 'roe'], 'Columns should be preserved'
print('EC01 PASS: Empty DataFrame handled correctly')
"
```

### EC02: Missing Join Keys Graceful Degradation

```bash
cd third_party/quantaalpha
python -c "
from quantaalpha.factors.pit_alignment import apply_pit_alignment
import pandas as pd

# Missing required column should raise KeyError
try:
    df = apply_pit_alignment(
        pd.DataFrame({'symbol': ['A'], 'trade_date': ['2024-03-28']}),
        'income_vip', 45, 'ann_date', 'trade_date', 'symbol'
    )
    print('EC02 FAIL: Should have raised KeyError')
except KeyError as e:
    print('EC02 PASS: KeyError raised for missing column:', str(e)[:80])
"
```

### EC03: Multiple Symbols

```bash
cd third_party/quantaalpha
python -c "
from quantaalpha.factors.pit_alignment import apply_pit_alignment
import pandas as pd

# Two symbols with different announcement dates
df = apply_pit_alignment(
    pd.DataFrame({
        'symbol': ['A', 'A', 'B', 'B'],
        'trade_date': ['2024-03-28'] * 4,
        'ann_date': ['2024-02-10', '2024-03-01', '2024-02-10', '2024-03-01'],
        'roe': [0.10, 0.12, 0.15, 0.18]
    }),
    'income_vip', 45, 'ann_date', 'trade_date', 'symbol'
)
assert len(df) == 2, f'Should have 2 rows (one per symbol), got {len(df)}'
assert set(df['symbol']) == {'A', 'B'}, 'Both symbols should be present'
print('EC03 PASS: Multiple symbols handled correctly')
"
```

### EC04: Daily Expression Bypasses PIT

```bash
cd third_party/quantaalpha
python -c "
from quantaalpha.factors.pit_alignment import needs_pit_alignment

# Daily-only expression should return False
result = needs_pit_alignment('RANK(TS_PCTCHANGE(\$close, 10))')
assert result == False, f'Daily expression should return False, got {result}'
print('EC04 PASS: Daily expression bypasses PIT check')
"
```

---

## UAT Summary

| Test Case | Category | Result |
|-----------|----------|--------|
| TC01: Module compilation | Contract | ✅ Pass |
| TC02: 26 unit tests | Contract | ✅ 26/26 Pass |
| TC03: 12 integration tests | Integration | ✅ 12/12 Pass |
| TC04: Diagnostic metadata | Observability | ✅ Pass |
| TC05: Grep verification | Contract | ✅ Pass |
| TC06: Config section | Configuration | ✅ Pass |
| EC01: Empty DataFrame | Edge Case | ✅ Pass |
| EC02: Missing keys | Edge Case | ✅ Pass |
| EC03: Multiple symbols | Edge Case | ✅ Pass |
| EC04: Daily bypass | Edge Case | ✅ Pass |

**Overall UAT Result: ✅ PASS**

All required and edge case tests pass. The PIT alignment execution layer is ready for integration with D012 (Parquet dual-track engine).
