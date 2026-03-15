# 因子状态流转规则

Status: draft
Owner: QuantaAlpha team
Created: 2026-03-14
Outcome: pending
Phase: 2
Depends-on:
- /home/quan/testdata/aspipe_v4/docs/03-changes/quantaalpha/quantaalpha2026-3-14checklist/2026-03-14-factor-library-schema-extension.md
- /home/quan/testdata/aspipe_v4/docs/03-changes/quantaalpha/quantaalpha2026-3-14checklist/2026-03-14-revalidate-cli.md
Related-to: /home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/2026-03-14-quantaalpha-continuous-factor-implementation-checklist.md

---

## Background

有了 `evaluation.status` 字段以后，如果没有统一流转规则，这个字段很快会退化成“随便填一个字符串”。状态的价值不在于存下来，而在于能被一致地更新、解释和消费。

因此本阶段要把状态更新从“写库时顺手赋值”升级为“规则驱动的可测试逻辑”。

---

## Goal

定义一套最小但闭环的状态机，覆盖以下场景：

- 新因子入库
- 验证通过
- 长期未验证
- 效果显著下降
- 连续复验失败
- 人工恢复

---

## Non-goals

- 不实现机器学习驱动的状态预测。
- 不实现复杂审批流。
- 不开放任意自定义状态集合。

---

## Acceptance Criteria

1. 每个状态变化都有明确触发条件。
2. 同一个输入条件在任意入口得到相同状态结果。
3. 流转逻辑可独立单元测试，不依赖文件 I/O。
4. `revalidate` CLI 和正常验证流程都复用同一套规则。

---

## Design Decision

### 状态机

```text
pending_validation --[验证通过]--> active
active --[超过阈值未验证]--> stale
active --[稳定性下降超过阈值]--> degraded
degraded --[复验通过]--> active
stale --[复验通过]--> active
degraded --[连续失败达到阈值]--> deprecated
stale --[连续失败达到阈值]--> deprecated
deprecated --[人工恢复]--> active
```

### 配置结构

```yaml
factor_status:
  stale_threshold_days: 30
  degraded_stability_threshold: 0.3
  active_stability_threshold: 0.5
  consecutive_failures_to_deprecate: 3
```

### 规则函数

建议实现纯函数，例如：

```python
def update_factor_status(factor_entry, validation_result, now=None, config=None) -> str:
    ...
```

该函数只负责返回新状态和必要的统计更新，不负责文件读写。

---

## Affected Modules

- `third_party/quantaalpha/quantaalpha/factors/library.py`
- 复验回写逻辑
- 如需隔离规则，可新增 `third_party/quantaalpha/quantaalpha/factors/status_rules.py`

---

## Implementation Plan

1. 先冻结首版状态集合和阈值配置。
2. 把状态计算抽成纯函数，与 JSON 读写解耦。
3. 在正常验证写回和 `revalidate` CLI 两处共用同一规则函数。
4. 为 `consecutive_failures`、`last_validated` 等依赖字段补默认值。
5. 将“人工恢复”保留为显式命令或手工操作，不混入自动规则。

---

## Test Plan

### 单元测试

1. `pending_validation` 在验证通过后变为 `active`。
2. `active` 超过阈值未验证后变为 `stale`。
3. `active` 在稳定性跌破阈值后变为 `degraded`。
4. `degraded` 连续失败达到阈值后变为 `deprecated`。
5. `stale` 或 `degraded` 复验通过后可恢复为 `active`。

### 集成测试

6. `revalidate` CLI 更新后的状态与规则函数输出一致。
7. 多周期验证结果回写时，状态变化符合阈值设定。
8. 旧因子缺少统计字段时，系统会补默认值而不是崩溃。

### 手工验收

9. 构造一个完整生命周期样本，从 `pending_validation` 走到 `deprecated` 再人工恢复，确认状态链路闭环。

---

## Risk Points

1. 阈值设置不合理会导致状态频繁抖动。
2. 规则函数若与时间处理耦合过深，测试会变脆弱。
3. 若多个入口各自实现流转逻辑，状态会失真。

---

## Rollback Plan

- 状态自动流转可通过配置关闭。
- 保留人工覆盖状态的能力。
- 若规则争议较大，可先只启用 `pending_validation -> active` 和 `active -> stale` 两条最基础流转。

---

## Final Result

> 待实施后填写

---

## Validation Evidence

> 待实施后填写

---

## Lessons Learned

> 待实施后填写
