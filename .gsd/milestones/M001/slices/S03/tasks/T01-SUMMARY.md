---
id: T01
parent: S03
milestone: M001
provides:
  - client.py:_escape_control_chars_in_json 添加状态机转义控制字符
requires:
  - slice: S02
    provides: LLM 流式安全拦截
affects: [S04]
key_files:
  - third_party/quantaalpha/quantaalpha/llm/client.py
key_decisions:
  - "只转义 JSON 字符串内部的控制字符，使用双指针/flag追踪引号开关"
patterns_established:
  - "模型吐出的含脏控字符强力清洗"
drill_down_paths:
  - .gsd/milestones/M001/slices/S03/tasks/T01-PLAN.md
duration: 25min
verification_result: pass
completed_at: 2026-03-22T00:00:00Z
---

# T01: 增加 JSON 控制字符转义逻辑

**实现 _escape_control_chars_in_json 状态机函数清洗输出中的非法 \n \r \t**

## What Happened
在 LaTeX 处理之后、二次 json.loads 之前调用状态机进行清洗转义。

## Deviations
None

## Files Created/Modified
- `third_party/quantaalpha/quantaalpha/llm/client.py` — 添加清洗状态机
