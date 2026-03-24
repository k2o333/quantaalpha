# T01: 配置股票过滤排除北交所

**Slice:** S03 — P0 配置解锁优化
**Milestone:** M003

## Description

在 `configs/backtest.yaml` 中启用股票过滤功能，排除北交所 (Beijing Stock Exchange, market code "bj")。北交所股票流动性较低，排除后可获得更可靠的因子评估结果。

## Steps

1. 打开 `third_party/quantaalpha/configs/backtest.yaml`
2. 找到 `data.stock_filter` 配置块
3. 将 `enabled: false` 改为 `enabled: true`
4. 将 `exclude_markets: []` 改为 `exclude_markets: ["bj"]`
5. 可选：设置 `exclude_st: true` 排除 ST 股票，设置 `min_list_days: 60` 要求至少上市 60 天

## Must-Haves

- [ ] `data.stock_filter.enabled` 设置为 `true`
- [ ] `data.stock_filter.exclude_markets` 包含 `"bj"`
- [ ] YAML 语法正确

## Verification

```bash
# 验证 stock_filter 配置
grep -A 3 "stock_filter:" third_party/quantaalpha/configs/backtest.yaml
# 应显示:
#   stock_filter:
#     enabled: true
#     exclude_markets: ["bj"]
```

## Inputs

- `third_party/quantaalpha/configs/backtest.yaml` — 现有配置文件

## Expected Output

- `third_party/quantaalpha/configs/backtest.yaml` — 修改后的配置文件，stock_filter 已启用并排除北交所
