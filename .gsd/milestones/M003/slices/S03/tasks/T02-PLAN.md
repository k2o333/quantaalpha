# T02: 配置多周期回测验证

**Slice:** S03 — P0 配置解锁优化
**Milestone:** M003

## Description

在 `configs/backtest.yaml` 中启用多周期回测验证，覆盖 4 个不同的中国股市周期：去杠杆 (2017-2018)、结构牛 (2019-2020)、震荡熊 (2021-2022)、复苏 (2023-2025)。多周期验证可验证因子在不同市场环境下的鲁棒性。

## Steps

1. 打开 `third_party/quantaalpha/configs/backtest.yaml`
2. 找到 `multi_period_validation` 配置块
3. 将 `enabled: false` 改为 `enabled: true`
4. 将 `fail_fast: true` 改为 `fail_fast: false` (运行所有周期)
5. 将空的 `periods: []` 替换为 4 个 period 配置：

```yaml
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

## Must-Haves

- [ ] `multi_period_validation.enabled` 设置为 `true`
- [ ] `multi_period_validation.fail_fast` 设置为 `false`
- [ ] 包含 4 个 period 配置
- [ ] 每个 period 有 name, train, valid, test 字段
- [ ] 日期范围符合 train <= valid <= test 顺序

## Verification

```bash
# 验证多周期配置存在
grep -c "name:" third_party/quantaalpha/configs/backtest.yaml
# 应返回 >= 5 (experiment.name + 4 个 period.name)

# 验证 periods 数量
python -c "import yaml; cfg=yaml.safe_load(open('third_party/quantaalpha/configs/backtest.yaml')); print(f'Periods: {len(cfg[\"multi_period_validation\"][\"periods\"])}')"
# 应输出: Periods: 4
```

## Inputs

- `third_party/quantaalpha/configs/backtest.yaml` — 现有配置文件

## Expected Output

- `third_party/quantaalpha/configs/backtest.yaml` — 修改后的配置文件，包含 4 个多周期验证配置
