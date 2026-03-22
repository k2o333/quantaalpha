# Bug Report: LLM JSON Responses Fail to Parse Due to Unescaped Control Characters

## Bug Title
JSON parsing fails with "Invalid control character at: line X column Y (char Z)" when LLM responses contain unescaped newlines or other control characters in JSON strings.

## Root Cause Analysis

The issue occurs in the JSON parsing pipeline when LLM generates JSON responses containing **actual newline characters** (U+000A) or other control characters inside JSON string values. According to the JSON specification (RFC 8259), control characters (U+0000 to U+001F) must be escaped when they appear within strings.

### Code Flow

1. **LLM Response Generation** (`_create_chat_completion_inner_function`):
   - When `json_mode=True` or `reasoning_flag=True`, the code extracts JSON from the response (lines 1047-1051)
   - The response often contains markdown code blocks like ` ```json ... ``` `

2. **Initial JSON Parse Attempt** (line 1054):
   ```python
   json.loads(resp)
   ```
   This fails when the JSON string contains unescaped control characters.

3. **JSON Fix Logic** (lines 1056-1075):
   ```python
   # Fix LaTeX backslash: \text, \frac etc. misinterpreted as escapes
   latex_commands = ['text', 'frac', 'left', 'right', 'times', 'cdot', 'sqrt', 'sum', 'prod', 'int']
   for cmd in latex_commands:
       fixed_resp = re.sub(r'(?<!\\)\\(' + cmd + r')', r'\\\\\1', fixed_resp)
   
   # Fix other invalid escapes: \_ \{ \} etc.
   fixed_resp = re.sub(r'(?<!\\)\\([_\{\}\[\]])', r'\\\\\1', fixed_resp)
   ```
   **The fix logic only handles LaTeX backslashes and specific escape sequences, but does NOT handle control characters.**

4. **Second Parse Attempt** (line 1071):
   ```python
   json.loads(fixed_resp)
   ```
   This still fails because control characters remain unescaped.

5. **Warning Logged** (line 1075):
   ```python
   logger.warning(f"JSON fix failed: {e2}, using raw response")
   ```

6. **Downstream Parsing** (`robust_json_parse` in `build_messages_and_create_chat_completion_json`):
   - The raw response (with unescaped control characters) is passed to `robust_json_parse`
   - All parsing strategies fail, and a `json.JSONDecodeError` is raised with message "Could not parse JSON; original text length: ..."

### Why This Happens

LLMs frequently generate JSON responses with **multi-line string values** that contain actual newline characters. For example:

```json
{
  "Observations": "
1. **Performance Analysis**:
   - The current combined result shows **improvement**...
```

The newline after `"Observations": "` is an actual newline character (U+000A), not the escaped sequence `\n`. This is valid in prose but invalid in JSON strings.

## Code Locations

### Primary Issue
- **File**: `/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/llm/client.py`
- **Function**: `_create_chat_completion_inner_function`
- **Lines**: 1047-1075 (JSON extraction and fix logic)
- **Problem**: Lines 1061-1068 only fix LaTeX backslashes, not control characters

### Related Code
- **File**: `/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/llm/client.py`
- **Function**: `robust_json_parse` (lines 153-218)
- **Helper Functions**:
  - `_escape_common_json_sequences` (lines 110-131): Only handles LaTeX commands
  - `_remove_trailing_commas` (lines 134-135)
  - `_close_truncated_json` (lines 138-149)

### Error Propagation
- **File**: `/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/feedback.py`
- **Lines**: 170-183: JSON parse retry logic catches `json.JSONDecodeError` and retries
- **Lines**: 306-314: Similar retry logic in `AlphaAgentQlibFactorHypothesisExperiment2Feedback`

- **File**: `/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py`
- **Lines**: 101-128: Calls `build_messages_and_create_chat_completion_json` and catches exceptions

## Evidence from Logs

### Terminal Log: `/home/quan/testdata/aspipe_v4/third_party/facotors/terminal/20260321_214610.txt`

**Pattern 1: "line 2 column 20 (char 21)"**
```
Line 1096: 2026-03-21 21:51:20.917 | WARNING  | quantaalpha.llm.client:_create_chat_completion_inner_function:1075 - JSON fix failed: Invalid control character at: line 2 column 20 (char 21), using raw response
Line 1097: 2026-03-21 21:51:20.929 | WARNING  | quantaalpha.factors.feedback:generate_feedback:306 - [AlphaAgent] JSON parse failed (attempt 1/3): Could not parse JSON; original text length: 8944: line 1 column 1 (char 0)
```

**Pattern 2: "line 4 column 33 (char 83)"**
```
Line 286: 2026-03-21 21:48:48.614 | WARNING  | quantaalpha.llm.client:_create_chat_completion_inner_function:1075 - JSON fix failed: Invalid control character at: line 4 column 33 (char 83), using raw response
Line 287: 2026-03-21 21:48:48.627 | ERROR    | quantaalpha.factors.regulator.consistency_checker:check_consistency:128 - Consistency check error: Could not parse JSON; original text length: 4896: line 1 column 1 (char 0)
```

