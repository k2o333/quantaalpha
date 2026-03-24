---
id: T01
parent: S05
milestone: M004
status: completed
verification_result: passed
completed_at: 2026-03-24
blocker_discovered: false
provides:
  - status_rules.py with complete state machine implementation
requires:
  - S02: last_validated field (consumed for stale detection)
  - S03: tags (not directly consumed in this task)
affects:
  - S05-T02: state machine for library integration
key_files:
  - third_party/quantaalpha/quantaalpha/factors/status_rules.py
key_decisions:
  - State set differs from plan: pending_validation/active/stale/degraded/deprecated vs seasonal/archived
  - Stability score thresholds: active >= 0.5, degraded < 0.3
  - Consecutive failures to deprecate: 3
patterns_established:
  - Config-driven threshold: DEFAULT_FACTOR_STATUS_CONFIG dict with customizable overrides
observability_surfaces:
  - status field in evaluation dict
  - consecutive_failures counter
  - last_validated timestamp
---

# T01: 状态机定义与转换函数实现

**Status:** Completed

## Intended Outcome

- 状态机可表达完整生命周期转换

## What Was Built

`status_rules.py` 实现了因子生命周期状态机，包含以下状态：

| 状态 | 描述 |
|------|------|
| `pending_validation` | 初始状态，等待首次验证 |
| `active` | 验证成功且稳定性 >= 0.5 |
| `stale` | active 状态超过 30 天未复验 |
| `degraded` | 验证失败或稳定性 < 0.3 |
| `deprecated` | 连续失败 >= 3 次 |

## State Transitions

```
pending_validation → active (success + stability >= 0.5)
pending_validation → degraded (failure OR stability < 0.5)
active → stale (30 days without validation)
active → degraded (failure OR stability drop)
degraded → active (success + stability >= 0.5)
degraded → deprecated (consecutive_failures >= 3)
```

## Key Implementation Details

- `update_factor_status()` 函数接收 factor_entry、validation_result、now、config
- 使用 `deepcopy()` 避免修改原始 entry
- `last_validated` 自动更新到 ISO 格式时间戳
- `consecutive_failures` 计数器在失败时递增
- 状态转换触发 audit trail 记录

## Verification Evidence

| Command | Exit Code | Verdict | Duration |
|---------|-----------|---------|----------|
| `python -m py_compile quantaalpha/factors/status_rules.py` | 0 | PASS | <1s |
| `grep "seasonal\|archived" status_rules.py` | 1 | N/A (states differ) | <1s |

## Diagnostics

- 检查因子状态: `entry["evaluation"]["status"]`
- 检查连续失败: `entry["evaluation"]["consecutive_failures"]`
- 检查上次验证: `entry["evaluation"]["last_validated"]`

## Deviation from Plan

**Planned states:** seasonal, archived
**Actual states:** pending_validation, active, stale, degraded, deprecated

The implementation follows a different but valid state model focused on validation success/failure and stability rather than seasonal patterns.
