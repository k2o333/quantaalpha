# S01: 定位数据类型 Bug 触发位置 — UAT

**Milestone:** M002
**Written:** 2026-03-23

## UAT Type

- UAT mode: **artifact-driven** — Static analysis and test execution (no live runtime required)
- Why this mode is sufficient: S01 is a diagnostic/bug-location task. Bug reproduction via test script provides sufficient proof that the bug location is correct.

## Preconditions

1. Python 3.8+ with access to `third_party/quantaalpha`
2. Terminal logs available at `/home/quan/testdata/aspipe_v4/third_party/facotors/terminal/`
3. `test/test_dict_replace_bug.py` exists and is executable

## Smoke Test

```bash
python -m py_compile third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py
# Expected: No output (syntax valid)

python test/test_dict_replace_bug.py
# Expected: "Results: 8 passed, 0 failed"
```

## Test Cases

### TC01: Syntax Check

**Purpose**: Verify consistency_checker.py has valid Python syntax

1. Run `python -m py_compile third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py`
2. **Expected:** Exit code 0, no error output

### TC02: Locate replace() Call

**Purpose**: Confirm the exact line where .replace() is called

1. Run `rg -n "expression\.replace" third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py`
2. **Expected:** Output includes `265:        expr_clean = expression.replace(" ", "")`

### TC03: Bug Reproduction Test

**Purpose**: Verify the bug can be reproduced with a test script

1. Run `python test/test_dict_replace_bug.py`
2. **Expected:** All 5 test cases pass:
   - Test 1: String expression with replace() ✅
   - Test 2: Dict expression triggers AttributeError ✅
   - Test 3: normalize_corrected_expression() fix validation ✅
   - Test 4: Data flow simulation ✅
   - Test 5: Edge cases (various dict structures) ✅

### TC04: Terminal Log Verification

**Purpose**: Confirm the bug exists in production logs

1. Run `grep -r "dict.*has no attribute" /home/quan/testdata/aspipe_v4/third_party/facotors/terminal/`
2. **Expected:** Multiple log entries showing the error:
   ```
   2026-03-21 21:47:50.617 | WARNING | ... - Consistency check error: 'dict' object has no attribute 'replace'
   ```

### TC05: Data Flow Confirmation

**Purpose**: Verify the complete call chain exists in code

1. Search for `complexity_checker.check(factor_expression)` in consistency_checker.py
2. Search for `factor_expression = corrected_expr` in consistency_checker.py
3. **Expected:** Both calls exist at the expected line numbers (489 and 487 respectively)

## Edge Cases

### EC01: Multiple dict Structures

The test validates 4 different dict structure variants:
- `{"code": "close / open"}`
- `{"expression": "close / open", "reason": "invalid"}`
- `{"expr": "close / open", "alternatives": ["a/b", "c/d"]}`
- `{"code": "close", "normalized": "close / 1"}`

**All should trigger the same AttributeError.**

### EC02: String Expression (Non-Bug)

Verify that normal string expressions work correctly:
- Input: `"close / open"`
- After `.replace(" ", "")`: `"close/open"`

## Failure Signals

- Syntax check fails → Code has syntax errors
- Test script exits with non-zero → Bug not reproduced
- No grep results in terminal logs → Error may have been fixed already or logs missing

## Not Proven By This UAT

- **Fix implementation** — S01 only locates the bug, does not implement a fix
- **Live runtime** — No actual factor mining workflow executed
- **Integration** — The proposed fix (calling `normalize_corrected_expression()`) not yet tested

## Notes for Tester

1. **This UAT is static-only** — No actual factor mining pipeline runs
2. **Terminal logs are historical** — They prove the bug existed, not that it's fixed
3. **Test script import warning** — The `normalize_corrected_expression` import may fail due to missing pydantic_core dependency; the test handles this gracefully with an inline fallback
4. **Fix location** — S02 should implement fix at `consistency_checker.py:487`:
   ```python
   # Add after line 487
   from quantaalpha.factors.proposal import normalize_corrected_expression
   factor_expression = normalize_corrected_expression(corrected_expr)
   ```
