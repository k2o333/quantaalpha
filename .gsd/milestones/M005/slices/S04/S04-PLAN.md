# S04: 停止对不可恢复 BadRequest 重试

**Goal:** 让 `client.py` 遇到不可恢复的 BadRequestError（如 invalid model）时快速抛出。
**Demo:** 如果请求配错了模型名称，系统将立即抛异常退出，而不重试 10 次。

## Must-Haves
- 捕获 BadRequestError 后检查 `str(e)`，如果是 invalid model 则立马 raise。

## Tasks

- [ ] **T01: 重构 _try_create_chat_completion_or_embedding**
  增加 BadRequestError 的 catch 和判断逻辑。

## Files Likely Touched
- `quantaalpha/llm/client.py`
- `third_party/quantaalpha/quantaalpha/llm/client.py`
