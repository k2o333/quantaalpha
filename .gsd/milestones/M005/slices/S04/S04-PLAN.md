# S04: 停止对不可恢复 BadRequest 重试

**Goal:** 让 `client.py` 遇到不可恢复的 BadRequestError（如 invalid model）时快速抛出。
**Demo:** 如果请求配错了模型名称，系统将立即抛异常退出，而不重试 10 次。

## Must-Haves
- 捕获 BadRequestError 后检查 `str(e)`，如果是 invalid model 则立马 raise。

## Tasks

- [ ] **T01: 重构 _try_create_chat_completion_or_embedding** ✅ 2026-03-24
  增加 BadRequestError 的 catch 和判断逻辑。

  **变更内容：**
  - `error_str = str(e)` 替换 `e.message`（更健壮）
  - `"Invalid model" in error_str` 守卫：在入口处检测不可恢复错误
  - 检测到后立即 `raise`（保留原 traceback）
  - 日志输出实际失败的模型名（chat 或 embedding）

  **文件变更：**
  - `quantaalpha/llm/client.py` (+8 lines, -2 lines)
  - submodule commit: `7b15e5d`
  - parent commit: `62793a1`

  **验证：**
  - `python -m py_compile quantaalpha/llm/client.py` → ✅
  - `grep -n "Invalid model" quantaalpha/llm/client.py` → line 808
