# S06: 集中 JSON 转义修复

**Goal:** 将处理 JSON 转义的 regex 添加到 `_escape_common_json_sequences()` 并复用。
**Demo:** 不论是从 chat 还是 embedding 走的 JSON 提取逻辑，都能处理杂散的反斜杠转义。

## Must-Haves
- 实现 regex `re.sub(r'\\(?!["\\\\/bfnrtu])', r'\\\\', text)`。
- 系统统一走 `_escape_common_json_sequences()`。

## Tasks

- [ ] **T01: 完善 _escape_common_json_sequences 并统一调用处**

## Files Likely Touched
- `quantaalpha/llm/client.py`
- `third_party/quantaalpha/quantaalpha/llm/client.py`
