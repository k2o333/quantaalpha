# S03: 修复 JSON 控制字符未转义

**Goal:** 在 JSON fix 逻辑中添加控制字符转义，使包含多行文本的 JSON 能被正确解析
**Demo:** LLM 返回包含换行符的 JSON 响应时，能被成功解析而不再报 "Invalid control character"

## Must-Haves

- `_create_chat_completion_inner_function` 的 JSON fix 逻辑**添加**控制字符转义处理
- 转义换行符 `\n`、回车 `\r`、制表符 `\t` 等常见控制字符
- 保留现有 LaTeX 反斜杠修复逻辑

## Verification

- `python -m py_compile third_party/quantaalpha/quantaalpha/llm/client.py` 通过
- 代码审查确认控制字符转义逻辑在 LaTeX 修复之后、第二次 `json.loads` 之前

## Observability / Diagnostics

- Runtime signals: 成功转义时记录日志 **"Fixed JSON format issues"**（与实际代码一致）
- Inspection surfaces: 日志显示 "JSON fix failed" 次数减少
- Failure visibility: 控制字符导致的解析错误被消除

## Integration Closure

- Upstream surfaces consumed: S02 修复后的空响应检查
- New wiring introduced: 控制字符转义逻辑
- What remains: 无，这是 M001 最后一个修复（但 `'dict' object has no attribute 'replace'` 错误留待 M002 处理）

## Tasks

- [ ] **T01: 添加控制字符转义逻辑** `est:25m`
  - Why: JSON fix 逻辑**未设计**为处理控制字符（当前只处理 LaTeX 反斜杠），需要**添加**控制字符转义
  - Files: `third_party/quantaalpha/quantaalpha/llm/client.py`
  - Do: 
    在第二次 `json.loads` 尝试之前（约 line 1068 后），添加控制字符转义：
    ```python
    # 在 LaTeX 修复后，添加控制字符处理
    # 匹配实际换行符（前面不是反斜杠的）
    fixed_resp = re.sub(r'(?<!\)\n', r'\\n', fixed_resp)
    fixed_resp = re.sub(r'(?<!\)\r', r'\\r', fixed_resp)
    fixed_resp = re.sub(r'(?<!\)\t', r'\\t', fixed_resp)
    ```
    或使用更简单的方法（先处理已转义的控制字符，再处理实际控制字符）：
    ```python
    # 方法2: 统一转义实际控制字符
    control_char_map = {
        '\n': '\\n',
        '\r': '\\r',
        '\t': '\\t',
    }
    for char, escape in control_char_map.items():
        # 只替换实际的控制字符，不触碰已转义的
        fixed_resp = fixed_resp.replace(char, escape)
    ```
  - Verify: 
    - 代码审查：确认 `fixed_resp.replace` 或 `re.sub` 逻辑在 LaTeX 修复之后
    - 检查 `grep -n "\\\\n"` 或类似模式定位转义逻辑（注意 shell 转义）
    - 更好的验证：检查 `"Fixed JSON format issues"` 日志消息是否在控制字符修复后被打印
  - Done when: 控制字符被正确转义，JSON 解析成功率提高

## Files Likely Touched

- `third_party/quantaalpha/quantaalpha/llm/client.py`

## Notes

- **实际日志消息**: 代码中实际的日志消息是 `"Fixed JSON format issues"`（line 1073），不是 "Fixed JSON control characters"
- **修复位置**: 在 `client.py:1061-1068`（LaTeX 修复）之后，第二次 `json.loads` 尝试之前
- **M002 待处理问题**: `'dict' object has no attribute 'replace'` 错误（consistency check 数据类型问题）不在本切片范围内
