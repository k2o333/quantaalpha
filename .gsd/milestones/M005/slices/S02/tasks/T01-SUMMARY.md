---
id: T01
parent: S02
milestone: M005
provides:
  - Hardened normalize_corrected_expression function with 80-line multi-pattern handler
  - 16 test cases covering all dirty-string normalization scenarios
key_files:
  - quantaalpha/factors/proposal.py
  - tests/test_normalize_corrected_expression.py
patterns_established:
  - exec()-based source extraction for isolated function testing (avoids jinja2 import chain)
  - Dict-first handling before non-string string conversion (preserves dict key extraction)
observability_surfaces:
  - pytest test suite: tests/test_normalize_corrected_expression.py
  - python -m py_compile syntax verification
duration: ~5 min
verification_result: passed
completed_at: 2026-03-24T10:32:00+08:00
blocker_discovered: false
---

# T01: 替换 normalize_corrected_expression 并创建测试文件

**用硬化版本替换 `normalize_corrected_expression` 函数，创建 16 个测试用例，全部通过。**

## What Happened

Replaced the 5-line stub `normalize_corrected_expression` in `quantaalpha/factors/proposal.py` with a ~80-line multi-pattern handler that strips fenced code blocks (triple-backtick variants), `//` and `#` inline comments, extracts RHS from variable assignments (e.g., `factor = STD(close/open)` → `STD(close/open)`), strips non-DSL prefixes from option-style lines (e.g., `Option A: STD(...)` → `STD(...)`), handles multi-line input by picking the first DSL-expressive line, and falls back to regex DSL pattern extraction when no valid line remains.

**Key adaptation during execution:** The original plan placed the dict check inside the string-only branch. This caused `test_dict_with_code_key` and `test_dict_with_expression_key` to fail because `str(dict)` converted dict inputs to their repr string form before JSON parsing could extract the nested key. Fixed by moving dict handling to the very top of the function, before the `isinstance(str)` guard.

**Second adaptation:** `test_multi_candidate_option_a` (`"Option A: STD(close/open)"`) needed a non-DSL-prefix stripping step after the pure DSL line check, since the line doesn't start with the DSL function name directly. Added a regex search `([A-Z][A-Z_]*\s*\([^)]+\))` on each valid line to extract the first embedded DSL expression.

**Third_party file note:** `third_party/quantaalpha/quantaalpha/factors/proposal.py` does not exist yet — that is T02's responsibility, not T01's.

## Verification

pytest confirmed all 16 tests pass. py_compile confirmed zero syntax errors in `quantaalpha/factors/proposal.py`. The third_party file sync is T02's deliverable.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m py_compile quantaalpha/factors/proposal.py && echo "SYNTAX OK"` | 0 | ✅ pass | <1s |
| 2 | `python -m pytest tests/test_normalize_corrected_expression.py -v` | 0 | ✅ pass (16/16) | 0.03s |

## Diagnostics

To inspect the normalized output for any dirty-string pattern:
```bash
python -c "
import ast, os
PROPOSAL_PATH = 'quantaalpha/factors/proposal.py'
with open(PROPOSAL_PATH) as f:
    content = f.read()
tree = ast.parse(content)
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == 'normalize_corrected_expression':
        src = ast.get_source_segment(content, node)
        exec_globals = {}
        exec(src, exec_globals)
        fn = exec_globals['normalize_corrected_expression']
        print(fn('factor = STD(close/open)'))
        break
"
```

## Deviations

1. **Dict-first handling** — moved dict branch before `isinstance(str)` guard (planned implementation had dict handled inside the string block). Required to fix `test_dict_with_code_key` and `test_dict_with_expression_key` failures.
2. **Non-DSL-prefix stripping** — added embedded DSL regex search `([A-Z][A-Z_]*\s*\([^)]+\))` on valid lines as a fallback after the pure-DSL-line check. Required to fix `test_multi_candidate_option_a` failure.

## Known Issues

None.

## Files Created/Modified

- `quantaalpha/factors/proposal.py` — `normalize_corrected_expression` function replaced (lines 23–~95), expanded from 5 to ~80 lines
- `tests/test_normalize_corrected_expression.py` — new test file with 16 test cases loaded via `exec()` of AST-extracted source
