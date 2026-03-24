---
id: T03
parent: S01
milestone: M001
provides:
  - universe.py:_coerce_date f-string 修复
requires: []
affects: [S02, S03]
key_files:
  - third_party/quantaalpha/quantaalpha/backtest/universe.py
key_decisions: []
patterns_established: []
drill_down_paths:
  - .gsd/milestones/M001/slices/S01/tasks/T03-PLAN.md
duration: 10min
verification_result: pass
completed_at: 2026-03-22T00:00:00Z
---

# T03: 修复 _coerce_date 日志参数错误

**修复 backtest/universe.py 中的 logger.warning 调用，使用 f-string 替代多参数**

## What Happened
将 `logger.warning("...%s ", value)` 改为 f-string。

## Deviations
None

## Files Created/Modified
- `third_party/quantaalpha/quantaalpha/backtest/universe.py` — 修复 logger 参数
