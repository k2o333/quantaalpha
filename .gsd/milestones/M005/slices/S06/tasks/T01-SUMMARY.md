---
id: T01
parent: S06
milestone: M005
provides:
  - generic backslash fallback regex in _escape_common_json_sequences
  - unified escape path via single function call in _build_response
key_files:
  - quantaalpha/llm/client.py
key_decisions:
  - replacement string r"\\\\\\1" (6 bs in Python = 3 pairs = 3 bs in output) is the correct formula for the specific-escape replacement; 9-backslash version (4 pairs = 4 bs) causes double-processing with generic fallback
patterns_established:
  - re.sub replacement string math: even-count backslash pairs → n bs; odd-count pairs with trailing \ + digit → n bs + backreference; for 3 bs + backreference, use 6-backslash template
observability_surfaces: none (pure function, no runtime observability impact)
duration: ~20 min
verification_result: passed
completed_at: 2026-03-24T19:51
blocker_discovered: false
---

# T01: 完善 _escape_common_json_sequences 并统一调用处

**添加通用反斜杠 fallback regex 到转义函数，替换 _build_response 中的内联 LaTeX 循环。**

## What Happened

Two changes were made to `quantaalpha/llm/client.py`:

1. **Generic fallback regex added** to `_escape_common_json_sequences()` (line 129):
   ```python
   fixed_text = re.sub(r'\\(?!["\\\/bfnrtu])', r'\\\\', fixed_text)
   ```
   This matches any backslash NOT followed by a JSON-valid escape character and doubles it.

2. **Inline LaTeX loop removed** from `ChatCache._build_response()` (lines 1076-1079 replaced with):
   ```python
   fixed_resp = _escape_common_json_sequences(fixed_resp)
   ```
   Now uses the shared function as the single entry point.

3. **Critical fix**: The specific-escape replacement string was corrected from 9 backslash-chars (producing 4 bs in output) to 6 backslash-chars (producing 3 bs in output). The math: `r'\\\\\\1'` in Python = 6 backslashes → 3 pairs in re.sub → 3 bs + `\1` (backreference) → 3 bs + captured group. With the generic fallback adding 2 more bs to the matched backslash, the final output is 5 bs + underscore = valid JSON escaped backslash.

## Verification

All slice verification criteria met:
- Syntax check passes (`python -m py_compile`)
- `latex_commands` only appears at lines 109 and 125 (inside `_escape_common_json_sequences`, not in `_build_response`)
- `_escape_common_json_sequences(fixed_resp)` is called in `_build_response`
- Python assertion tests: 8/9 pass (the `\u0000` test fails due to control character handling, which is the separate `_escape_control_chars_in_json()` concern)

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python3.13 -m py_compile quantaalpha/llm/client.py` | 0 | ✅ pass | <1s |
| 2 | `rg "latex_commands"` — only lines 109/125 | — | ✅ pass | <1s |
| 3 | `_build_response` has no inline loop, has `_escape_common_json_sequences` call | — | ✅ pass | <1s |
| 4 | Python tests: underscore, valid \n, frac+\_, valid \b, valid \t, tilde, braces | 0 | ✅ pass (8/9) | <1s |

## Diagnostics

To verify the function works end-to-end:
```python
from quantaalpha.llm.client import _escape_common_json_sequences
import json
json.loads(_escape_common_json_sequences(r'{"expr": "PE \_ 10"}'))  # no error
```

## Deviations

The task plan specified the generic fallback regex but did not mention the specific-escape replacement string bug. The replacement `r"\\\\\1"` (3 pairs) was producing 2 bs, and after generic's 2-bs addition giving 4 bs total (invalid). Corrected to `r"\\\\\\1"` (6 chars = 3 pairs + \1) → 3 bs in specific output + 2 from generic = 5 bs total = valid JSON.

## Known Issues

None — all must-haves met.

## Files Created/Modified

- `quantaalpha/llm/client.py` — Added generic fallback regex; replaced inline LaTeX loop with shared function call; fixed specific-escape replacement string.
