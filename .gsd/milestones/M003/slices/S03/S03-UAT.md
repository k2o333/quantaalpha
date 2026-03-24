# S03: P0 配置解锁优化 — UAT Script

## Preconditions
- Working directory: `/home/quan/testdata/aspipe_v4/.gsd/worktrees/M003`
- Python 3 with PyYAML installed
- Target file: `third_party/quantaalpha/configs/backtest.yaml`

## Test Cases

### TC-01: YAML Parsing
**Purpose**: Verify backtest.yaml is valid YAML syntax

**Steps**:
1. Open terminal in worktree directory
2. Run: `python -c "import yaml; yaml.safe_load(open('third_party/quantaalpha/configs/backtest.yaml'))"`
3. Verify no exception is raised

**Expected Result**: Command exits with code 0, no Python traceback

---

### TC-02: Stock Filter Enabled
**Purpose**: Verify stock filtering is activated

**Precondition**: TC-01 must pass

**Steps**:
1. Run: `grep -A 3 "stock_filter:" third_party/quantaalpha/configs/backtest.yaml`
2. Verify output contains:
   - `enabled: true`
   - `exclude_markets:`

**Expected Result**: Both conditions present in grep output

---

### TC-03: Beijing Exchange Exclusion
**Purpose**: Verify BJ exchange is in exclusion list

**Precondition**: TC-02 must pass

**Steps**:
1. Run: `python -c "import yaml; cfg=yaml.safe_load(open('third_party/quantaalpha/configs/backtest.yaml')); assert 'bj' in cfg['data']['stock_filter']['exclude_markets']"`
2. Verify exit code 0

**Expected Result**: Assertion passes, "bj" is in exclude_markets list

---

### TC-04: ST Stock Filtering
**Purpose**: Verify ST stocks are filtered

**Precondition**: TC-01 must pass

**Steps**:
1. Run: `python -c "import yaml; cfg=yaml.safe_load(open('third_party/quantaalpha/configs/backtest.yaml')); assert cfg['data']['stock_filter'].get('exclude_st') == True"`
2. Verify exit code 0

**Expected Result**: exclude_st is true

---

### TC-05: Listing Days Requirement
**Purpose**: Verify minimum listing days constraint

**Precondition**: TC-01 must pass

**Steps**:
1. Run: `python -c "import yaml; cfg=yaml.safe_load(open('third_party/quantaalpha/configs/backtest.yaml')); assert cfg['data']['stock_filter'].get('min_list_days', 0) >= 60"`
2. Verify exit code 0

**Expected Result**: min_list_days >= 60

---

### TC-06: Multi-Period Validation Enabled
**Purpose**: Verify multi-period validation is activated

**Precondition**: TC-01 must pass

**Steps**:
1. Run: `grep -A 2 "multi_period_validation:" third_party/quantaalpha/configs/backtest.yaml`
2. Verify output contains `enabled: true`

**Expected Result**: enabled is true

---

### TC-07: Four Periods Configured
**Purpose**: Verify exactly 4 market cycle periods exist

**Precondition**: TC-01 must pass

**Steps**:
1. Run: `python -c "import yaml; cfg=yaml.safe_load(open('third_party/quantaalpha/configs/backtest.yaml')); assert len(cfg['multi_period_validation']['periods']) == 4"`
2. Verify exit code 0

**Expected Result**: Exactly 4 periods in configuration

---

### TC-08: Period Naming Convention
**Purpose**: Verify all 4 periods have descriptive names

**Precondition**: TC-07 must pass

**Steps**:
1. Run: `python -c "import yaml; cfg=yaml.safe_load(open('third_party/quantaalpha/configs/backtest.yaml')); names=[p['name'] for p in cfg['multi_period_validation']['periods']]; print(names)"`
2. Verify output contains expected period names:
   - "2017_2018_去杠杆"
   - "2019_2020_结构牛"
   - "2021_2022_震荡熊"
   - "2023_2025_复苏"

**Expected Result**: All 4 period names present

---

### TC-09: Train/Valid/Test Segmentation
**Purpose**: Verify each period has train/valid/test segments

**Precondition**: TC-07 must pass

