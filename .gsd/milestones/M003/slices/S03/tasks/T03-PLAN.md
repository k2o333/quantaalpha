# T03: 验证 YAML 语法和配置完整性

**Slice:** S03 — P0 配置解锁优化
**Milestone:** M003

## Description

验证 `configs/backtest.yaml` 的 YAML 语法正确性和配置完整性，确保所有修改都已正确应用。

## Steps

1. 使用 Python yaml.safe_load() 验证 YAML 语法
2. 验证 stock_filter 配置：
   - `enabled` 为 `true`
   - `exclude_markets` 包含 `"bj"`
3. 验证 multi_period_validation 配置：
   - `enabled` 为 `true`
   - `periods` 长度为 4
   - 每个 period 有有效的日期范围

## Must-Haves

- [ ] yaml.safe_load() 成功解析，无语法错误
- [ ] stock_filter.enabled == True
- [ ] "bj" in stock_filter.exclude_markets
- [ ] multi_period_validation.enabled == True
- [ ] len(multi_period_validation.periods) == 4

## Verification

```bash
# 完整验证脚本
python -c "
import yaml
cfg = yaml.safe_load(open('third_party/quantaalpha/configs/backtest.yaml'))

# Stock filter checks
assert cfg['data']['stock_filter']['enabled'] == True, 'stock_filter not enabled'
assert 'bj' in cfg['data']['stock_filter']['exclude_markets'], 'bj not in exclude_markets'

# Multi-period checks
assert cfg['multi_period_validation']['enabled'] == True, 'multi_period_validation not enabled'
periods = cfg['multi_period_validation']['periods']
assert len(periods) == 4, f'Expected 4 periods, got {len(periods)}'

# Validate each period has required fields
for p in periods:
    assert 'name' in p, f'Period missing name: {p}'
    assert 'train' in p and 'valid' in p and 'test' in p, f'Period missing date fields: {p}'

print('All assertions passed!')
echo 'Configuration verified successfully.'
"
```

## Inputs

- `third_party/quantaalpha/configs/backtest.yaml` — 已修改的配置文件

## Expected Output

- 验证脚本输出 "All assertions passed!"
- 无异常退出
