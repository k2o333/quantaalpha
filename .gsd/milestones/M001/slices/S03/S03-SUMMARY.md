---
id: S03
parent: M001
milestone: M001
provides:
  - _escape_control_chars_in_json 状态机函数
  - JSON 字符串内部控制字符转义
requires:
  - slice: S01
    provides: 日志系统修复
affects: [S04]
key_files:
  - third_party/quantaalpha/quantaalpha/llm/client.py
key_decisions:
  - "使用状态机跟踪 JSON 字符串边界：只转义字符串内部的控制字符，不破坏结构空白"
patterns_established:
  - "JSON 控制字符转义必须区分字符串内部和外部"
drill_down_paths:
  - .gsd/milestones/M001/slices/S03/S03-PLAN.md
duration: 25min
verification_result: pass
completed_at: 2026-03-22T00:00:00Z
---

# S03: 修复 JSON 控制字符未转义

**添加 `_escape_control_chars_in_json` 状态机函数，只转义 JSON 字符串内部的控制字符（\n \r \t 等），不破坏 JSON 结构空白**

## What Happened

client.py 的 JSON fix 逻辑只处理 LaTeX 反斜杠，不处理控制字符。
新增 `_escape_control_chars_in_json` 函数通过状态机追踪是否在 JSON 字符串内部，
只在字符串内部转义控制字符。放在 LaTeX 修复之后、第二次 json.loads 之前。

## Deviations
None

## Files Created/Modified
- `third_party/quantaalpha/quantaalpha/llm/client.py` — line 1078-1102 添加 _escape_control_chars_in_json 函数
