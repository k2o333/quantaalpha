---
id: S01
parent: M001
milestone: M001
provides:
  - logger.warning() 调用统一使用 f-string 格式
  - client.py:69-74 log_tokenizer_fallback_once 修复
  - client.py:667 get_model_for_task 修复
  - backtest/universe.py:111 _coerce_date 修复
requires: []
affects: [S02, S03]
key_files:
  - third_party/quantaalpha/quantaalpha/llm/client.py
  - third_party/quantaalpha/quantaalpha/backtest/universe.py
key_decisions:
  - "使用 f-string 替代 %s 格式：RDAgentLog.warning() 不兼容标准 logging API"
patterns_established:
  - "日志调用一律使用 f-string 而非 %s 多参数格式"
drill_down_paths:
  - .gsd/milestones/M001/slices/S01/S01-PLAN.md
duration: 35min
verification_result: pass
completed_at: 2026-03-22T00:00:00Z
---

# S01: 修复 Logger 参数签名不匹配

**修复了3处 `logger.warning()` 调用中的 `%s` 多参数格式，统一改为 f-string，消除 `TypeError: warning() takes 2 positional arguments` 异常**

## What Happened

client.py 和 universe.py 中三处 `logger.warning()` 使用了标准 logging 的 `%s` 多参数模式，
但 `RDAgentLog.warning()` 只接受单个 `msg` 参数。改为 f-string 后日志正常输出，
不再掩盖底层异常。

## Deviations
None

## Files Created/Modified
- `third_party/quantaalpha/quantaalpha/llm/client.py` — line 69-74, 667 改为 f-string
- `third_party/quantaalpha/quantaalpha/backtest/universe.py` — line 111 改为 f-string
