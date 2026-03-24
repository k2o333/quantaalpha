---
id: T01
parent: S01
milestone: M001
provides:
  - client.py:log_tokenizer_fallback_once f-string 修复
requires: []
affects: [S02, S03]
key_files:
  - third_party/quantaalpha/quantaalpha/llm/client.py
key_decisions:
  - "使用 f-string 消除 %s 参数不匹配错误"
patterns_established:
  - "RDAgentLog.warning 必须使用 f-string"
drill_down_paths:
  - .gsd/milestones/M001/slices/S01/tasks/T01-PLAN.md
duration: 10min
verification_result: pass
completed_at: 2026-03-22T00:00:00Z
---

# T01: 修复 log_tokenizer_fallback_once 日志参数错误

**修复 log_tokenizer_fallback_once 中的 logger.warning 调用，使用 f-string 替代多参数**

## What Happened
将 `logger.warning("...", model, ...)` 改为 f-string。

## Deviations
None

## Files Created/Modified
- `third_party/quantaalpha/quantaalpha/llm/client.py` — 修复 logger 参数
