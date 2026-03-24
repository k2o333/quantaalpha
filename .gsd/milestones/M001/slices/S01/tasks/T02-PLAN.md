# T02: 修复 client.py:667 的 logger.warning 调用
**Slice:** S01  **Milestone:** M001
## Goal
修复 `get_model_for_task()` 中 `%s` 格式为 f-string。
## Must-Haves
### Truths
- `grep "logger.warning" client.py | grep -c "%s,"` 返回 0
### Artifacts
- `third_party/quantaalpha/quantaalpha/llm/client.py` line 667 已修改
## Steps
1. 将 `logger.warning("Unknown llm task_type=%s...", task_type)` 改为 f-string。
