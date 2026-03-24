# S03: 添加回归测试和文档 — UAT

**Milestone:** M002
**Written:** 2026-03-23

## UAT Type

- UAT mode: **artifact-driven** (regression tests as primary proof)
- Why this mode is sufficient: The fix from S02 is now protected by 25 unit tests. The UAT verifies these tests pass and the fix is documented.

## Preconditions

- Python 3.8+ environment
- Worktree at `/home/quan/testdata/aspipe_v4/.gsd/worktrees/M002/`
- No special runtime services required (standalone tests)

## Smoke Test

Quick verification that regression tests run and pass:

```bash
cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M002
python test/test_dict_replace_fix_unit.py -v
# Expected: Ran 13 tests ... OK
```

## Test Cases

### 1. Regression Test Suite: test_dict_replace_fix_unit.py

1. Run: `python test/test_dict_replace_fix_unit.py -v`
2. **Expected:** All 13 tests pass within 0.01s

| Test | Verifies |
|------|----------|
| test_fix_exists_in_complexity_checker | Fix present in ComplexityChecker.check() |
| test_fix_exists_in_redundancy_checker | Fix present in RedundancyChecker.check() |
| test_dict_with_code_key | Dict with 'code' key extracts correctly |
| test_dict_with_expression_key | Dict with 'expression' key extracts correctly |
| test_dict_with_no_standard_keys | Fallback to str() works |
| test_empty_dict | Empty dict handled safely |
| test_isinstance_guard_on_dict | isinstance returns True for dict |
| test_isinstance_guard_on_int | isinstance returns False for int |
| test_isinstance_guard_on_none | isinstance returns False for None |
| test_isinstance_guard_on_string | isinstance returns False for string |
| test_original_bug_would_raise_attributeerror | Original bug would crash |
| test_string_replace_still_works | String input still works (baseline) |
| test_syntax_check | Python syntax valid |

### 2. Regression Test Suite: tests/test_dict_replace_bug_fix.py

1. Run: `python tests/test_dict_replace_bug_fix.py -v`
2. **Expected:** All 12 tests pass within 0.01s

| Test | Verifies |
|------|----------|
| test_code_key_takes_priority | 'code' > 'expression' when both present |
| test_empty_dict_falls_back_to_str | Empty dict → str() |
| test_expression_used_when_no_code | 'expression' used as fallback |
| test_str_fallback_when_no_code_or_expression | Unknown keys → str() |
| test_dict_with_code_key_does_not_raise_attribute_error | No crash on dict input |
| test_dict_with_expression_key_does_not_raise_attribute_error | No crash on dict input |
| test_dict_with_only_note_key | Non-standard keys handled |
| test_dict_with_unknown_keys_does_not_raise_attribute_error | Unknown structure handled |
| test_nested_dict_with_code_key | Nested dict extraction works |
| test_string_expression_still_works | String expressions work |
| test_fixed_code_handles_both | Both string and dict work |
| test_original_buggy_code_would_fail_on_dict | Original bug confirmed |

### 3. Fix Presence Verification

1. Run: `grep -n "isinstance.*expression.*dict" third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py`
2. **Expected:** Two matches at lines 265 and 354

```
265:        if isinstance(expression, dict):
354:        if isinstance(expression, dict):
```

### 4. Python Syntax Check

1. Run: `python -m py_compile third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py`
2. **Expected:** No output (exit code 0)

### 5. Documentation Verification

1. Run: `grep "M002 S03" .gsd/KNOWLEDGE.md`
2. **Expected:** Contains "## M002 S03: 回归测试固化" section

## Edge Cases

### Dict with deeply nested structure
1. Pass: `{"level1": {"code": "close/open"}}`
2. **Expected:** Extracts "close/open" from nested code key

### Dict with empty string values
1. Pass: `{"code": "", "expression": "close/open"}`
2. **Expected:** Falls back to "expression" key when "code" is empty

### Non-string types (int, float)
1. Pass: `42` (integer)
2. **Expected:** isinstance check returns False, passes through to original code (will fail at .replace() but that's expected - int is not valid input)

## Failure Signals

- Any test failing with `AttributeError: 'dict' object has no attribute 'replace'`
- grep showing fix missing from expected lines
- Python syntax compilation error

## Not Proven By This UAT

- Live factor mining pipeline execution (requires full quantaalpha environment with pydantic)
- Performance impact of defensive check (negligible - single isinstance call)
- Other potential dict-type issues in different code paths

## Notes for Tester

- Tests are designed to run independently without requiring full quantaalpha import chain
- Exit code 0 = all tests passed
- Duration of ~0.01s indicates tests are fast unit tests, not integration tests
- The pydantic issue in quantaalpha test suite is a pre-existing environment problem, not related to this fix
