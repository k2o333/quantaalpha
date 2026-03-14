# 因子状态流转规则

Status: draft
Owner: QuantaAlpha team
Created: 2026-03-14
Outcome: pending
Phase: 2
Depends-on: /home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/quantaalpha2026-3-14checklist/2026-03-14-factor-library-schema-extension.md
Related-to: /home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/2026-03-14-quantaalpha-continuous-factor-implementation-checklist.md

---

## Background

当前因子状态更新依赖"写库时一次性赋值"，缺乏：
- 规则驱动的自动状态管理
- 时间维度的状态衰减
- 效果维度的状态降级

---

## Goal

把因子状态更新从"一次性赋值"升级为"规则驱动更新"：
- 时间维度流转：`active -> stale`
- 效果维度流转：`active -> degraded`
- 复验恢复：`degraded -> active`
- 淘汰流转：`stale/degraded -> deprecated`

---

## Non-goals

- 不实现机器学习驱动的状态预测
- 不实现人工审批工作流
- 不支持自定义状态流转规则（首版硬编码）

---

## Acceptance Criteria

1. 状态变化逻辑清晰可测试
2. 不依赖人工修改 JSON 才能维护状态

---

## Test Plan

### 单元测试

1. 输入不同验证结果时，状态能正确流转
2. 时间阈值触发 `stale` 更新
3. 复验恢复后状态可回到 `active`
4. 连续失败触发 `deprecated`

### 集成测试

5. 与 revalidate CLI 集成后状态正确更新
6. 与多周期验证集成后状态正确更新

---

## Implementation Plan

### 主要修改点

- `quantaalpha/factors/library.py`
- 因子库写入逻辑

### 流转规则

```
pending_validation --[验证通过]--> active
active --[超过N天未验证]--> stale
active --[stability_score下降超过阈值]--> degraded
degraded --[复验通过]--> active
stale --[复验通过]--> active
degraded --[连续N次复验失败]--> deprecated
stale --[连续N次复验失败]--> deprecated
deprecated --[人工恢复]--> active
```

### 配置结构

```yaml
factor_status:
  stale_threshold_days: 30
  degraded_stability_threshold: 0.3
  consecutive_failures_to_deprecate: 3
```

### 实现伪代码

```python
def update_factor_status(factor, validation_result):
    current_status = factor.evaluation.status
    
    if current_status == "pending_validation":
        if validation_result.stability_score > 0.5:
            return "active"
    
    elif current_status == "active":
        if validation_result.stability_score < degraded_threshold:
            return "degraded"
    
    elif current_status in ["stale", "degraded"]:
        if validation_result.stability_score > 0.5:
            return "active"
        elif consecutive_failures >= threshold:
            return "deprecated"
    
    return current_status
```

---

## Risk Points

1. 阈值设置需要根据实际数据调优
2. 状态频繁切换可能导致不稳定性
3. 需要记录状态变更历史以支持审计

---

## Rollback Plan

- 状态流转规则可通过配置禁用
- 保留手动修改状态的能力
- 状态变更记录保留便于回溯

---

## Final Result

> 待实施后填写

---

## Validation Evidence

> 待实施后填写

---

## Lessons Learned

> 待实施后填写
