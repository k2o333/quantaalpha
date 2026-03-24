# S03 Research: P0 配置解锁优化

## Summary

Slice S03 modifies `configs/backtest.yaml` to:
1. Exclude Beijing Stock Exchange (北交所, market code "bj")
2. Activate multi-period backtesting with 4 market-cycle periods

This is a **light research** task — straightforward YAML configuration changes with established patterns.

## Findings

### File: configs/backtest.yaml

**Current state:**
- `data.stock_filter.enabled: false` (disabled)
- `data.stock_filter.exclude_markets: []` (empty)
- `multi_period_validation.enabled: false` (disabled)
- `multi_period_validation.periods: []` (empty)

**Changes required:**
1. Enable stock filter and exclude BJ market
2. Enable multi-period validation with 4 periods

### Market Exclusion Mechanism

From `universe.py`:
- Uses `instrument.rsplit(".", 1)[-1].lower()` to extract market code
- Example: "430001.BJ" → market code "bj"
- `filter_by_market()` filters instruments where `instrument_market_code` matches `exclude_markets`
- Case-insensitive matching via `.lower()`

### Multi-Period Validation Format

From `validation.py`:
- Each period requires: `name`, `train`, `valid`, `test` (each as `[start, end]`)
- Date ranges: `start <= end` enforced
- `fail_fast: true` stops on first failure; `false` runs all periods
- Aggregates metrics across periods for stability score

### Period Design (from S03-PLAN.md)

4 periods covering different Chinese market cycles:
| Period | Train | Valid | Test | Market Context |
|--------|-------|-------|------|----------------|
| 2017_2018_去杠杆 | 2015-2016 | 2017-H1 | 2017-H2-2018 | Deleveraging |
| 2019_2020_结构牛 | 2017-2018 | 2019-H1 | 2019-H2-2020 | Structural bull |
| 2021_2022_震荡熊 | 2019-2020 | 2021-H1 | 2021-H2-2022 | Volatile bear |
| 2023_2025_复苏 | 2021-2022 | 2023-H1 | 2023-H2-2025 | Recovery |

## Verification Commands

```bash
# Verify YAML syntax
python -c "import yaml; yaml.safe_load(open('configs/backtest.yaml'))"

# Check stock filter config
grep -A 4 "stock_filter:" configs/backtest.yaml

# Check multi_period_validation config  
grep -A 30 "multi_period_validation:" configs/backtest.yaml

# Syntax check (py_compile not needed for YAML)
```

## Implementation Approach

**T01: Stock Filter Configuration**
```yaml
data:
  stock_filter:
    enabled: true
    exclude_markets: ["bj"]
    exclude_st: true      # Also exclude ST stocks (good practice)
    min_list_days: 60     # Require 60+ days listing
```

**T02: Multi-Period Validation Configuration**
```yaml
multi_period_validation:
  enabled: true
  fail_fast: false        # Run all periods for full stability assessment
  periods:
    - name: "2017_2018_去杠杆"
      train: ["2015-01-01", "2016-12-31"]
      valid: ["2017-01-01", "2017-06-30"]
      test: ["2017-07-01", "2018-12-31"]
    - name: "2019_2020_结构牛"
      train: ["2017-01-01", "2018-12-31"]
      valid: ["2019-01-01", "2019-06-30"]
      test: ["2019-07-01", "2020-12-31"]
    - name: "2021_2022_震荡熊"
      train: ["2019-01-01", "2020-12-31"]
      valid: ["2021-01-01", "2021-06-30"]
      test: ["2021-07-01", "2022-12-31"]
    - name: "2023_2025_复苏"
      train: ["2021-01-01", "2022-12-31"]
      valid: ["2023-01-01", "2023-06-30"]
      test: ["2023-07-01", "2025-12-26"]
```

## Risks

- **Low**: YAML syntax errors — mitigated by Python yaml.safe_load() validation
- **Low**: Period date ranges overlap with dataset segments — existing code handles gracefully

## Task Order

1. T01: Modify stock_filter section
2. T02: Modify multi_period_validation section  
3. T03: Verify YAML syntax and configuration

No dependencies between T01 and T02 — can be done in parallel.
