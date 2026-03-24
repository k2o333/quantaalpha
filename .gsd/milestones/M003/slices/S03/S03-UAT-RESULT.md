---
sliceId: S03
uatType: artifact-driven
verdict: PASS
date: 2026-03-23T19:16:04+08:00
---

# UAT Result — S03

## Checks

| Check | Mode | Result | Notes |
|-------|------|--------|-------|
| TC-01: YAML Parsing | artifact | PASS | `yaml.safe_load()` succeeded, no exception raised |
| TC-02: Stock Filter Enabled | artifact | PASS | `enabled: true` and `exclude_markets:` present in grep output |
| TC-03: Beijing Exchange Exclusion | artifact | PASS | Assertion `'bj' in cfg['data']['stock_filter']['exclude_markets']` passed |
| TC-04: ST Stock Filtering | artifact | PASS | `exclude_st == True` confirmed |
| TC-05: Listing Days Requirement | artifact | PASS | `min_list_days >= 60` (value is 60) confirmed |
| TC-06: Multi-Period Validation Enabled | artifact | PASS | `enabled: true` present in grep output |
| TC-07: Four Periods Configured | artifact | PASS | `len(periods) == 4` assertion passed |
| TC-08: Period Naming Convention | artifact | PASS | All 4 names match: 2017_2018_去杠杆, 2019_2020_结构牛, 2021_2022_震荡熊, 2023_2025_复苏 |
| TC-09: Train/Valid/Test Segmentation | artifact | PASS | All 4 periods have train, valid, test fields |
| TC-10: Fail Fast Disabled | artifact | PASS | `fail_fast == False` confirmed |
| TC-11: Date Range Ordering | artifact | PASS | Train < Valid < Test ordering verified for all 4 periods |
| TC-12: Full Configuration Smoke Test | artifact | PASS | All 12 assertions passed; "ALL ASSERTIONS PASSED — S03 configuration valid" printed |
| EC-01: Wrong Market Code | artifact | PASS | `exclude_markets: ['bj']` — lowercase "bj" confirmed, not "BJ" or "beijing" |
| EC-02: Period Overlap | artifact | PASS | No assertion failure; adjacent periods have proper boundaries |
| EC-03: Empty exclude_markets | artifact | PASS | `len(exclude_markets) > 0` — list contains "bj" |

## Overall Verdict

**PASS** — All 12 test cases and 3 edge cases passed. The `backtest.yaml` configuration is valid, stock filtering excludes Beijing Stock Exchange, and multi-period validation is correctly configured with 4 market-cycle periods covering 2017–2025.

## Notes

- All assertions were executed via Python inline scripts against `third_party/quantaalpha/configs/backtest.yaml`
- No exceptions, tracebacks, or assertion failures were encountered
- The full smoke test (TC-12) confirms the combined correctness of all individual configuration values
