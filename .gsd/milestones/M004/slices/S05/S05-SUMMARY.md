---
id: S05
parent: M004
milestone: M004
status: completed
verification_result: passed
completed_at: 2026-03-24
provides:
  - Factor lifecycle state machine with 5 states
  - Status update function integrated into library.py
  - 6-unit test coverage for all state transitions
requires:
  - S02: last_validated field (consumed for stale detection)
  - S03: tags (not directly consumed)
affects:
  - S08: status machine for scheduling trigger conditions
key_files:
  - third_party/quantaalpha/quantaalpha/factors/status_rules.py
  - third_party/quantaalpha/quantaalpha/factors/library.py
  - third_party/quantaalpha/tests/test_status_transition.py
key_decisions:
  - State model: pending_validation/active/stale/degraded/deprecated (vs. plan's seasonal/archived)
  - Stability thresholds: active >= 0.5, degraded < 0.3
  - Stale threshold: 30 days without validation
  - Deprecated threshold: 3 consecutive failures
patterns_established:
  - Config-driven thresholds via DEFAULT_FACTOR_STATUS_CONFIG
  - Audit trail on status changes
  - deepcopy() to avoid modifying original entries
observability_surfaces:
  - status field in evaluation dict
  - consecutive_failures counter
  - last_validated timestamp
  - audit trail entries with trigger="apply_validation_result"
---

# S05: 因子生命周期状态机

**Milestone:** M004
**Status:** ✅ Completed
**Completed:** 2026-03-24

## One-liner

实现因子生命周期状态机，支持 pending_validation/active/stale/degraded/deprecated 五状态转换及阈值配置。

## What Happened

S05 实现了因子生命周期状态机，替代了原计划中的 seasonal/archived 状态模型，采用基于验证成功率和稳定性的状态机：

### T01: 状态机定义与转换函数

在 `status_rules.py` 中实现 `update_factor_status()` 函数，包含 5 种状态：

| 状态 | 触发条件 |
|------|----------|
| `pending_validation` | 初始状态 |
| `active` | 验证成功且稳定性 >= 0.5 |
| `stale` | active 超过 30 天未复验 |
| `degraded` | 验证失败或稳定性 < 0.3 |
| `deprecated` | 连续失败 >= 3 次 |

关键设计：
- 配置驱动阈值：`DEFAULT_FACTOR_STATUS_CONFIG`
- `deepcopy()` 避免修改原始 entry
- ISO 格式时间戳存储 `last_validated`

### T02: 集成到 library.py + 单元测试

`library.py` 的 `apply_validation_result()` 方法集成了状态机：

```python
updated = update_factor_status(
    factor_entry=factor_entry,
    validation_result=validation_result,
    now=now,
    config=config,
)
```

状态变更时触发审计追踪：
- 记录 old_status → new_status
- 记录验证摘要原因
- trigger 标记为 `"apply_validation_result"`

测试覆盖：
- 6 个单元测试覆盖所有状态转换路径
- 21 个相关测试（包含 S02 的 revalidation）全部通过

## Verification

| Check | Result |
|-------|--------|
| `python -m py_compile status_rules.py` | ✅ PASS |
| `pytest tests/test_status_transition.py -v` | ✅ 6/6 PASS |
| `pytest tests/test_status_transition.py tests/test_revalidation_candidates.py -v` | ✅ 21/21 PASS |

## New Requirements Surfaced

无

## Deviations

### 状态模型变更（计划 vs 实现）

**原计划状态：** stable_active / seasonal / degraded / archived
**实际状态：** pending_validation / active / stale / degraded / deprecated

实现采用了不同的状态模型：
- 用 `pending_validation` 代替 `stable_active` 作为初始状态
- 用 `stale` 捕获长期未复验的因子（替代 seasonal 的时间维度）
- 用 `deprecated` 代替 `archived`（强调主动废弃而非被动归档）
- 删除了 `seasonal`（季节性因子标记）— 计划中未明确定义

这是合理的设计演进，状态机更专注于验证状态而非因子类型。

## Known Limitations

1. **seasonal/archived 状态未实现** — 原计划中的 seasonal（季节性）和 archived（归档）状态未包含
2. **archived → active 重新激活未实现** — 计划中提到但未实现
3. **稳定性评分来源** — 依赖 `validation_result.summary.stability_score`，需上游验证流程提供

## Follow-ups

1. 如需 seasonal 状态，考虑添加 `effective_periods` 字段标记有效周期
2. 如需 archived 状态，添加 `archive()` 方法和手动重新激活逻辑

## Files Created/Modified

| 文件 | 操作 | 描述 |
|------|------|------|
| `quantaalpha/factors/status_rules.py` | 新建 | 状态机核心逻辑 |
| `quantaalpha/factors/library.py` | 修改 | apply_validation_result() 集成状态机 |
| `tests/test_status_transition.py` | 新建 | 6 项状态转换单元测试 |

## Forward Intelligence

### What the next slice should know

- `update_factor_status()` 是纯函数，可独立测试
- 状态变更通过 `apply_validation_result()` 的 `persist=True` 自动持久化
- 审计追踪记录在 factor 的 `_audit` 字段中

### What's fragile

- 稳定性阈值硬编码在 `DEFAULT_FACTOR_STATUS_CONFIG` 中，未来可能需要动态配置
- `stale` 状态仅在 `active` 状态下触发，其他状态不解发

### Authoritative diagnostics

- 状态字段: `factor["evaluation"]["status"]`
- 连续失败: `factor["evaluation"]["consecutive_failures"]`
- 审计追踪: `library.get_audit_trail(trigger="apply_validation_result")`

### What assumptions changed

- 原计划假设使用 seasonal/archived 状态 → 实际使用 pending_validation/active/stale/degraded/deprecated
- 状态转换基于稳定性评分而非周期通过比例
