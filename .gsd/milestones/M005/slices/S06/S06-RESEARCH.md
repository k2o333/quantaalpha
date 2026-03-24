# S06: 集中 JSON 转义修复 — Research

## Slice Overview
**Goal:** `_escape_common_json_sequences()` 需要添加通用反斜杠转义 regex，所有 JSON 修复路径共用此实现，消除重复代码。

**Success Criteria:**
- `_escape_common_json_sequences()` 包含通用反斜杠转义 regex
- 所有 JSON 修复路径共用同一 `_escape_common_json_sequences()` 实现
- 无分散的部分实现

---

## What Exists

### Current Implementation

**`_escape_common_json_sequences()` (lines 107-127):**
```python
def _escape_common_json_sequences(text: str) -> str:
    fixed_text = text
    latex_commands = [
        "text", "frac", "left", "right", "times", "cdot", "sqrt",
        "sum", "prod", "int", "alpha", "beta", "gamma", "delta",
    ]
    for cmd in latex_commands:
        fixed_text = re.sub(r"(?<!\\)\\(" + cmd + r")", r"\\\\\1", fixed_text)
    fixed_text = re.sub(r"(?<!\\)\\([_\{\}\[\]])", r"\\\\\1", fixed_text)
    return fixed_text
```
- Handles specific LaTeX commands
- Handles LaTeX special chars `_{}[]`
- **Missing**: generic backslash escape fallback for unrecognized escapes

**Inline duplicate in `ChatCache._build_response()` (lines ~1073-1079):**
```python
# Fix LaTeX backslash: \text, \frac etc. misinterpreted as escapes
latex_commands = ['text', 'frac', 'left', 'right', 'times', 'cdot', 'sqrt', 'sum', 'prod', 'int']
for cmd in latex_commands:
    fixed_resp = re.sub(r'(?<!\\)\\(' + cmd + r')', r'\\\\\1', fixed_resp)
# Fix other invalid escapes: \_ \{ \} etc.
fixed_resp = re.sub(r'(?<!\\)\\([_\{\}\[\]])', r'\\\\\1', fixed_resp)
```
- **Problem**: Duplicate of `_escape_common_json_sequences()` logic
- **Problem**: Lacks the generic backslash escape regex

**`_escape_control_chars_in_json()` (lines 1087-1112):**
```python
def _escape_control_chars_in_json(text):
    result = []
    in_string = False
    escape_next = False
    for char in text:
        # ... state machine to escape control chars inside strings
```
- Handles control characters (newline, tab, etc.) inside JSON strings
- Only called from `ChatCache._build_response()`, not from `robust_json_parse()`

---

## What Needs to Change

### Problem Analysis

1. **Duplicate LaTeX fix code**: The inline LaTeX fix in `ChatCache._build_response()` duplicates the logic in `_escape_common_json_sequences()`. This violates DRY and creates maintenance risk.

2. **Missing generic backslash escape regex**: The code only handles specific LaTeX commands but doesn't have a fallback for unrecognized backslash sequences like `\_` or `\~`. The proposed fix:
   ```python
   re.sub(r'\\(?!["\\\/bfnrtu])', r'\\\\', text)
   ```
   This regex matches any backslash NOT followed by a valid JSON escape char and doubles it.

3. **Inconsistent JSON repair paths**: `robust_json_parse()` uses `_escape_common_json_sequences()` but NOT `_escape_control_chars_in_json()`. The `ChatCache._build_response()` does the opposite.

### Required Changes

1. **Enhance `_escape_common_json_sequences()`** to add generic backslash escape:
   ```python
   # After existing LaTeX handling, add:
   # Fix all unrecognized backslash escapes (generic fallback)
   fixed_text = re.sub(r'\\(?!["\\\/bfnrtu])', r'\\\\', fixed_text)
   ```

2. **Replace inline LaTeX fix in `ChatCache._build_response()`** with call to `_escape_common_json_sequences()`:
   ```python
   # Replace lines 1073-1079 with:
   fixed_resp = _escape_common_json_sequences(fixed_resp)
   ```

3. **Consider integrating `_escape_control_chars_in_json`** - either:
   - Call it after `_escape_common_json_sequences()` in both paths
   - Or merge it into `_escape_common_json_sequences()` itself

---

## Files to Modify

| File | Change |
|-------|--------|
| `quantaalpha/llm/client.py` | Enhance `_escape_common_json_sequences()`, replace inline LaTeX fix |
| `third_party/quantaalpha/quantaalpha/llm/client.py` | Same changes (sync) |

---

## Verification Strategy

### Test Cases for Generic Backslash Escape

```python
# Test: unrecognized backslash sequences should be double-escaped
input1 = '{"expr": "PE \\_ 10"}'  # \_ is invalid
# Expected: '{"expr": "PE \\\\_ 10"}'

input2 = '{"expr": "close \\~ open"}'  # \~ is invalid  
# Expected: '{"expr": "close \\~ open"}' (valid JSON escape, should not change)

input3 = '{"expr": "a \\b c"}'  # \b is valid (backspace), keep
# Expected: unchanged

input4 = '{"expr": "a \\n b"}'  # \n is valid (newline in string)
# Expected: unchanged

# Test combined with LaTeX
input5 = '{"expr": "\\frac{close}{open} \\_ 10"}'
# Expected: both \frac and \_ properly escaped
```

### Verification Commands

```bash
# Syntax check
python -m py_compile third_party/quantaalpha/quantaalpha/llm/client.py

# Functional test
python -c "
from quantaalpha.llm.client import _escape_common_json_sequences
import json

# Test 1: Generic backslash escape
test1 = '{\"expr\": \"PE \\_ 10\"}'
result1 = _escape_common_json_sequences(test1)
assert json.loads(result1), f'Failed to parse: {result1}'
print(f'Test 1 passed: {result1}')

# Test 2: Valid JSON escapes preserved
test2 = '{\"expr\": \"line1\\nline2\"}'
result2 = _escape_common_json_sequences(test2)
assert json.loads(result2), f'Failed to parse: {result2}'
assert '\\\\n' not in result2, 'Should not double-escape valid \\\\n'
print(f'Test 2 passed: {result2}')

# Test 3: LaTeX + generic combined
test3 = '{\"expr\": \"\\\\frac{close}{open}\"}'
result3 = _escape_common_json_sequences(test3)
assert json.loads(result3), f'Failed to parse: {result3}'
print(f'Test 3 passed: {result3}')
"
```

---

## Implementation Plan

1. **Enhance `_escape_common_json_sequences()`**:
   - Keep existing LaTeX command handling
   - Keep existing `_{}[]` handling
   - Add generic backslash escape regex at the end

2. **Refactor `ChatCache._build_response()`**:
   - Replace inline LaTeX fix with `_escape_common_json_sequences(fixed_resp)`
   - Keep `_escape_control_chars_in_json()` call (or optionally integrate)

3. **Sync to vendored copy**:
   - Apply identical changes to `third_party/quantaalpha/quantaalpha/llm/client.py`
   - Verify with diff

---

## Key Design Decision

**Single vs. Multiple Functions**: Keep `_escape_common_json_sequences()` as the single entry point for LaTeX/generic escape handling. `_escape_control_chars_in_json()` handles a different concern (control characters vs. backslash escapes) so it can remain separate but should be called from both JSON repair paths.