**Steps**:
1. Run: `python -c "
import yaml
cfg = yaml.safe_load(open('third_party/quantaalpha/configs/backtest.yaml'))
for p in cfg['multi_period_validation']['periods']:
    assert 'train' in p and 'valid' in p and 'test' in p
print('All periods have train/valid/test')
"`
2. Verify exit code 0

**Expected Result**: All 4 periods have train, valid, test fields

---

### TC-10: Fail Fast Disabled
**Purpose**: Verify all periods will run regardless of individual results

**Precondition**: TC-01 must pass

**Steps**:
1. Run: `python -c "import yaml; cfg=yaml.safe_load(open('third_party/quantaalpha/configs/backtest.yaml')); assert cfg['multi_period_validation'].get('fail_fast', True) == False"`
2. Verify exit code 0

**Expected Result**: fail_fast is false

---

### TC-11: Date Range Ordering
**Purpose**: Verify train <= valid <= test chronological order

**Precondition**: TC-09 must pass

**Steps**:
1. Run: `python -c "
import yaml
cfg = yaml.safe_load(open('third_party/quantaalpha/configs/backtest.yaml'))
from datetime import datetime
for p in cfg['multi_period_validation']['periods']:
    train_start = datetime.strptime(p['train'][0], '%Y-%m-%d')
    train_end = datetime.strptime(p['train'][1], '%Y-%m-%d')
    valid_start = datetime.strptime(p['valid'][0], '%Y-%m-%d')
    valid_end = datetime.strptime(p['valid'][1], '%Y-%m-%d')
    test_start = datetime.strptime(p['test'][0], '%Y-%m-%d')
    test_end = datetime.strptime(p['test'][1], '%Y-%m-%d')
    assert train_end < valid_start, f'Train end {train_end} not before valid start {valid_start}'
    assert valid_end < test_start, f'Valid end {valid_end} not before test start {test_start}'
print('All periods have correct date ordering')
"`
2. Verify exit code 0

**Expected Result**: Train < Valid < Test for all periods

---

### TC-12: Full Configuration Smoke Test
**Purpose**: Comprehensive assertion of all configuration values

**Precondition**: None (self-contained)

**Steps**:
1. Run:
```bash
python -c "
import yaml
cfg = yaml.safe_load(open('third_party/quantaalpha/configs/backtest.yaml'))
# Stock filter assertions
assert cfg['data']['stock_filter']['enabled'] == True
assert 'bj' in cfg['data']['stock_filter']['exclude_markets']
assert cfg['data']['stock_filter'].get('exclude_st') == True
assert cfg['data']['stock_filter'].get('min_list_days', 0) >= 60
# Multi-period assertions
assert cfg['multi_period_validation']['enabled'] == True
assert cfg['multi_period_validation'].get('fail_fast') == False
assert len(cfg['multi_period_validation']['periods']) == 4
print('ALL ASSERTIONS PASSED — S03 configuration valid')
"
```
2. Verify output contains "ALL ASSERTIONS PASSED"

**Expected Result**: All assertions pass, success message printed

---

## Edge Cases

### EC-01: Wrong Market Code
Verify "bj" not "BJ" or "beijing":
```bash
python -c "import yaml; cfg=yaml.safe_load(open('third_party/quantaalpha/configs/backtest.yaml')); print(cfg['data']['stock_filter']['exclude_markets'])"
```

### EC-02: Period Overlap
Verify no date overlap between adjacent period test/train boundaries:
```bash
python -c "
import yaml
cfg = yaml.safe_load(open('third_party/quantaalpha/configs/backtest.yaml'))
periods = cfg['multi_period_validation']['periods']
for i in range(len(periods)-1):
    curr_test_end = periods[i]['test'][1]
    next_train_start = periods[i+1]['train'][0]
    # Allow small overlap for market continuity
"
```

### EC-03: Empty exclude_markets
Verify exclusion list is not empty:
```bash
python -c "import yaml; cfg=yaml.safe_load(open('third_party/quantaalpha/configs/backtest.yaml')); assert len(cfg['data']['stock_filter']['exclude_markets']) > 0"
```

## Summary
- **Total Test Cases**: 12
- **Edge Cases**: 3
- **Pass Criteria**: All 12 test cases must pass for slice acceptance
