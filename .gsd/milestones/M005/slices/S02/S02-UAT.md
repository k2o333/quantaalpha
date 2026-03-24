# S02-UAT: 强化 normalize_corrected_expression

**Precondition:** All commands run from `/home/quan/testdata/aspipe_v4/.gsd/worktrees/M005`

---

## Test Cases

### UC01: Dict Payload with `code` Key

**Precondition:** None
**Steps:**
```bash
python -c "
import ast, os
path = 'quantaalpha/factors/proposal.py'
with open(path) as f:
    content = f.read()
for node in ast.walk(ast.parse(content)):
    if isinstance(node, ast.FunctionDef) and node.name == 'normalize_corrected_expression':
        exec_globals = {}
        exec(ast.get_source_segment(content, node), exec_globals)
        fn = exec_globals['normalize_corrected_expression']
        result = fn({'code': 'STD(close/open)', 'note': 'correlation'})
        assert result == 'STD(close/open)', f'FAIL: got {result!r}'
        print('PASS: dict with code key → STD(close/open)')
        break
"
```
**Expected:** `PASS: dict with code key → STD(close/open)`

---

### UC02: Dict Payload with `expression` Key

**Precondition:** None
**Steps:**
```bash
python -c "
import ast
path = 'quantaalpha/factors/proposal.py'
with open(path) as f:
    content = f.read()
for node in ast.walk(ast.parse(content)):
    if isinstance(node, ast.FunctionDef) and node.name == 'normalize_corrected_expression':
        exec_globals = {}
        exec(ast.get_source_segment(content, node), exec_globals)
        fn = exec_globals['normalize_corrected_expression']
        result = fn({'expression': 'STD(close/open)'})
        assert result == 'STD(close/open)', f'FAIL: got {result!r}'
        print('PASS: dict with expression key → STD(close/open)')
        break
"
```
**Expected:** `PASS: dict with expression key → STD(close/open)`

---

### UC03: Fenced Code Block (Triple Backticks)

**Precondition:** None
**Steps:**
```bash
python -c "
import ast
path = 'quantaalpha/factors/proposal.py'
with open(path) as f:
    content = f.read()
for node in ast.walk(ast.parse(content)):
    if isinstance(node, ast.FunctionDef) and node.name == 'normalize_corrected_expression':
        exec_globals = {}
        exec(ast.get_source_segment(content, node), exec_globals)
        fn = exec_globals['normalize_corrected_expression']
        result = fn('\`\`\`\nSTD(close/open)\n\`\`\`')
        assert result == 'STD(close/open)', f'FAIL: got {result!r}'
        print('PASS: fenced block → STD(close/open)')
        break
"
```
**Expected:** `PASS: fenced block → STD(close/open)`

---

### UC04: Fenced Code Block with Language Hint

**Precondition:** None
**Steps:**
```bash
python -c "
import ast
path = 'quantaalpha/factors/proposal.py'
with open(path) as f:
    content = f.read()
for node in ast.walk(ast.parse(content)):
    if isinstance(node, ast.FunctionDef) and node.name == 'normalize_corrected_expression':
        exec_globals = {}
        exec(ast.get_source_segment(content, node), exec_globals)
        fn = exec_globals['normalize_corrected_expression']
        result = fn('\`\`\`python\nSTD(close/open)\n\`\`\`')
        assert result == 'STD(close/open)', f'FAIL: got {result!r}'
        print('PASS: fenced block with lang hint → STD(close/open)')
        break
"
```
**Expected:** `PASS: fenced block with lang hint → STD(close/open)`

---

### UC05: `//` Comment Stripping

**Precondition:** None
**Steps:**
```bash
python -c "
import ast
path = 'quantaalpha/factors/proposal.py'
with open(path) as f:
    content = f.read()
for node in ast.walk(ast.parse(content)):
    if isinstance(node, ast.FunctionDef) and node.name == 'normalize_corrected_expression':
        exec_globals = {}
        exec(ast.get_source_segment(content, node), exec_globals)
        fn = exec_globals['normalize_corrected_expression']
        result = fn('STD(close/open) // correlation')
        assert result == 'STD(close/open)', f'FAIL: got {result!r}'
        print('PASS: // comment stripped → STD(close/open)')
        break
"
```
**Expected:** `PASS: // comment stripped → STD(close/open)`

---

### UC06: `#` Comment Stripping

