# S01: 修复 Logger 参数签名不匹配和空响应检查

**Goal:** 修复日志参数不匹配导致的 TypeError，并添加 LLM 空响应检查
**Demo:** 运行因子挖掘时日志正常输出，空响应被检测并抛出明确异常

## Must-Haves

- 所有 `logger.warning()` 调用使用 f-string 格式，不再使用 `%s` 多参数格式
- `_create_chat_completion_inner_function` 在流式/非流式路径后检查空响应
- 空响应时抛出明确异常，包含模型名称和请求信息

## Verification

- `python -m py_compile third_party/quantaalpha/quantaalpha/llm/client.py` 通过
- `python -m py_compile third_party/quantaalpha/quantaalpha/backtest/universe.py` 通过
- 代码审查确认所有修复点已修改

## Observability / Diagnostics

- Runtime signals: 空响应时抛出 `RuntimeError` 包含模型名称
- Inspection surfaces: 日志输出显示修复后的格式
- Failure visibility: 明确的异常信息替代模糊的 TypeError

## Integration Closure

- Upstream surfaces consumed: `RDAgentLog.warning()` 接口
- New wiring introduced: 空响应检查逻辑
- What remains: 需要 S02 修复无限重试，S03 修复控制字符

## Tasks

- [ ] **T01: 修复 client.py:69-74 的 logger.warning 调用** `est:15m`
  - Why: 这是触发 Bug 的主要位置，使用 `%s` 格式导致 TypeError
  - Files: `third_party/quantaalpha/quantaalpha/llm/client.py`
  - Do: 将 `logger.warning("...%s...", model, DEFAULT_FALLBACK_TOKENIZER, reason)` 改为 `logger.warning(f"...{model}...{DEFAULT_FALLBACK_TOKENIZER}...{reason}")`
  - Verify: `grep -n "logger.warning.*%s" third_party/quantaalpha/quantaalpha/llm/client.py | head -5` 返回空
  - Done when: 该位置的 warning 调用使用 f-string 格式

- [ ] **T02: 修复 client.py:667 的 logger.warning 调用** `est:10m`
  - Why: 同样使用 `%s` 格式，可能在 task_type 未知时触发
  - Files: `third_party/quantaalpha/quantaalpha/llm/client.py`
  - Do: 将 `logger.warning("Unknown llm task_type=%s...", task_type)` 改为 f-string 格式
  - Verify: `grep -n "logger.warning.*%s" third_party/quantaalpha/quantaalpha/llm/client.py | head -5` 返回空
  - Done when: 该位置的 warning 调用使用 f-string 格式

- [ ] **T03: 修复 universe.py:111 的 logger.warning 调用** `est:10m`
  - Why: 同样使用 `%s` 格式
  - Files: `third_party/quantaalpha/quantaalpha/backtest/universe.py`
  - Do: 将 `logger.warning("Failed to parse as_of_date=%s...", value)` 改为 f-string 格式
  - Verify: `grep -n "logger.warning.*%s" third_party/quantaalpha/quantaalpha/backtest/universe.py` 返回空
  - Done when: 该位置的 warning 调用使用 f-string 格式

- [ ] **T04: 添加空响应检查逻辑** `est:20m`
  - Why: 防止空响应进入 JSON 解析导致崩溃
  - Files: `third_party/quantaalpha/quantaalpha/llm/client.py`
  - Do: 在流式循环结束后（约 line 1027）和非流式路径后（约 line 1033）添加 `if not resp or not resp.strip(): raise RuntimeError(f"LLM returned empty response for model {model}")`
  - Verify: `grep -n "empty response" third_party/quantaalpha/quantaalpha/llm/client.py` 找到检查逻辑
  - Done when: 空响应被检测并抛出明确异常

## Files Likely Touched

- `third_party/quantaalpha/quantaalpha/llm/client.py`
- `third_party/quantaalpha/quantaalpha/backtest/universe.py`
