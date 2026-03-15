# 多周期验证

Status: completed
Owner: QuantaAlpha team
Created: 2026-03-14
Outcome: implemented
Phase: 1
Depends-on: /home/quan/testdata/aspipe_v4/docs/03-changes/quantaalpha/quantaalpha2026-3-14checklist/2026-03-14-unified-stock-universe-filter.md
Related-to: /home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/2026-03-14-quantaalpha-continuous-factor-implementation-checklist.md

---

## Background

当前回测主要基于单一时间窗口，结果容易被特定市场阶段放大或误导。单次 `IC` 或收益表现更适合做局部筛选，不足以支撑“稳定可复用因子”的判断。

因此首版要解决的是“在不重写回测引擎的前提下，让一份配置能跑多个时间窗口并产出可聚合结果”。

---

## Goal

在现有 `quantaalpha/backtest/runner.py` 上扩展配置驱动的多周期验证能力：

- 顺序执行多个 `period`
- 每个 `period` 产出独立回测结果
- 聚合为稳定性指标
- 将聚合结果提供给因子库写入与后续筛选逻辑

---

## Non-goals

- 不实现新的独立回测引擎。
- 不做 period 间自动调参。
- 不在首版支持并行执行多个 period。
- 不在本阶段定义因子状态流转，只负责产出验证结果。

---

## Acceptance Criteria

1. `enabled=false` 时，行为与现有单周期完全一致。
2. 配置多个 periods 时，系统会逐个执行并分别输出结果。
3. 聚合结果包含 period 明细、均值、波动度和统一 `stability_score`。
4. 聚合结果可被因子库写入逻辑消费。

---

## Design Decision

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

### 输出结构

```python
{
    "period_results": [
        {
            "name": "recent",
            "segments": {...},
            "metrics": {...},
            "status": "success",
        }
    ],
    "summary": {
        "ic_mean": 0.042,
        "ic_std": 0.011,
        "rank_ic_mean": 0.038,
        "rank_ic_std": 0.014,
        "win_rate_mean": 0.67,
        "max_drawdown_worst": -0.12,
        "stability_score": 0.81,
    }
}
```

### 首版实现策略

- 在 `BacktestRunner.run()` 外层增加“period 循环层”。
- 每次循环只覆写 `dataset.segments` 与 `backtest.backtest.{start_time,end_time}`。
- 聚合逻辑独立成纯函数，例如 `aggregate_period_metrics()`，便于后续测试和复用。
- 对单个 period 失败的行为用配置控制，默认 `fail_fast=true`。

---

## Affected Modules

- `third_party/quantaalpha/quantaalpha/backtest/runner.py`
- `third_party/quantaalpha/configs/backtest.yaml`
- 因子库结果回写链路

---

## Implementation Plan

1. 在配置解析阶段增加 `multi_period_validation` 开关和 period 校验。
2. 将当前单次运行逻辑拆成“单个 period 执行函数 + 外层多 period 调度函数”。
3. 增加聚合函数，统一计算均值、标准差、失败数和 `stability_score`。
4. 将 period 级结果和 summary 一并写入结果文件。
5. 为下游因子库写入预留稳定字段名，避免后续重复改协议。

---

## Test Plan

### 单元测试

1. `enabled=false` 时调用路径与旧逻辑一致。
2. `aggregate_period_metrics()` 对均值、标准差、失败数计算正确。
3. 空 period 列表、非法日期区间、重复 period 名称会被明确拒绝。

### 集成测试

4. 配置两个 periods 时，确实执行两次回测。
5. 每个 period 都有独立结果文件或结果段落。
6. `summary` 中包含 `period_results` 聚合后的关键指标。
7. 单个 period 失败时，错误信息包含失败 period 名称和日期范围。

### 手工验收

8. 用一个已知稳定因子和一个已知不稳定因子对比 `stability_score`，确认排序方向符合直觉。

---

## Risk Points

1. 回测耗时近似按 period 数线性增长。
2. 如果股票池过滤未统一，不同 period 之间可能混入不一致 universe。
3. 若聚合指标设计过于激进，会误伤新因子或样本较短因子。

---

## Rollback Plan

- `multi_period_validation.enabled: false` 直接回退为单周期模式。
- 多周期逻辑与旧逻辑分支隔离，不修改核心训练和回测算法。
- 若 `stability_score` 公式存在争议，可先保留 period 明细并暂不下游消费该分数。

---

## Final Result

- 已在回测链路中加入配置驱动的多周期验证能力。
- 当前支持：
  - `enabled` 开关
  - 多个 `period` 顺序执行
  - period 级结果聚合为 `summary`
  - 输出 `stability_score` 供因子库和 evolution 消费
- 首版仍是串行执行，不包含更复杂的调参或并行调度。

---

## Validation Evidence

- 相关能力已纳入项目内连续因子特性测试：
  - `third_party/quantaalpha/tests/test_continuous_factor_features.py`
- 文档、README 与验收草案已同步补充多周期使用方式和验收路径。
- 后续回测结果已可进入因子库 `evaluation.period_results` / `evaluation.stability_score`。

---

## Lessons Learned

- 多周期能力必须和统一 universe 一起考虑，否则 period 间结果不可比。
- 首版先把协议和聚合字段定下来，比一开始追求复杂调度更稳妥。