**Precondition:** None
**Steps:**
```bash
python -c "
import ast
path = 'quantaalpha/factors/proposal.py'
with open(path) as f:
    content = f.read()
for node in ast.walk(ast.parse(content)):
    if isinstance(node, ast.FunctionDef) and node.name == 'normalize_corrected_expression':
        exec_globals = {}
        exec(ast.get_source_segment(content, node), exec_globals)
        fn = exec_globals['normalize_corrected_expression']
        result = fn('STD(close/open) # lagged')
        assert result == 'STD(close/open)', f'FAIL: got {result!r}'
        print('PASS: # comment stripped → STD(close/open)')
        break
"
```
**Expected:** `PASS: # comment stripped → STD(close/open)`

---

### UC07: Variable Assignment RHS Extraction

**Precondition:** None
**Steps:**
```bash
python -c "
import ast
path = 'quantaalpha/factors/proposal.py'
with open(path) as f:
    content = f.read()
for node in ast.walk(ast.parse(content)):
    if isinstance(node, ast.FunctionDef) and node.name == 'normalize_corrected_expression':
        exec_globals = {}
        exec(ast.get_source_segment(content, node), exec_globals)
        fn = exec_globals['normalize_corrected_expression']
        result = fn('factor = STD(close/open)')
        assert result == 'STD(close/open)', f'FAIL: got {result!r}'
        print('PASS: assignment RHS extracted → STD(close/open)')
        break
"
```
**Expected:** `PASS: assignment RHS extracted → STD(close/open)`

---

### UC08: Variable Assignment (Chained)

**Precondition:** None
**Steps:**
```bash
python -c "
import ast
path = 'quantaalpha/factors/proposal.py'
with open(path) as f:
    content = f.read()
for node in ast.walk(ast.parse(content)):
    if isinstance(node, ast.FunctionDef) and node.name == 'normalize_corrected_expression':
        exec_globals = {}
        exec(ast.get_source_segment(content, node), exec_globals)
        fn = exec_globals['normalize_corrected_expression']
        result = fn('result = RANK(STD(close/open))')
        assert result == 'RANK(STD(close/open))', f'FAIL: got {result!r}'
        print('PASS: chained assignment → RANK(STD(close/open))')
        break
"
```
**Expected:** `PASS: chained assignment → RANK(STD(close/open))`

---

### UC09: Multi-line (First DSL Line)

**Precondition:** None
**Steps:**
```bash
python -c "
import ast
path = 'quantaalpha/factors/proposal.py'
with open(path) as f:
    content = f.read()
for node in ast.walk(ast.parse(content)):
    if isinstance(node, ast.FunctionDef) and node.name == 'normalize_corrected_expression':
        exec_globals = {}
        exec(ast.get_source_segment(content, node), exec_globals)
        fn = exec_globals['normalize_corrected_expression']
        result = fn('dispersion = STD(close/open)\nMEAN(volume)')
        assert result == 'STD(close/open)', f'FAIL: got {result!r}'
        print('PASS: multi-line → first DSL line')
        break
"
```
**Expected:** `PASS: multi-line → first DSL line`

---

### UC10: Pure Comment Then Valid

**Precondition:** None
**Steps:**
```bash
python -c "
import ast
path = 'quantaalpha/factors/proposal.py'
with open(path) as f:
    content = f.read()
for node in ast.walk(ast.parse(content)):
    if isinstance(node, ast.FunctionDef) and node.name == 'normalize_corrected_expression':
        exec_globals = {}
        exec(ast.get_source_segment(content, node), exec_globals)
        fn = exec_globals['normalize_corrected_expression']
        result = fn('// Wrong expression\nSTD(close)')
        assert result == 'STD(close)', f'FAIL: got {result!r}'
        print('PASS: comment then valid → STD(close)')
        break
"
```
**Expected:** `PASS: comment then valid → STD(close)`

---

### UC11: Non-DSL Prefix (Option A/B)

**Precondition:** None
**Steps:**
```bash
python -c "
import ast
path = 'quantaalpha/factors/proposal.py'
with open(path) as f:
    content = f.read()
for node in ast.walk(ast.parse(content)):
    if isinstance(node, ast.FunctionDef) and node.name == 'normalize_corrected_expression':
        exec_globals = {}
        exec(ast.get_source_segment(content, node), exec_globals)
        fn = exec_globals['normalize_corrected_expression']
        result = fn('Option A: STD(close/open)\nOption B: ZSCORE(close)')
        assert result == 'STD(close/open)', f'FAIL: got {result!r}'
        print('PASS: non-DSL prefix stripped → STD(close/open)')
        break
"
```
**Expected:** `PASS: non-DSL prefix stripped → STD(close/open)`

---

### UC12: Whitespace Stripping

