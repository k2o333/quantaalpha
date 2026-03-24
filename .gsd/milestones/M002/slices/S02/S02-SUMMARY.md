---
id: S02
milestone: M002
provides:
  - Defensive isinstance() guard for dict inputs in consistency checkers
  - Unit tests verifying the fix for 'dict' object has no attribute 'replace'
patterns_established:
  - Defensive type checking at function entry points before string operations
  - Graceful fallback chain: extract 'code' key → extract 'expression' key → str(dict)
key_files:
  - third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py
  - test/test_dict_replace_fix_unit.py
duration: ~10 minutes
verification_result: passed
completed_at: 2026-03-23
---

# S02: 实现类型检查与转换逻辑

**Milestone:** M002 — QuantaAlpha 数据类型 Bug 修复

## What Happened

Added defensive `isinstance(expression, dict)` checks in `consistency_checker.py` to prevent the `'dict' object has no attribute 'replace'` error. The bug occurs when `LLM` returns a factor expression as a dict (with `code` or `expression` keys) instead of a plain string, and the quality gate checkers call `.replace()` on it directly.

**Fix locations (2 sites):**
- `ComplexityChecker.check()` — line 264-266
- `RedundancyChecker.check()` — line 353-355

**Fix pattern:**
```python
# Defensive: Handle dict input (e.g., from LLM corrected_expression)
if isinstance(expression, dict):
    expression = expression.get("code") or expression.get("expression") or str(expression)
```

This:
1. Detects dict inputs via `isinstance(expression, dict)`
2. Extracts the expression from `code` or `expression` keys (matching LLM response shape)
3. Falls back to `str(expression)` for unknown dict structures
4. Preserves all original string behavior — no breaking changes

## Verification

| # | Check | Result |
|---|-------|--------|
| 1 | `python -m py_compile consistency_checker.py` | ✅ Syntax OK |
| 2 | `python test/test_dict_replace_fix_unit.py` | ✅ All 9 tests pass |
| 3 | `grep -c "isinstance.*expression.*dict" consistency_checker.py` | ✅ 2 occurrences |

## What Remains (S03)

S02 delivers the defensive code and unit tests. S03 will add:
- Regression tests committed to the test suite
- Documentation of this bug/fix in KNOWLEDGE.md

## Relationship to Prior Work

- **M001**: Fixed 4 blockers that kept the factor mining workflow from starting (logger, empty response, infinite retry, JSON control chars)
- **S02**: Fixes a data-type mismatch that surfaces mid-workflow during quality gate checks

Both are independent bug fixes — S03 closes the milestone by adding tests and docs.
