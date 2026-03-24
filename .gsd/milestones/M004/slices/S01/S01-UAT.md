---
id: S01
parent: M004
milestone: M004
---

# S01: 跨周期验证通过标准 — UAT

**Milestone:** M004
**Written:** 2026-03-24

## UAT Type

- UAT mode: **artifact-driven**
- Why this mode is sufficient: 核心逻辑为纯函数 (evaluate_multi_period_results)，无外部依赖，可通过 Python 交互式验证完全覆盖

## Preconditions

```python
# 确保模块可导入
cd /home/quan/testdata/aspipe_v4
python -c "from third_party.quantaalpha.quantaalpha.backtest.validation_judge import evaluate_multi_period_results"
```

## Smoke Test

```python
python -c "
from third_party.quantaalpha.quantaalpha.backtest.validation_judge import evaluate_multi_period_results
r = evaluate_multi_period_results(
    [{'name': 'test', 'metrics': {'IC': 0.05, 'Rank IC': 0.05, 'status': 'success'}}],
    {'min_ic': 0.02, 'min_rank_ic': 0.02, 'min_periods_pass': 1},
    True,
)
assert r.overall_pass == True, 'Smoke test failed'
print('Smoke test passed')
"
```

## Test Cases

### 1. 全通过场景 (All Periods Pass)

```python
from third_party.quantaalpha.quantaalpha.backtest.validation_judge import evaluate_multi_period_results

result = evaluate_multi_period_results(
    period_results=[
        {"name": "2022", "metrics": {"IC": 0.05, "Rank IC": 0.04, "status": "success"}},
        {"name": "2023", "metrics": {"IC": 0.03, "Rank IC": 0.03, "status": "success"}},
    ],
    pass_criteria={"min_ic": 0.02, "min_rank_ic": 0.02, "min_periods_pass": 2},
    require_all_pass=True,
)
```

1. **Expected:** `result.overall_pass == True`
2. **Expected:** `result.passing_periods == ["2022", "2023"]`
3. **Expected:** `result.failing_periods == []`
4. **Expected:** `result.passing_count == 2`

### 2. 部分通过场景 (Partial Pass with require_all_pass=False)

```python
result = evaluate_multi_period_results(
    period_results=[
        {"name": "2022", "metrics": {"IC": 0.05, "Rank IC": 0.04, "status": "success"}},
        {"name": "2023", "metrics": {"IC": 0.01, "Rank IC": 0.01, "status": "success"}},
    ],
    pass_criteria={"min_ic": 0.02, "min_rank_ic": 0.02, "min_periods_pass": 1},
    require_all_pass=False,
)
```

1. **Expected:** `result.overall_pass == True` (1 passing >= min_periods_pass=1)
2. **Expected:** `result.passing_periods == ["2022"]`
3. **Expected:** `result.failing_periods == ["2023"]`

### 3. 全部失败场景 (All Periods Fail)

```python
result = evaluate_multi_period_results(
    period_results=[
        {"name": "2022", "metrics": {"IC": 0.01, "Rank IC": 0.01, "status": "success"}},
        {"name": "2023", "metrics": {"IC": 0.005, "Rank IC": 0.005, "status": "success"}},
    ],
    pass_criteria={"min_ic": 0.02, "min_rank_ic": 0.02, "min_periods_pass": 2},
    require_all_pass=True,
)
```

1. **Expected:** `result.overall_pass == False`
2. **Expected:** `result.failing_periods == ["2022", "2023"]`
3. **Expected:** reason contains "IC" and "<= threshold"

### 4. 空输入场景 (Empty Period Results)

```python
result = evaluate_multi_period_results(
    period_results=[],
    pass_criteria={"min_ic": 0.02, "min_rank_ic": 0.02, "min_periods_pass": 2},
    require_all_pass=True,
)
```

1. **Expected:** `result.overall_pass == False`
2. **Expected:** `result.total_periods == 0`
3. **Expected:** `result.passing_count == 0`

### 5. 非成功状态场景 (Non-Success Status)

