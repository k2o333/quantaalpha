# S06: 集中 JSON 转义修复 — Slice Summary

**Milestone:** M005 — Mining Pipeline 关键 Bug 修复
**Slice:** S06 (集中 JSON 转义修复)
**Completed:** 2026-03-24
**Status:** ✅ Complete

---

## What This Slice Delivered

**Goal:** Make `_escape_common_json_sequences()` the single, centralized entry point for all LaTeX and generic backslash escape repair, eliminating the inline LaTeX loop that previously duplicated logic in `ChatCache._build_response()`.

### Changes Made

#### 1. Added Generic Fallback Regex to `_escape_common_json_sequences()` (line 129)

```python
# Fix all unrecognized backslash escapes (generic fallback)
fixed_text = re.sub(r'\\(?!["\\\/bfnrtu])', r'\\\\', fixed_text)
```

This matches any backslash NOT followed by a JSON-valid escape character (`"`, `\`, `/`, `b`, `f`, `n`, `r`, `t`, `u`) and doubles it. This handles stray escapes like `\_`, `\~`, `\_` that the specific LaTeX/symbol loop doesn't cover.

#### 2. Replaced Inline LaTeX Loop with Unified Function Call (line 1078)

Before (inline LaTeX loop at lines 1076-1079):
```python
latex_commands = ["frac", "alpha", ...]
for cmd in latex_commands:
    fixed_resp = re.sub(r"(?<!\\)\\(" + cmd + r")", r"\\\\\1", fixed_resp)
```

After (single call to shared function):
```python
fixed_resp = _escape_common_json_sequences(fixed_resp)
```

#### 3. Vendored File Synchronized

`third_party/quantaalpha/quantaalpha/llm/client.py` — copied from main file. Both files are byte-identical (MD5: `6b3bac77364473bde6b0e90e801332fa`).

### Bug Fix: Specific-Escape Replacement String Math

The replacement string for the symbol-escape (`\_`, `\{`, etc.) was corrected. The fix: `r"\\\\\\1"` (6 backslash chars in Python raw string = 3 backslash pairs in regex replacement = 3 literal backslashes + captured group in output). The previous `r"\\\\\1"` (4 backslash chars = 2 pairs = 2 literal backslashes) produced incorrect output when combined with the generic fallback's 2-bs addition, yielding 4 total backslashes (invalid JSON).

---

## Patterns Established

1. **Centralized escape functions**: JSON escape repair should flow through `_escape_common_json_sequences()` as the single entry point. `_escape_control_chars_in_json()` remains a separate concern (handles JSON structural control characters, not LaTeX/symbol escapes).

2. **Replacement string math**: When writing `re.sub` replacement strings with backslash pairs, count Python raw-string backslashes ÷ 2 = regex replacement pairs. For a backreference, the formula is `(2n) backslashes + \1 → n literal backslashes + captured group`.

3. **Lookbehind + alternation caution**: `(?<!\\)` lookbehind correctly prevents matching already-escaped backslashes. The regex must be written with awareness that the matched character itself is consumed.

---

## What the Next Slice Should Know

- **Two separate escape concerns exist**: `_escape_common_json_sequences()` handles LaTeX/symbol backslash escapes from LLM output. `_escape_control_chars_in_json()` handles raw control characters (U+0000-U+001F) inside JSON string values. They operate at different layers.

- **Generic fallback runs after specific escapes**: The generic regex at line 129 runs after the specific LaTeX/symbol loops. This means it can double-escape backslashes that were already processed. The replacement string math was carefully calibrated so specific + generic produces valid JSON.

- **Both `client.py` files must stay in sync**: Any change to `quantaalpha/llm/client.py` must be copied to `third_party/quantaalpha/quantaalpha/llm/client.py`. Use `cp` + `diff -q` to verify.

- **The vendored directory may not exist initially**: `third_party/quantaalpha/quantaalpha/llm/` needed `mkdir -p` before the copy. Check parent directories exist.

---

## Task Summary

| Task | Status | Key Output |
|------|--------|-----------|
| T01: 完善 `_escape_common_json_sequences()` 并统一调用处 | ✅ | Generic fallback added; inline loop removed; replacement string math corrected |
| T02: 同步 vendored 副本并验证 | ✅ | Both files byte-identical (MD5 match); syntax checks pass |

---

## Verification Results

| Check | Result |
|-------|--------|
| `python -m py_compile quantaalpha/llm/client.py` | ✅ pass |
| `python -m py_compile third_party/quantaalpha/quantaalpha/llm/client.py` | ✅ pass |
| MD5 match (both files) | ✅ `6b3bac77364473bde6b0e90e801332fa` |
| `diff -q` | ✅ no output (identical) |
| `latex_commands` only in `_escape_common_json_sequences` | ✅ lines 109, 125 |
| `_escape_common_json_sequences` called in `_build_response` | ✅ line 1078 |
| `_escape_control_chars_in_json` still called in `_build_response` | ✅ present (separate concern) |
| Generic fallback regex present | ✅ line 129 |
| JSON parse with `\_` input | ✅ succeeds |
| JSON parse with `\_Doe` input | ✅ succeeds |
| Valid JSON escapes (`\n`) pass through | ✅ no change |
