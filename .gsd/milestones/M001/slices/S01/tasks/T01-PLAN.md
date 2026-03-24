# T01: 修复 client.py:69-74 的 logger.warning 调用
**Slice:** S01  **Milestone:** M001
## Goal
修复 `log_tokenizer_fallback_once()` 中 `%s` 格式为 f-string。
## Must-Haves
### Truths
- `grep -n 'logger.warning(f"Tokenizer' client.py` 找到修复后的代码
### Artifacts
- `third_party/quantaalpha/quantaalpha/llm/client.py` line 69-74 已修改
## Steps
1. 将 `logger.warning("Tokenizer lookup failed for model %s; ...", model, ...)` 改为 f-string。
