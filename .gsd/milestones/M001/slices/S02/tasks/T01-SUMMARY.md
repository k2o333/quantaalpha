---
id: T01
parent: S02
milestone: M001
provides:
  - client.py 增加响应结果为空的拦截
requires:
  - slice: S01
    provides: f-string 修复
affects: [S03, S04]
key_files:
  - third_party/quantaalpha/quantaalpha/llm/client.py
key_decisions:
  - "空响应作为正常空字符串返回由调用层处理逻辑重试"
patterns_established: []
drill_down_paths:
  - .gsd/milestones/M001/slices/S02/tasks/T01-PLAN.md
duration: 15min
verification_result: pass
completed_at: 2026-03-22T00:00:00Z
---

# T01: LLMClient 空响应截获

**在 client.py 流式和非流式调用中添加空响应检查，拦截下游解析异常**

## What Happened
流式完成后检查是否非空，非流式检查是否非空。记录日志并返回空字符串。

## Deviations
None

## Files Created/Modified
- `third_party/quantaalpha/quantaalpha/llm/client.py` — 空响应拦截
