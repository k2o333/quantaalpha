---
id: S02
parent: M001
milestone: M001
provides:
  - proposal.py 有限重试循环 MAX_RETRIES=10
  - client.py 流式/非流式空响应检查
  - 循环结束 RuntimeError 异常
requires:
  - slice: S01
    provides: 日志系统修复
affects: [S03, S04]
key_files:
  - third_party/quantaalpha/quantaalpha/factors/proposal.py
  - third_party/quantaalpha/quantaalpha/llm/client.py
key_decisions:
  - "MAX_RETRIES=10：重试上限设为10次，平衡成功率与资源消耗"
  - "空响应返回空字符串而非抛异常：让调用方的重试逻辑统一处理"
patterns_established:
  - "所有重试循环必须有明确上限，禁止 while True"
  - "空响应检测放在重试循环内部"
drill_down_paths:
  - .gsd/milestones/M001/slices/S02/S02-PLAN.md
duration: 40min
verification_result: pass
completed_at: 2026-03-22T00:00:00Z
---

# S02: 修复无限重试死循环和空响应检查

**将 `while True` 改为 `for attempt in range(MAX_RETRIES)` 并在循环内添加空响应检测，消除 factor_construct 阶段的进程卡死**

## What Happened

proposal.py 的 `_convert_with_history_limit` 方法中 `while True` 循环在遇到持续的 JSON 解析失败时
导致进程无限挂起。改为有限重试 (MAX_RETRIES=10) 并在 client.py 的流式/非流式路径之后添加空响应检测。
空响应返回空字符串，让重试逻辑统一处理。达到上限后抛出 RuntimeError。

## Deviations
None

## Files Created/Modified
- `third_party/quantaalpha/quantaalpha/factors/proposal.py` — line 483 有限循环, 491-494 空响应检查, 615 RuntimeError
- `third_party/quantaalpha/quantaalpha/llm/client.py` — line 1022-1027 流式空响应检查, 1034-1038 非流式空响应检查
