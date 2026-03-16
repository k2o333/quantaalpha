# 多周期稳定性结果接入 Evolution

Status: implemented
Owner: QuantaAlpha team
Created: 2026-03-14
Outcome: implemented
Phase: 2
Depends-on:
- /home/quan/testdata/aspipe_v4/docs/03-changes/quantaalpha/implemented/2026-03-14-multi-period-validation.md
- /home/quan/testdata/aspipe_v4/docs/03-changes/quantaalpha/implemented/2026-03-14-factor-library-schema-extension.md
Related-to: /home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/2026-03-14-quantaalpha-continuous-factor-implementation-checklist.md

---

## Background

当前 evolution 更偏向使用最近一次结果或短期收益作为父因子选择依据，这会让短期偶然胜出的因子被过度放大。多周期验证做出来以后，如果不接入 evolution，它只会停留在“存档信息”，不会真正改变搜索行为。

---

## Goal

让多周期稳定性结果参与 evolution 的三个关键决策：

- parent 选择
- 候选因子分流
- 低质量因子的淘汰

---

## Non-goals

- 不重写 evolution controller 的整体调度结构。
- 不做自动修复链路。
- 不把稳定性作为唯一排序指标。

---

## Acceptance Criteria

1. `active` 且高稳定性的因子在 parent 选择中优先级更高。
2. `degraded`、`stale`、`deprecated` 因子不会与 `active` 因子走同一条演化路径。
3. 可通过配置关闭稳定性介入，回到旧行为。

---

## Design Decision

### 接入点

优先在以下模块接入，而不是散落在 prompt 层：

- `quantaalpha/pipeline/factor_mining.py`
- `quantaalpha/pipeline/evolution/controller.py`
- `quantaalpha/pipeline/evolution/trajectory.py`

### 首版策略

```python
def select_parent_factors(candidates, n=3):
    active = [f for f in candidates if f["evaluation"]["status"] == "active"]
    active.sort(
        key=lambda f: (
            f["evaluation"].get("stability_score") or 0.0,
            f.get("backtest_results", {}).get("ic", 0.0),
        ),
        reverse=True,
    )
    return active[:n]
```

```python
def route_factor_by_status(factor):
    status = factor["evaluation"]["status"]
    if status == "active":
        return "evolution_pool"
    if status == "stale":
        return "revalidate_queue"
    if status == "degraded":
        return "repair_or_hold"
    return "excluded"
```

### 配置结构

```yaml
evolution:
  parent_selection:
    prefer_active: true
    min_stability_score: 0.5
    exclude_statuses: ["deprecated", "pending_validation"]
  factor_routing:
    stale: "revalidate"
    degraded: "hold"
```

---

## Affected Modules

- `third_party/quantaalpha/quantaalpha/pipeline/factor_mining.py`
- `third_party/quantaalpha/quantaalpha/pipeline/evolution/controller.py`
- `third_party/quantaalpha/quantaalpha/pipeline/evolution/trajectory.py`

---

## Implementation Plan

1. 在 parent 候选读取阶段接入 `evaluation.status` 和 `stability_score`。
2. 把排序逻辑封装成可测试函数，而不是直接写在控制器流程里。
3. 对无稳定性数据的新因子定义保守行为，例如仅参与原始池、不参与高优先级 parent 选择。
4. 将状态分流结果写入日志或 trajectory 元数据，方便复盘。
5. 提供配置开关，允许完全忽略稳定性。

---

## Test Plan

### 单元测试

1. parent 排序会优先 `active` 且 `stability_score` 更高的因子。
2. `deprecated` 和 `pending_validation` 因子不会进入 parent 候选池。
3. 无稳定性分数的因子会按降级策略处理，而不是直接报错。

### 集成测试

4. evolution 运行时，选出的 parent 与预期状态和分数一致。
5. `stale` 和 `degraded` 因子会被分流到非演化主路径。
6. 关闭配置后，parent 选择退回旧逻辑。

### 手工验收

7. 对比接入前后的一个 evolution round，确认 parent 选择日志出现稳定性相关依据。

---

## Risk Points

1. 如果稳定性阈值过高，新因子可能很难进入演化主路径。
2. 过度依赖稳定性会降低探索多样性。
3. 如果排序逻辑写在多个模块里，结果会不可解释。

---

## Rollback Plan

- 提供 `ignore_stability` 或等价配置开关。
- 保留旧的 parent 选择策略函数。
- 若效果不稳定，可先只做候选过滤，不改排序权重。

---

## Final Result

- 多周期稳定性结果已接入 evolution 的 parent 选择与候选分流逻辑。
- 当前是首版保守接入，不是完全重写 evolution controller。
- 后续又补了运行期改进：
  - debug 成功项会提前退出
  - 后续轮次更偏向只处理失败项
- 这些运行期优化与本变更目标一致，进一步减少了低价值重复调试。

---

## Validation Evidence

- 连续因子特性测试已覆盖 stability 参与排序/分流的最小行为。
- README、模块文档和验收草案已补充“多周期验证后让 evolution 优先选稳定因子”的场景。
- 实际运行中 trajectory pool 已带有 routing/selection 相关元信息。

---

## Lessons Learned

- 稳定性如果只写入库不参与选择，就只是“存档字段”。
- 演化策略里应先做保守排序与分流，再考虑更激进的淘汰策略。
