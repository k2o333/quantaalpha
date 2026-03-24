# T01: 完善 _escape_common_json_sequences 并统一调用处

**Slice:** S06 — 集中 JSON 转义修复
**Milestone:** M005

## Description

在 `quantaalpha/llm/client.py` 中完成两件事：1) 在 `_escape_common_json_sequences()` 末尾添加 generic backslash escape fallback regex（处理 `\_`、`\~` 等无效转义）；2) 将 `ChatCache._build_response()` 中 lines 1076-1079 的内联 LaTeX 修复循环替换为对 `_escape_common_json_sequences()` 的单行调用，消除重复代码。`_escape_control_chars_in_json()` 保持不变（处理不同 concern）。

## Steps

1. 读取 `quantaalpha/llm/client.py`，找到 `_escape_common_json_sequences()` 函数（lines 107-127 附近），在 `return fixed_text` 之前插入一行：

   ```python
   # Fix all unrecognized backslash escapes (generic fallback)
   fixed_text = re.sub(r'\\(?!["\\\/bfnrtu])', r'\\\\', fixed_text)
   ```

   这个 regex 匹配任何不以反斜杠开头的反斜杠后跟非 JSON 合法转义字符（`"`、`\`、`/`、`b`、`f`、`n`、`r`、`t`、`u`），将其双写转义。

2. 读取 `ChatCache._build_response()` 中的内联 LaTeX 修复代码（lines 1076-1079 附近），找到：

   ```python
   latex_commands = ['text', 'frac', 'left', 'right', 'times', 'cdot', 'sqrt', 'sum', 'prod', 'int']
   for cmd in latex_commands:
       fixed_resp = re.sub(r'(?<!\\)\\(' + cmd + r')', r'\\\\\1', fixed_resp)
   # Fix other invalid escapes: \_ \{ \} etc.
   fixed_resp = re.sub(r'(?<!\\)\\([_\{\}\[\]])', r'\\\\\1', fixed_resp)
   ```

   将其替换为单行：

   ```python
   fixed_resp = _escape_common_json_sequences(fixed_resp)
   ```

3. 保留 `_escape_control_chars_in_json()` 函数及其在 `ChatCache._build_response()` 中的调用（line 1113 附近），因为它处理的是控制字符（与 backslash escape 是不同 concern）。

4. 运行语法检查：`python -m py_compile quantaalpha/llm/client.py`

5. 运行 Python 断言测试验证 generic fallback 正确工作：

   ```python
   python -c "
   from quantaalpha.llm.client import _escape_common_json_sequences
   import json

   # Test 1: Generic backslash escape - \_ should be double-escaped
   t1 = '{\"expr\": \"PE \\_ 10\"}'
   r1 = _escape_common_json_sequences(t1)
   json.loads(r1)  # must not raise
   print('Test 1 OK:', r1)

   # Test 2: Valid JSON escape \n preserved
   t2 = '{\"expr\": \"line1\\nline2\"}'
   r2 = _escape_common_json_sequences(t2)
   json.loads(r2)
   assert r2 == t2, 'Should not change valid \\n'
   print('Test 2 OK: valid \\\\n preserved')

   # Test 3: LaTeX + generic combined
   t3 = '{\"expr\": \"\\\\frac{close}{open} \\_ 10\"}'
   r3 = _escape_common_json_sequences(t3)
   json.loads(r3)
   print('Test 3 OK:', r3)

   # Test 4: Valid escape \b preserved
   t4 = '{\"expr\": \"a\\b c\"}'
   r4 = _escape_common_json_sequences(t4)
   json.loads(r4)
   assert r4 == t4, 'Should not change valid \\b'
   print('Test 4 OK: valid \\\\b preserved')

   print('All tests passed!')
   "
   ```

## Must-Haves

- [ ] `_escape_common_json_sequences()` 包含 generic fallback regex
- [ ] `ChatCache._build_response()` 不再有内联 `latex_commands` for 循环
- [ ] `_escape_control_chars_in_json()` 及其调用保持不变
- [ ] 语法检查通过

## Verification

- `python -m py_compile quantaalpha/llm/client.py` — 无输出表示通过
- `rg "latex_commands" quantaalpha/llm/client.py` — 应只在 `_escape_common_json_sequences()` 函数内出现（lines 109-125 附近），不应在 `ChatCache._build_response()` 中出现
- Python 断言测试全部通过（见步骤 5）

## Inputs

- `quantaalpha/llm/client.py` — 待修改的主文件

## Expected Output

- `quantaalpha/llm/client.py` — 修改后的主文件（含 generic fallback 和统一调用）