```python
result = evaluate_multi_period_results(
    period_results=[
        {"name": "2024", "metrics": {"IC": 0.05, "Rank IC": 0.04, "status": "error"}},
    ],
    pass_criteria={"min_ic": 0.02, "min_rank_ic": 0.02, "min_periods_pass": 1},
    require_all_pass=False,
)
```

1. **Expected:** `result.overall_pass == False`
2. **Expected:** `result.period_judgments[0]["reason"] == "Period status is 'error'"`

### 6. 缺失指标场景 (Missing IC or Rank IC)

```python
result = evaluate_multi_period_results(
    period_results=[
        {"name": "2022", "metrics": {"IC": None, "Rank IC": 0.04, "status": "success"}},
    ],
    pass_criteria={"min_ic": 0.02, "min_rank_ic": 0.02, "min_periods_pass": 1},
    require_all_pass=False,
)
```

1. **Expected:** `result.overall_pass == False`
2. **Expected:** reason contains "IC not available"

### 7. 配置边界值 (Threshold Boundary Values)

```python
# IC exactly at threshold should FAIL (strictly greater than)
result = evaluate_multi_period_results(
    period_results=[
        {"name": "2022", "metrics": {"IC": 0.02, "Rank IC": 0.03, "status": "success"}},
    ],
    pass_criteria={"min_ic": 0.02, "min_rank_ic": 0.02, "min_periods_pass": 1},
    require_all_pass=True,
)
```

1. **Expected:** `result.overall_pass == False` (IC must be > 0.02, not >=)
2. **Expected:** reason contains "IC (0.0200) <= threshold (0.0200)"

## Edge Cases

### Edge Case 1: min_periods_pass 大于实际周期数

```python
result = evaluate_multi_period_results(
    period_results=[
        {"name": "2022", "metrics": {"IC": 0.05, "Rank IC": 0.05, "status": "success"}},
    ],
    pass_criteria={"min_ic": 0.02, "min_rank_ic": 0.02, "min_periods_pass": 5},
    require_all_pass=False,
)
```

1. **Expected:** `result.overall_pass == False` (1 passing < 5 required)

### Edge Case 2: 默认值处理 (Missing pass_criteria fields)

```python
result = evaluate_multi_period_results(
    period_results=[
        {"name": "2022", "metrics": {"IC": 0.05, "Rank IC": 0.05, "status": "success"}},
    ],
    pass_criteria={},  # Empty criteria
    require_all_pass=True,
)
```

1. **Expected:** `result.overall_pass == True` (defaults: min_ic=0.0, min_rank_ic=0.0, min_periods_pass=1)

### Edge Case 3: format_evaluation_result() 输出格式

```python
from quantaalpha.quantaalpha.backtest.validation_judge import format_evaluation_result

result = evaluate_multi_period_results(
    period_results=[
        {"name": "2022", "metrics": {"IC": 0.05, "Rank IC": 0.04, "status": "success"}},
        {"name": "2023", "metrics": {"IC": 0.01, "Rank IC": 0.01, "status": "success"}},
    ],
    pass_criteria={"min_ic": 0.02, "min_rank_ic": 0.02, "min_periods_pass": 2},
    require_all_pass=True,
)
formatted = format_evaluation_result(result)
```

1. **Expected:** formatted contains "Multi-Period Validation Result: FAIL"
2. **Expected:** formatted contains "Passing: 1/2"
3. **Expected:** formatted contains "Failing periods: 2023"

## Failure Signals

- `python -m py_compile` 失败 → 语法错误
- `result.period_judgments` 为空列表但 total_periods > 0 → 逻辑错误
- `overall_pass=True` 但 `passing_periods` 为空 → 逻辑错误
- `format_evaluation_result()` 抛出异常 → 输出格式化问题

## Not Proven By This UAT

- 回测结果聚合模块是否实际调用了 `evaluate_multi_period_results()`
- 实际回测运行中配置是否正确读取
- 长时间运行稳定性

## Notes for Tester

- IC 和 Rank IC 使用**严格大于**比较 (`>`)，不是 `>=`
- 当 status != 'success' 时，即使 IC 达标也视为失败
- None 值被视为不达标（无法与阈值比较）