**Frequency**: The error occurs **48+ times** in the terminal log, indicating a systemic issue.

### Error Message Analysis
- "Invalid control character at: line 2 column 20 (char 21)" suggests a newline character at position 21 in the JSON string
- The position "char 21" aligns with the opening quote and the first newline in a multi-line string value

## Is This a Code Bug or LLM Output Issue?

**This is primarily a CODE BUG**, not just an LLM output issue. Reasons:

1. **LLM Behavior is Expected**: LLMs naturally generate multi-line text with newlines. This is standard behavior for language models producing prose content.

2. **JSON Specification Requires Escaping**: The JSON spec requires control characters to be escaped in strings. The code should handle this.

3. **Incomplete Fix Logic**: The existing fix logic (lines 1061-1068) demonstrates awareness that LLM output needs post-processing, but it's incomplete—it only handles LaTeX backslashes, not control characters.

4. **No Fallback for Control Characters**: The `robust_json_parse` function and its helpers don't attempt to escape control characters either.

5. **Systemic Occurrence**: The error occurs dozens of times, indicating it's not an edge case but a common scenario.

## Suggested Fix

### Option 1: Escape Control Characters in the Fix Logic (Recommended)

Add control character escaping to the JSON fix logic in `_create_chat_completion_inner_function`:

```python
# In _create_chat_completion_inner_function, after line 1068:
# Escape control characters in JSON strings
# Replace actual newlines/tabs/etc. with escaped versions
control_char_map = {
    '\n': '\\n',
    '\r': '\\r',
    '\t': '\\t',
    '\b': '\\b',
    '\f': '\\f',
}
for char, escape in control_char_map.items():
    # Only replace if not already escaped
    fixed_resp = fixed_resp.replace(char, escape)
```

### Option 2: Use `json.dumps` with `ensure_ascii=False` on the Raw Response

Before attempting to parse, normalize the JSON string:

```python
# Try to parse as JSON after escaping control characters
try:
    # First, try to load as-is
    json.loads(resp)
except json.JSONDecodeError:
    # If fails, escape control characters and retry
    import codecs
    # Use a more robust approach: escape all control characters
    escaped_resp = resp.encode('unicode_escape').decode('ascii')
    # But this might over-escape, so be careful
```

### Option 3: Enhance `robust_json_parse` to Handle Control Characters

Add a pre-processing step in `robust_json_parse`:

```python
def _escape_control_chars_in_json_strings(text: str) -> str:
    """
    Escape control characters that appear inside JSON string values.
    This is a best-effort approach using regex to find string values.
    """
    # Pattern to match JSON string values (simplified)
    # Matches: "key": "value with potential control chars"
    def escape_control_in_match(match):
        string_content = match.group(1)
        # Escape control characters
        string_content = string_content.replace('\n', '\\n')
        string_content = string_content.replace('\r', '\\r')
        string_content = string_content.replace('\t', '\\t')
        return f'"{string_content}"'
    
    # This is complex; simpler approach: escape all unescaped control chars
    result = []
    i = 0
    in_string = False
    escape_next = False
    
    while i < len(text):
        char = text[i]
        
        if escape_next:
            result.append(char)
            escape_next = False
            i += 1
            continue
        
        if char == '\\':
            result.append(char)
            escape_next = True
            i += 1
            continue
        
        if char == '"':
            in_string = not in_string
            result.append(char)
            i += 1
            continue
        
        if in_string and ord(char) < 32:  # Control character
            # Escape it
            escape_map = {'\n': '\\n', '\r': '\\r', '\t': '\\t', '\b': '\\b', '\f': '\\f'}
            if char in escape_map:
                result.append(escape_map[char])
            else:
                result.append(f'\\u{ord(char):04x}')
            i += 1
            continue
        
        result.append(char)
        i += 1
    
    return ''.join(result)
```

### Option 4: Use `strict=False` in `json.loads` (Python 3.12+)

If using Python 3.12+, the `json.loads` function supports `strict=False` which allows control characters:

```python
json.loads(resp, strict=False)
```

However, this requires Python 3.12+ and may not be available in all environments.

## Recommended Implementation

**Implement Option 1** as it's the simplest and most targeted fix. Add control character escaping to the existing fix logic in `_create_chat_completion_inner_function`. This ensures that:

1. The fix is applied at the point where JSON parsing is attempted
2. It works with the existing retry/fallback logic
3. It doesn't require changes to the downstream `robust_json_parse` function
4. It's backward compatible

## Additional Notes

- The error pattern "line 2 column 20 (char 21)" suggests the newline appears early in the JSON string (after the opening quote and some initial text)
- The error "line 4 column 33 (char 83)" suggests a similar issue deeper in the response
- The `robust_json_parse` function already attempts multiple parsing strategies, but none handle control characters
- The retry logic in feedback.py (lines 170-183) will re-request the LLM, but the same issue may recur if the LLM continues to generate unescaped control characters
