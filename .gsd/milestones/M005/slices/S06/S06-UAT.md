# S06: 集中 JSON 转义修复 — UAT

**Milestone:** M005
**Slice:** S06
**Test Scope:** `_escape_common_json_sequences()` centralized escape repair and vendored file sync

---

## Preconditions

```bash
# Verify files exist
ls quantaalpha/llm/client.py
ls third_party/quantaalpha/quantaalpha/llm/client.py
```

---

## Test Cases

### UAT-1: Syntax — Main File

**Purpose:** Verify no syntax errors in main `client.py`.

**Steps:**
```bash
python -m py_compile quantaalpha/llm/client.py
```

**Expected:** No output, exit code 0.

---

### UAT-2: Syntax — Vendored File

**Purpose:** Verify vendored `client.py` is syntactically valid.

**Steps:**
```bash
python -m py_compile third_party/quantaalpha/quantaalpha/llm/client.py
```

**Expected:** No output, exit code 0.

---

### UAT-3: Byte-Identity — MD5 Match

**Purpose:** Ensure vendored file is a precise copy of main file.

**Steps:**
```bash
md5sum quantaalpha/llm/client.py third_party/quantaalpha/quantaalpha/llm/client.py
```

**Expected:** Two MD5 hashes identical. Both read `6b3bac77364473bde6b0e90e801332fa`.

---

### UAT-4: Byte-Identity — Diff

**Purpose:** Confirm zero differences between main and vendored files.

**Steps:**
```bash
diff -q quantaalpha/llm/client.py third_party/quantaalpha/quantaalpha/llm/client.py
```

**Expected:** No output (files are identical).

---

### UAT-5: Generic Fallback Regex Present

**Purpose:** Verify the generic backslash escape regex was added to `_escape_common_json_sequences()`.

**Steps:**
```bash
grep -n 'Fix all unrecognized backslash' quantaalpha/llm/client.py
sed -n '129p' quantaalpha/llm/client.py
```

**Expected Output (line 129):**
```
    fixed_text = re.sub(r'\\(?!["\\\/bfnrtu])', r'\\\\', fixed_text)
```

---

### UAT-6: Inline LaTeX Loop Removed from `_build_response`

**Purpose:** Confirm `latex_commands` is no longer referenced inside `_build_response`.

**Steps:**
```bash
# Extract _build_response region and check
python3 -c "
with open('quantaalpha/llm/client.py') as f:
    lines = f.readlines()
in_build = False
for i, line in enumerate(lines):
    if 'def _build_response' in line:
        in_build = True
    if in_build and 'latex_commands' in line:
        print(f'FOUND at line {i+1}: {line}', end='')
        exit(1)
    if in_build and line.startswith('def ') and 'def _build_response' not in line:
        break
print('OK: latex_commands NOT in _build_response')
"
```

**Expected:** "OK: latex_commands NOT in _build_response" (exit code 0).

---

### UAT-7: Unified Function Call Present in `_build_response`

**Purpose:** Verify `_escape_common_json_sequences(fixed_resp)` is called in `_build_response`.

**Steps:**
```bash
grep -n '_escape_common_json_sequences(fixed_resp)' quantaalpha/llm/client.py
```

**Expected:** One match at approximately line 1078:
```
1078:                    fixed_resp = _escape_common_json_sequences(fixed_resp)
```

---

### UAT-8: `_escape_control_chars_in_json` Still Called

**Purpose:** Verify the separate control-character handler is not accidentally removed.

**Steps:**
```bash
grep -n '_escape_control_chars_in_json' quantaalpha/llm/client.py | head -5
```

**Expected:** At least one call inside `_build_response` (around lines 1083-1120), confirming the two escape concerns are distinct and both present.

---

### UAT-9: Specific-Escape Replacement String Correct

**Purpose:** Verify the symbol-escape replacement string uses the correct 6-backslash template.

**Steps:**
```bash
sed -n '127p' quantaalpha/llm/client.py
```