**Precondition:** None
**Steps:**
```bash
python -c "
import ast
path = 'quantaalpha/factors/proposal.py'
with open(path) as f:
    content = f.read()
for node in ast.walk(ast.parse(content)):
    if isinstance(node, ast.FunctionDef) and node.name == 'normalize_corrected_expression':
        exec_globals = {}
        exec(ast.get_source_segment(content, node), exec_globals)
        fn = exec_globals['normalize_corrected_expression']
        result = fn('  STD(close)  \n')
        assert result == 'STD(close)', f'FAIL: got {result!r}'
        print('PASS: whitespace stripped → STD(close)')
        break
"
```
**Expected:** `PASS: whitespace stripped → STD(close)`

---

### UC13: None Input

**Precondition:** None
**Steps:**
```bash
python -c "
import ast
path = 'quantaalpha/factors/proposal.py'
with open(path) as f:
    content = f.read()
for node in ast.walk(ast.parse(content)):
    if isinstance(node, ast.FunctionDef) and node.name == 'normalize_corrected_expression':
        exec_globals = {}
        exec(ast.get_source_segment(content, node), exec_globals)
        fn = exec_globals['normalize_corrected_expression']
        result = fn(None)
        assert result == 'None', f'FAIL: got {result!r}'
        print('PASS: None input → str(None)')
        break
"
```
**Expected:** `PASS: None input → str(None)`

---

### UC14: Int Input

**Precondition:** None
**Steps:**
```bash
python -c "
import ast
path = 'quantaalpha/factors/proposal.py'
with open(path) as f:
    content = f.read()
for node in ast.walk(ast.parse(content)):
    if isinstance(node, ast.FunctionDef) and node.name == 'normalize_corrected_expression':
        exec_globals = {}
        exec(ast.get_source_segment(content, node), exec_globals)
        fn = exec_globals['normalize_corrected_expression']
        result = fn(42)
        assert result == '42', f'FAIL: got {result!r}'
        print('PASS: int input → str(42)')
        break
"
```
**Expected:** `PASS: int input → str(42)`

---

### UC15: Plain Text (No DSL)

**Precondition:** None
**Steps:**
```bash
python -c "
import ast
path = 'quantaalpha/factors/proposal.py'
with open(path) as f:
    content = f.read()
for node in ast.walk(ast.parse(content)):
    if isinstance(node, ast.FunctionDef) and node.name == 'normalize_corrected_expression':
        exec_globals = {}
        exec(ast.get_source_segment(content, node), exec_globals)
        fn = exec_globals['normalize_corrected_expression']
        result = fn('plain text no DSL')
        assert result == 'plain text no DSL', f'FAIL: got {result!r}'
        print('PASS: plain text returned as-is')
        break
"
```
**Expected:** `PASS: plain text returned as-is`

---

### UC16: Vendored Copy Consistency

**Precondition:** None
**Steps:**
```bash
python -c "
import ast
path = 'third_party/quantaalpha/quantaalpha/factors/proposal.py'
with open(path) as f:
    content = f.read()
for node in ast.walk(ast.parse(content)):
    if isinstance(node, ast.FunctionDef) and node.name == 'normalize_corrected_expression':
        exec_globals = {}
        exec(ast.get_source_segment(content, node), exec_globals)
        fn = exec_globals['normalize_corrected_expression']
        # Test 3 key patterns
        assert fn('\`\`\`\nSTD(close/open)\n\`\`\`') == 'STD(close/open)'
        assert fn('factor = STD(close/open)') == 'STD(close/open)'
        assert fn({'code': 'STD(close/open)'}) == 'STD(close/open)'
        print('PASS: vendored copy produces correct results')
        break
"
```
**Expected:** `PASS: vendored copy produces correct results`

---

## Full Suite Run

```bash
# All tests at once
python -m pytest tests/test_normalize_corrected_expression.py -v

# Expected: 16 passed
```

---

## Syntax Verification

```bash
# Both files must compile cleanly
python -m py_compile quantaalpha/factors/proposal.py && echo "MAIN OK"
python -m py_compile third_party/quantaalpha/quantaalpha/factors/proposal.py && echo "VENDORED OK"

# Files must be byte-identical
diff -q quantaalpha/factors/proposal.py third_party/quantaalpha/quantaalpha/factors/proposal.py && echo "SYNC OK"
```

**Expected:** `MAIN OK`, `VENDORED OK`, `SYNC OK` (or no output from diff)

---

## Edge Cases Not Covered by Tests

| Edge Case | Expected Behavior | Notes |
|-----------|------------------|-------|
| Empty string `""` | Returns empty string | Falls through all checks |
| Dict without recognized keys | Returns `str(dict)` | `str({"unknown": "value"})` |
| String dict without JSON parse | Returns original string | JSON parse fails, string processing continues |
| Multiple DSL patterns | Returns first one found | Embedded regex extracts first match |
| Assignment with expression containing `=` | Extracts everything after first `=` | e.g., `x = a = b` → `a = b` |
