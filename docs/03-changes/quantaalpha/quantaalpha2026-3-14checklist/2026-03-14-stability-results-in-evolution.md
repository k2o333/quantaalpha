# 多周期稳定性结果接入 Evolution

Status: draft
Owner: QuantaAlpha team
Created: 2026-03-14
Outcome: pending
Phase: 2
Depends-on:
- /home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/quantaalpha2026-3-14checklist/2026-03-14-multi-period-validation.md
- /home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/quantaalpha2026-3-14checklist/2026-03-14-factor-library-schema-extension.md
Related-to: /home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/2026-03-14-quantaalpha-continuous-factor-implementation-checklist.md

---

## Background

当前因子演化（evolution）只依赖短期单次回测结果：
- parent 选择不考虑稳定性
- degraded 因子仍可能被选为 parent
- 演化方向缺乏长期视角

---

## Goal

让多周期验证结果参与因子演化过程：
- 优先选择 `stability_score` 更高的因子作为 mutation parent
- `degraded` 因子优先进入复验或轻量修复
- `stale` 因子进入复验队列

---

## Non-goals

- 不实现自动因子修复
- 不改变现有 evolution 算法核心
- 不实现跨因子融合

---

## Acceptance Criteria

1. 验证结果真正反馈到因子演化链路
2. evolution 不再只依赖短期单次回测结果

---

## Test Plan

### 单元测试

1. parent 选择函数会读取稳定性信息
2. 高稳定性因子在候选排序中优先级更高

### 集成测试

3. `degraded`、`stale` 因子被正确分流
4. evolution 流程完整运行且使用稳定性信息

### 手工验收

5. 观察一个 evolution 任务中 parent 选择是否考虑稳定性

---

## Implementation Plan

### 主要修改点

- evolution 相关模块
- 因子筛选逻辑
- trajectory 选择逻辑

### 首版策略

```python
def select_parent_factors(candidates, n=3):
    # 优先选择 active 状态
    active_factors = [f for f in candidates if f.evaluation.status == "active"]
    
    # 按 stability_score 排序
    active_factors.sort(key=lambda f: f.evaluation.stability_score, reverse=True)
    
    return active_factors[:n]

def route_factor_by_status(factor):
    status = factor.evaluation.status
    
    if status == "degraded":
        return "repair_queue"  # 进入修复队列
    elif status == "stale":
        return "revalidate_queue"  # 进入复验队列
    elif status == "active":
        return "evolution_pool"  # 可参与演化
    else:
        return "excluded"  # 不参与演化
```

### 配置结构

```yaml
evolution:
  parent_selection:
    min_stability_score: 0.5
    prefer_active: true
    exclude_statuses: ["deprecated", "pending_validation"]
  
  factor_routing:
    degraded: "repair"
    stale: "revalidate"
```

---

## Risk Points

1. 过度依赖稳定性可能限制探索多样性
2. 新因子因无稳定性数据可能被排除
3. 需要平衡稳定性与创新性

---

## Rollback Plan

- 稳定性筛选可通过配置禁用
- 保留仅依赖单次回测结果的演化路径
- 提供 `--ignore-stability` 选项强制使用旧行为

---

## Final Result

> 待实施后填写

---

## Validation Evidence

> 待实施后填写

---

## Lessons Learned

> 待实施后填写