**Expected:**
```
    fixed_text = re.sub(r"(?<!\\)\\([_\{\}\[\]])", r"\\\\\\1", fixed_text)
```
(Raw string `r"\\\\\\1"` = 6 backslash chars = 3 pairs in replacement output.)

---

### UAT-10: JSON Parse — Stray Underscore Escape

**Purpose:** Verify `\_` in JSON parses correctly via generic fallback.

**Precondition:** Requires a Python environment where `quantaalpha.llm.client` is importable. If import fails (pydantic_settings missing), extract function manually.

**Steps:**
```bash
python3 << 'PYEOF'
import re, json

def _escape_common_json_sequences(text: str) -> str:
    fixed_text = text
    latex_commands = ["text","frac","left","right","times","cdot","sqrt","sum","prod","int","alpha","beta","gamma","delta"]
    for cmd in latex_commands:
        fixed_text = re.sub(r"(?<!\\)\\(" + cmd + r")", r"\\\\\1", fixed_text)
    fixed_text = re.sub(r"(?<!\\)\\([_\{\}\[\]])", r"\\\\\\1", fixed_text)
    fixed_text = re.sub(r'\\(?!["\\\/bfnrtu])', r'\\\\', fixed_text)
    return fixed_text

tests = [
    r'{"x": "\_ 10"}',
    r'{"expr": "PE \_ 10"}',
    '{"name": "John\_Doe"}',
    '{"valid": "\\n is newline"}',
]

all_pass = True
for t in tests:
    result = _escape_common_json_sequences(t)
    try:
        json.loads(result)
        print(f"✅ {t[:40]!r} → parses OK")
    except json.JSONDecodeError as e:
        print(f"❌ {t[:40]!r} → {e}")
        all_pass = False

if all_pass:
    print("\nAll JSON parse tests PASSED")
PYEOF
```

**Expected:**
```
✅ '{"x": "\_ 10"}' → parses OK
✅ '{"expr": "PE \_ 10"}' → parses OK
✅ '{"name": "John\_Doe"}' → parses OK
✅ '{"valid": "\\n is newline"}' → parses OK

All JSON parse tests PASSED
```

---

### UAT-11: `latex_commands` Only Inside `_escape_common_json_sequences`

**Purpose:** Confirm no `latex_commands` references remain outside the escape function.

**Steps:**
```bash
grep -n "latex_commands" quantaalpha/llm/client.py
```

**Expected:** Only two lines, both inside `_escape_common_json_sequences`:
```
109:    latex_commands = [
125:    for cmd in latex_commands:
```

---

### UAT-12: Vendored File Has Same Key Markers

**Purpose:** Confirm vendored copy was updated with T01 changes.

**Steps:**
```bash
grep -n "_escape_common_json_sequences(fixed_resp)" third_party/quantaalpha/quantaalpha/llm/client.py
grep -n 'Fix all unrecognized backslash' third_party/quantaalpha/quantaalpha/llm/client.py
```

**Expected:** One match each, at the same line numbers as the main file.

---

## Edge Cases

### EC-1: Already Escaped Backslash

**Input:** `'{"x": "\\\\_ 10"}'` (already has `\\`)

**Expected:** Does not over-escape. The specific regex `(?<!\\)\\` won't match `\\\_` because the backslash is preceded by a backslash. Generic fallback `\\(?!...)` also won't match because the second backslash is preceded by a backslash. Result: stays as-is, parses as `{"x": "\\ 10"}`.

### EC-2: Valid JSON Escape Sequence

**Input:** `'{"x": "\\n is newline"}'`

**Expected:** `\n` is a valid JSON escape. Generic fallback negative lookahead `(?![..."\\/bfnrtu])` excludes `n`, so `\n` is not modified. Result: passes through unchanged.

### EC-3: Mixed Valid and Invalid Escapes

**Input:** `'{"formula": "\\alpha + \\_ + \\n"}'`

**Expected:** `\alpha` → handled by specific LaTeX loop → `\\alpha`. `\_` → handled by specific symbol regex + generic → `\\\_` → JSON parses as `\\ ` (escaped backslash + space). `\n` → not modified (valid JSON escape). All parse OK.
