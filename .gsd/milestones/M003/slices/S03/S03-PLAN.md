# S03: P0 配置解锁优化

**Goal:** Exclude Beijing Stock Exchange (北交所) from backtesting and activate multi-period validation with 4 market-cycle periods
**Demo:** `configs/backtest.yaml` updated with stock_filter.enabled=true, exclude_markets=["bj"], and multi_period_validation.enabled=true with 4 periods covering 2017-2025 market cycles

## Must-Haves

- `data.stock_filter.enabled` set to `true`
- `data.stock_filter.exclude_markets` includes `"bj"`
- `multi_period_validation.enabled` set to `true`
- `multi_period_validation.periods` contains 4 periods (2017_2018, 2019_2020, 2021_2022, 2023_2025)
- YAML syntax validated via `yaml.safe_load()`

## Verification

- `python -c "import yaml; yaml.safe_load(open('third_party/quantaalpha/configs/backtest.yaml'))"`
- `grep -A 2 "stock_filter:" third_party/quantaalpha/configs/backtest.yaml` shows `enabled: true` and `exclude_markets:`
- `grep -A 6 "multi_period_validation:" third_party/quantaalpha/configs/backtest.yaml` shows `enabled: true` and 4 periods

## Observability / Diagnostics

- **Runtime inspection**: After enabling, backtest logs will indicate stock count before/after filtering
- **Failure visibility**: Invalid YAML will fail at `yaml.safe_load()` with clear parse error
- **Misconfiguration detection**: Missing `bj` in `exclude_markets` can be verified via grep or Python assertion
- **Period boundary checks**: Each period's date range can be validated against market event timeline

## Diagnostics / Failure-Path Checks

- **YAML parse failure**: Run `python -c "import yaml; yaml.safe_load(...)"` — any syntax error will surface immediately
- **Empty exclude_markets**: Verify list is not `[]` — use `grep -A 2 "exclude_markets:" backtest.yaml`
- **Wrong market code**: Confirm "bj" is correct code (vs "BJ", "beijing", etc.) — grep output confirms exact match
- **Period overlap/missing**: Validate 4 periods cover full range without gaps using Python date range comparison

## Tasks

- [x] **T01: 配置股票过滤排除北交所** `est:5m`
  - Why: 排除北交所低流动性股票，避免影响因子有效性评估
  - Files: `third_party/quantaalpha/configs/backtest.yaml`
  - Do: 将 `data.stock_filter.enabled` 改为 `true`，将 `data.stock_filter.exclude_markets` 改为 `["bj"]`
  - Verify: `grep -A 3 "stock_filter:" third_party/quantaalpha/configs/backtest.yaml`
  - Done when: `enabled: true` 和 `exclude_markets: ["bj"]` 存在于配置中

- [x] **T02: 配置多周期回测验证** `est:5m`
  - Why: 覆盖不同市场周期，验证因子鲁棒性
  - Files: `third_party/quantaalpha/configs/backtest.yaml`
  - Do: 将 `multi_period_validation.enabled` 改为 `true`，添加 4 个 periods (2017_2018_去杠杆, 2019_2020_结构牛, 2021_2022_震荡熊, 2023_2025_复苏)
  - Verify: `grep -c "name:" third_party/quantaalpha/configs/backtest.yaml` 返回 >= 5 (1个全局name + 4个period name)
  - Done when: 4 个 period 配置存在且日期范围正确

- [x] **T03: 验证 YAML 语法和配置完整性** `est:5m`
  - Why: 确保配置无语法错误，可被系统正确加载
  - Files: `third_party/quantaalpha/configs/backtest.yaml`
  - Do: 运行 Python yaml.safe_load() 验证语法，检查 stock_filter 和 multi_period_validation 配置
  - Verify: `python -c "import yaml; cfg=yaml.safe_load(open('third_party/quantaalpha/configs/backtest.yaml')); assert cfg['data']['stock_filter']['enabled']==True; assert 'bj' in cfg['data']['stock_filter']['exclude_markets']; assert cfg['multi_period_validation']['enabled']==True; assert len(cfg['multi_period_validation']['periods'])==4; print('All assertions passed')"`
  - Done when: 所有断言通过，输出 "All assertions passed"

## Files Likely Touched

- `third_party/quantaalpha/configs/backtest.yaml`

---
estimated_steps: 6
estimated_files: 1
skills_used:
  - lint
