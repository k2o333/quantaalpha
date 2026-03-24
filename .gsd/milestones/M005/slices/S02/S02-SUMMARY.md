# S02: 强化 normalize_corrected_expression — Slice Summary

**Completed:** 2026-03-24
**Tasks:** T01 ✅, T02 ✅
**Verification:** 16/16 tests pass, both files compile, byte-identical sync confirmed

---

## What This Slice Delivered

Replaced the 5-line stub `normalize_corrected_expression` in `quantaalpha/factors/proposal.py` with an ~80-line multi-pattern handler that robustly handles LLM dirty-string outputs:

| Pattern | Input Example | Output |
|---------|--------------|--------|
| Dict payload (code key) | `{"code": "STD(close/open)"}` | `STD(close/open)` |
| Fenced code block | `` ```\nSTD(close/open)\n``` `` | `STD(close/open)` |
| `//` comment | `STD(close/open) // correlation` | `STD(close/open)` |
| `#` comment | `STD(close/open) # lagged` | `STD(close/open)` |
| Variable assignment | `factor = STD(close/open)` | `STD(close/open)` |
| Multi-line (first DSL) | `dispersion = STD(close/open)\nMEAN(volume)` | `STD(close/open)` |
| Non-DSL prefix | `Option A: STD(close/open)` | `STD(close/open)` |

**Key adaptations made during execution:**

1. **Dict-first handling**: Moved dict branch before `isinstance(str)` guard. Original plan handled dict inside the string block, causing `str(dict)` to convert dicts to repr form before JSON parsing could extract nested keys. Dict check is now the first operation.

2. **Non-DSL-prefix stripping**: Added embedded DSL regex `([A-Z][A-Z_]*\s*\([^)]+\))` as a fallback step after pure-DSL-line check. Required for `Option A: STD(...)` patterns where DSL isn't at line start.

3. **String dict payload handling**: Added JSON parsing for string inputs that look like dicts (`{...}`). Handles cases where the input arrives as a string repr of a dict rather than an actual dict object.

4. **DSL fallback**: When no valid line survives processing, falls back to regex search for first `FUNC(...)` pattern in the original input string.

---

## Files Produced

| File | Action | Description |
|------|--------|-------------|
| `quantaalpha/factors/proposal.py` | Modified | `normalize_corrected_expression` replaced (lines 23–~95) |
| `tests/test_normalize_corrected_expression.py` | Created | 16 test cases via `exec()` source extraction |
| `third_party/quantaalpha/quantaalpha/factors/proposal.py` | Created | Byte-identical vendored copy |
| `third_party/quantaalpha/quantaalpha/factors/__init__.py` | Created | Package marker |

---

## Verification Results

| Check | Command | Result |
|-------|---------|--------|
| Syntax (main) | `python -m py_compile quantaalpha/factors/proposal.py` | ✅ pass |
| Syntax (vendored) | `python -m py_compile third_party/.../proposal.py` | ✅ pass |
| File sync | `diff -q quantaalpha/factors/proposal.py third_party/.../proposal.py` | ✅ identical |
| Tests | `python -m pytest tests/test_normalize_corrected_expression.py -v` | ✅ 16/16 pass |

---

## Patterns Established

1. **exec()-based source extraction**: Tests load the function via AST parsing + `exec()` in isolation, avoiding jinja2 import chain failures. Pattern used in tests and diagnostic commands.

2. **Dict-first ordering**: Dict handling must come before `isinstance(str)` guard to preserve key extraction semantics.

3. **Byte-identical vendored sync**: Vendored copy is always a byte-for-byte mirror. `cp` to sync, `diff -q` to verify.

---

## What S03 Should Know

- The `normalize_corrected_expression` function is now robust and should handle any dirty-string output from LLM quality gates
- The function returns a single-line DSL expression or falls back to the original input if no DSL pattern is found
- R016 (expression-parsing) is now validated — S03's tightened prompts will further reduce dirty-string frequency, but the normalization layer is the safety net
- Downstream consumers: `AlphaAgentHypothesis2FactorExpression._convert_with_history_limit` in `proposal.py` calls this function before passing to the consistency checker

---

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Dict-first handling (dict before `isinstance(str)`) | `str(dict)` converts to repr form, losing key extraction opportunity |
| Non-DSL-prefix stripping via embedded regex | `Option A: STD(...)` needs regex to extract embedded DSL |
| JSON parsing for string dict payloads | Input may arrive as string repr of dict, not actual dict object |
| DSL fallback to original input | Prefer returning something over empty string |
| Byte-identical vendored sync | Consistent with S01's `log/__init__.py` pattern; single source of truth |
