# S03: 修复 JSON 控制字符未转义

**Goal:** 在 JSON fix 逻辑中添加控制字符转义，使包含多行文本的 JSON 能被正确解析
**Demo:** LLM 返回包含换行符的 JSON 响应时，能被成功解析而不再报 "Invalid control character"

## Must-Haves

- `_create_chat_completion_inner_function` 的 JSON fix 逻辑处理控制字符
- 转义换行符 `\n`、回车 `\r`、制表符 `\t` 等常见控制字符
- 保留现有 LaTeX 反斜杠修复逻辑

## Verification

- `python -m py_compile third_party/quantaalpha/quantaalpha/llm/client.py` 通过
- 代码审查确认控制字符转义逻辑在 LaTeX 修复之后、第二次 `json.loads` 之前

## Observability / Diagnostics

- Runtime signals: 成功转义时记录日志 "Fixed JSON control characters"
- Inspection surfaces: 日志显示 "JSON fix failed" 次数减少
- Failure visibility: 控制字符导致的解析错误被消除

## Integration Closure

- Upstream surfaces consumed: S01 修复后的空响应检测
- New wiring introduced: 控制字符转义逻辑
- What remains: 无，这是最后一个修复

## Tasks

- [ ] **T01: 添加控制字符转义逻辑** `est:25m`
  - Why: JSON 字符串中的实际换行符等控制字符导致解析失败
  - Files: `third_party/quantaalpha/quantaalpha/llm/client.py`
  - Do: 在 JSON fix 逻辑中（约 line 1068 后，第二次 `json.loads` 之前）添加控制字符转义：将实际换行符替换为 `\\n`，实际回车替换为 `\\r`，实际制表符替换为 `\\t`。注意：只替换未转义的控制字符（前面没有反斜杠的）
  - Verify: `grep -n "\\\\n" third_party/quantaalpha/quantaalpha/llm/client.py | grep -A2 -B2 "fixed_resp"` 找到转义逻辑
  - Done when: 控制字符被正确转义，JSON 解析成功率提高

## Files Likely Touched

- `third_party/quantaalpha/quantaalpha/llm/client.py`
