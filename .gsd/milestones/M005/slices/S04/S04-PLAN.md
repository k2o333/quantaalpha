# S04: 停止对不可恢复 BadRequest 重试

**Goal:** `_try_create_chat_completion_or_embedding()` 遇到不可恢复的 BadRequestError（如 invalid model name）时立即重抛，不消耗重试次数。
**Demo:** 配置了无效模型名时，系统立即抛出异常退出，而不会重试 10 次。

## Must-Haves

- `except openai.BadRequestError` 分支中包含 `"Invalid model" in error_str` 快速失败守卫
- 守卫触发时记录 `logger.error(...)` 输出失败模型名称
- 守卫通过裸 `raise` 立即退出，不落入重试循环

## Verification

- `python -m py_compile quantaalpha/llm/client.py` — 语法正确
- `grep -n "Invalid model" quantaalpha/llm/client.py` — 守卫存在（line 808）
- `grep -n "^                raise$" quantaalpha/llm/client.py` — 裸 raise 存在

## Tasks

- [x] **T01: 添加 BadRequestError 快速失败守卫** `est:5m`
  - Why: 消除无效重试浪费、暴露配置错误
  - Files: `quantaalpha/llm/client.py`
  - Do: 在 `except openai.BadRequestError` 中添加 `"Invalid model" in error_str` 守卫，立即 raise
  - Verify: `python -m py_compile && grep -n "Invalid model"`
  - Done when: 守卫存在且语法正确

## Files Likely Touched

- `quantaalpha/llm/client.py`

---

estimated_steps: 2
estimated_files: 1
skills_used:
  - review
  - systematic-debugging
