# S06: 集中 JSON 转义修复

**Goal:** `_escape_common_json_sequences()` 包含通用反斜杠转义 regex，所有 JSON 修复路径共用此实现，消除重复代码。
**Demo:** 含杂散反斜杠的 JSON（如 `\_`、`\~`）通过统一修复路径解析；`_escape_common_json_sequences()` 是唯一的 LaTeX/通用转义入口。

## Must-Haves

- `_escape_common_json_sequences()` 末尾添加 `re.sub(r'\\(?!["\\\/bfnrtu])', r'\\\\', fixed_text)` generic fallback。
- `ChatCache._build_response()` 中 lines 1076-1079 的内联 LaTeX 修复替换为 `_escape_common_json_sequences(fixed_resp)`。
- 两份 `client.py`（主目录 + vendored）MD5 一致。

## Verification

- `python -m py_compile quantaalpha/llm/client.py` 无语法错误
- `python -m py_compile third_party/quantaalpha/quantaalpha/llm/client.py` 无语法错误
- `md5sum quantaalpha/llm/client.py third_party/quantaalpha/quantaalpha/llm/client.py` 两文件 MD5 一致
- `rg "_escape_common_json_sequences" quantaalpha/llm/client.py | grep -v "^107:" | grep "latex_commands"` 返回空（内联 LaTeX 循环已移除）
- Python 断言测试（见 T01）全部通过

## Tasks

- [x] **T01: 完善 _escape_common_json_sequences 并统一调用处** `est:15m`
  - Why: 在 `quantaalpha/llm/client.py` 中添加 generic backslash escape fallback，将 `ChatCache._build_response()` 的内联 LaTeX 循环替换为 `_escape_common_json_sequences()` 调用，消除重复代码。
  - Files: `quantaalpha/llm/client.py`
  - Do: 在 `_escape_common_json_sequences()` 末尾 `return fixed_text` 之前插入 generic regex；在 `ChatCache._build_response()` 中将 lines 1076-1079 的内联 LaTeX 修复替换为单行调用 `_escape_common_json_sequences(fixed_resp)`；`_escape_control_chars_in_json()` 保持不变（处理不同 concern）。
  - Verify: `python -m py_compile quantaalpha/llm/client.py && python -c "from quantaalpha.llm.client import _escape_common_json_sequences; import json; t='{\"x\": \"\_ 10\"}'; r=_escape_common_json_sequences(t); json.loads(r); print('OK')"`
  - Done when: `_escape_common_json_sequences()` 包含 generic fallback regex；内联 LaTeX 循环已从 `ChatCache._build_response()` 移除；`_escape_control_chars_in_json()` 调用保留；语法检查通过；Python 断言测试通过

- [ ] **T02: 同步 vendored 副本并验证** `est:5m`
  - Why: `third_party/quantaalpha/quantaalpha/llm/client.py` 必须与主副本 byte-identical，保持 vendored 导入路径正常工作。
  - Files: `third_party/quantaalpha/quantaalpha/llm/client.py`
  - Do: 将 T01 修改后的 `quantaalpha/llm/client.py` cp 到 vendored 路径；用 `diff -q` 验证两份文件一致；运行 `python -m py_compile` 验证语法。
  - Verify: `md5sum quantaalpha/llm/client.py third_party/quantaalpha/quantaalpha/llm/client.py` 两文件 MD5 一致；两份文件 diff 返回空
  - Done when: vendored 文件与主文件 byte-identical；两份语法检查通过

## Files Likely Touched

- `quantaalpha/llm/client.py`
- `third_party/quantaalpha/quantaalpha/llm/client.py`

---
estimated_steps: 6
estimated_files: 2
skills_used:
  - systematic-debugging
  - test
