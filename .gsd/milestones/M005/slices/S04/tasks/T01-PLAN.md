# T01: 添加 BadRequestError 快速失败守卫

**Slice:** S04 — 停止对不可恢复 BadRequest 重试
**Milestone:** M005 (Mining Pipeline 关键 Bug 修复)

## Description

在 `_try_create_chat_completion_or_embedding()` 的 `BadRequestError` 异常处理器中添加早期守卫，检测不可恢复的错误（如 invalid model name）后立即 `raise`，不消耗重试次数。

## Steps

1. 在 `quantaalpha/llm/client.py` 的 `except openai.BadRequestError` 处理器中：
   - 将 `e.message` 替换为 `error_str = str(e)` 以提高健壮性
   - 在日志输出后立即检查 `"Invalid model" in error_str`
   - 若检测到不可恢复错误：使用 `self.embedding_model` 或 `self.chat_model` 记录实际失败的模型名
   - 通过裸 `raise` 立即重抛（保留原始 traceback，不创建新异常类型）

2. 验证语法正确且只有目标修改：
   - `python -m py_compile quantaalpha/llm/client.py` 通过
   - `grep -n "Invalid model" quantaalpha/llm/client.py` 输出行号 808

## Must-Haves

- [ ] `except openai.BadRequestError` 分支中包含 `"Invalid model" in error_str` 守卫
- [ ] 守卫触发时记录 `logger.error(...)` 输出失败的模型名称
- [ ] 守卫通过裸 `raise` 立即退出，不落入重试逻辑

## Verification

```bash
# 语法检查
python -m py_compile quantaalpha/llm/client.py

# 确认守卫存在
grep -n "Invalid model" quantaalpha/llm/client.py

# 确认 raise 语句存在（无参数）
grep -n "^                raise$" quantaalpha/llm/client.py
```

## Inputs

- `quantaalpha/llm/client.py` — 需要修改的源文件

## Expected Output

- `quantaalpha/llm/client.py` — 添加了 BadRequestError 快速失败守卫
