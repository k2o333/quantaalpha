# 因子库状态与验证字段扩展

Status: draft
Owner: QuantaAlpha team
Created: 2026-03-14
Outcome: pending
Phase: 1
Related-to: /home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/2026-03-14-quantaalpha-continuous-factor-implementation-checklist.md

---

## Background

当前因子库结构主要作为"结果归档"，缺乏：
- 因子状态管理
- 验证历史记录
- 数据依赖声明

这导致因子维护困难，无法支持可持续的研究知识库。

---

## Goal

扩展因子库结构，让其从"结果归档"升级到"可持续维护的研究知识库"：
- 支持因子状态管理
- 记录验证历史
- 声明数据依赖

---

## Non-goals

- 不实现因子版本控制
- 不实现因子血缘追踪
- 不改变现有因子存储格式（仍为 JSON）

---

## Acceptance Criteria

1. 新老因子库文件都可正常读取
2. 因子库中可直接查看最近验证时间、状态、稳定性
3. 状态字段能支持后续筛选、复验、前端展示

---

## Test Plan

### 单元测试

1. 新因子写入后包含完整 `evaluation` 和 `data_requirements` 结构
2. 状态流转函数能按输入条件正确更新

### 集成测试

3. 历史因子库在升级后可兼容读取
4. 多周期验证完成后能正确回写 `stability_score` 和 `period_results`
5. 未提供验证结果时不会破坏旧逻辑

---

## Implementation Plan

### 主要修改点

- `quantaalpha/factors/library.py`
- 因子写库调用链
- 多周期验证结果回写逻辑

### 新增字段

```python
{
    "evaluation": {
        "status": "pending_validation | active | degraded | stale | deprecated",
        "last_validated": "2026-03-14T10:00:00",
        "stability_score": 0.85,
        "period_results": [...],
        "validation_summary": "..."
    },
    "data_requirements": {
        "fields": ["$close", "$volume"],
        "dimensions": ["price_volume"]
    }
}
```

### 状态集合

| 状态 | 含义 |
|------|------|
| `pending_validation` | 新因子入库，待验证 |
| `active` | 验证通过，可正常使用 |
| `degraded` | 复验分数明显下降 |
| `stale` | 长时间未验证 |
| `deprecated` | 已淘汰 |

### 状态流转规则

1. 新因子入库时设为 `pending_validation`
2. 多周期验证通过后更新为 `active`
3. 复验分数明显下降时更新为 `degraded`
4. 长时间未验证时更新为 `stale`
5. 人工淘汰或连续失败时更新为 `deprecated`

---

## Risk Points

1. 历史因子库升级可能存在兼容性问题
2. 状态流转规则需要根据实际使用调优
3. 新增字段可能增加文件体积

---

## Rollback Plan

- 因子库读取逻辑兼容无新字段的旧格式
- 状态字段为可选，不影响核心回测流程
- 可通过配置禁用状态自动更新

---

## Final Result

> 待实施后填写

---

## Validation Evidence

> 待实施后填写

---

## Lessons Learned

> 待实施后填写
