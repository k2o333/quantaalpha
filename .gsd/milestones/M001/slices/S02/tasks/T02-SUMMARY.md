---
id: T02
parent: S02
milestone: M001
provides:
  - proposal.py 采用 MAX_RETRIES 有限循环
requires:
  - slice: S01
    provides: f-string 修复
affects: [S04]
key_files:
  - third_party/quantaalpha/quantaalpha/factors/proposal.py
key_decisions:
  - "设置因子提案最大重试次数为 10 次"
patterns_established:
  - "消除不可控死循环，改为有限重试后触发 RuntimeError"
drill_down_paths:
  - .gsd/milestones/M001/slices/S02/tasks/T02-PLAN.md
duration: 15min
verification_result: pass
completed_at: 2026-03-22T00:00:00Z
---

# T02: 修复无限重试死循环

**将 factor_construct 中的 while True 改为有限次数的 for-loop**

## What Happened
`proposal.py` 内部使用 `for attempt in range(MAX_RETRIES)` 并在耗尽时抛错。

## Deviations
None

## Files Created/Modified
- `third_party/quantaalpha/quantaalpha/factors/proposal.py` — 修复重试循环
