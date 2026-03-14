# 多周期验证

Status: draft
Owner: QuantaAlpha team
Created: 2026-03-14
Outcome: pending
Phase: 1
Related-to: /home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/2026-03-14-quantaalpha-continuous-factor-implementation-checklist.md

---

## Background

当前 QuantaAlpha 系统仅支持单周期回测，因子稳定性评估依赖单次验证结果。这导致：
- 无法评估因子在不同市场环境下的表现
- 稳定性评估缺乏统计学依据
- 因子选择可能过拟合于特定时间段

---

## Goal

在现有单周期 backtest 能力上扩展配置驱动的多周期验证：
- 遍历多个 period
- 分别执行训练/验证/测试
- 聚合 period 级指标
- 输出稳定性评分

---

## Non-goals

- 不单独抽象成独立 engine（首版在 runner 中实现）
- 不支持 period 间的参数优化
- 不改变现有单周期回测的核心算法

---

## Acceptance Criteria

1. 可通过配置运行多组时间窗口验证
2. 能得到 period 级明细和聚合稳定性指标
3. 聚合结果能回写因子库
4. 单周期模式不回归

---

## Test Plan

### 单元测试

1. `enabled=false` 时，行为与现有单周期完全一致
2. 稳定性聚合函数计算正确

### 集成测试

3. 配置两个 periods 时，确实运行两组回测
4. 每个 period 都有独立结果输出
5. 聚合结果中包含均值、标准差和 period 明细
6. 单个 period 失败时，错误信息明确，且整体行为符合预期

---

## Implementation Plan

### 主要修改点

- `quantaalpha/backtest/runner.py`
- `configs/backtest.yaml`
- 因子库写入逻辑所在模块

### 配置结构

```yaml
multi_period_validation:
  enabled: true
  periods:
    - name: "recent"
      train: ["2022-01-01", "2023-12-31"]
      valid: ["2024-01-01", "2024-06-30"]
      test: ["2024-07-01", "2025-03-13"]
    - name: "historical"
      train: ["2017-01-01", "2019-12-31"]
      valid: ["2020-01-01", "2020-12-31"]
      test: ["2021-01-01", "2021-12-31"]
```

### 首版输出指标

```python
{
    "period_results": [...],
    "ic_mean": float,
    "ic_std": float,
    "rank_ic_mean": float,
    "rank_ic_std": float,
    "win_rate_by_period": [...],
    "max_drawdown_by_period": [...],
    "turnover_by_period": [...],
    "stability_score": float
}
```

---

## Risk Points

1. 多周期运行时间成倍增长
2. 不同 period 结果差异大时，聚合指标的解读需要谨慎
3. 需要确保每个 period 的数据对齐方式一致

---

## Rollback Plan

- 配置 `multi_period_validation.enabled: false` 回退到单周期模式
- 不修改现有单周期回测代码路径
- 新增逻辑通过条件分支隔离

---

## Final Result

> 待实施后填写

---

## Validation Evidence

> 待实施后填写

---

## Lessons Learned

> 待实施后填写
