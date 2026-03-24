---
id: T01
parent: S03
milestone: M003
provides:
  - Stock filter enabled with BJ exchange exclusion
  - Multi-period validation enabled with 4 market-cycle periods
  - Observability/diagnostics sections added to slice plan
key_files:
  - third_party/quantaalpha/configs/backtest.yaml
key_decisions:
  - Excluded BJ exchange to improve factor evaluation reliability
  - Added exclude_st=true and min_list_days=60 for additional quality filtering
  - Configured 4 periods covering 2017-2025 market cycles (deleveraging, structural bull, volatile bear, recovery)
patterns_established:
  - Configuration-driven market cycle validation
observability_surfaces:
  - None (configuration-only change, no runtime signals)
duration: 5m
verification_result: passed
completed_at: 2026-03-23T19:16:00+08:00
blocker_discovered: false
---

# T01: 配置股票过滤排除北交所

**Enabled stock filtering to exclude Beijing Stock Exchange (北交所) and activated multi-period validation with 4 market-cycle periods**

## What Happened

Configured `third_party/quantaalpha/configs/backtest.yaml` to enable stock filtering and exclude the Beijing Stock Exchange (market code "bj"). Also enabled multi-period validation with 4 market-cycle periods covering 2017-2025. Added recommended optional settings: `exclude_st=true` to filter ST stocks and `min_list_days=60` to require minimum listing days.

Additionally addressed pre-flight notes by adding `## Observability / Diagnostics` and `## Diagnostics / Failure-Path Checks` sections to S03-PLAN.md to document runtime inspection points and failure detection methods.

## Verification

Ran comprehensive Python assertions to verify all configuration values are correctly set:
- `stock_filter.enabled` = true
- `stock_filter.exclude_markets` = ["bj"]
- `stock_filter.exclude_st` = true
- `stock_filter.min_list_days` = 60
- `multi_period_validation.enabled` = true
- `multi_period_validation.periods` count = 4

All assertions passed successfully.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -c "import yaml; yaml.safe_load(open('third_party/quantaalpha/configs/backtest.yaml'))"` | 0 | ✅ pass | <1s |
| 2 | `grep -A 5 "stock_filter:" third_party/quantaalpha/configs/backtest.yaml` | 0 | ✅ pass | <1s |
| 3 | `grep -A 18 "multi_period_validation:" third_party/quantaalpha/configs/backtest.yaml` | 0 | ✅ pass | <1s |
| 4 | Python assertion test for all config values | 0 | ✅ pass | <1s |

## Diagnostics

- **YAML parse validation**: Run `python -c "import yaml; yaml.safe_load(open('third_party/quantaalpha/configs/backtest.yaml'))"`
- **Stock filter check**: `grep -A 3 "stock_filter:" third_party/quantaalpha/configs/backtest.yaml`
- **Period validation**: Count periods with `grep -c "name:" third_party/quantaalpha/configs/backtest.yaml`
- **Failure surface**: Any parse error in YAML will fail at load time with Python traceback

## Deviations

None — implementation matched task plan exactly.

## Known Issues

None.

## Files Created/Modified

- `third_party/quantaalpha/configs/backtest.yaml` — Enabled stock_filter (enabled=true, exclude_markets=["bj"], exclude_st=true, min_list_days=60) and multi_period_validation (enabled=true with 4 periods)
- `.gsd/milestones/M003/slices/S03/S03-PLAN.md` — Added Observability/Diagnostics and Diagnostics/Failure-Path Checks sections
