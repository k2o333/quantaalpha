---
sliceId: S02
uatType: artifact-driven
verdict: PASS
date: 2026-03-24T18:32:00+08:00
---

# UAT Result — S02

## Checks

| Check | Mode | Result | Notes |
|-------|------|--------|-------|
| UC01: Dict payload with `code` key | artifact | PASS | `fn({'code': 'STD(close/open)', 'note': 'correlation'})` → `STD(close/open)` |
| UC02: Dict payload with `expression` key | artifact | PASS | `fn({'expression': 'STD(close/open)'})` → `STD(close/open)` |
| UC03: Fenced code block (triple backticks) | artifact | PASS | `` fn('```\nSTD(close/open)\n```') `` → `STD(close/open)` |
| UC04: Fenced code block with language hint | artifact | PASS | `` fn('```python\nSTD(close/open)\n```') `` → `STD(close/open)` |
| UC05: `//` comment stripping | artifact | PASS | `fn('STD(close/open) // correlation')` → `STD(close/open)` |
| UC06: `#` comment stripping | artifact | PASS | `fn('STD(close/open) # lagged')` → `STD(close/open)` |
| UC07: Variable assignment RHS extraction | artifact | PASS | `fn('factor = STD(close/open)')` → `STD(close/open)` |
| UC08: Variable assignment (chained) | artifact | PASS | `fn('result = RANK(STD(close/open))')` → `RANK(STD(close/open))` |
| UC09: Multi-line (first DSL line) | artifact | PASS | `fn('dispersion = STD(close/open)\nMEAN(volume)')` → `STD(close/open)` |
| UC10: Pure comment then valid | artifact | PASS | `fn('// Wrong expression\nSTD(close)')` → `STD(close)` |
| UC11: Non-DSL prefix (Option A/B) | artifact | PASS | `fn('Option A: STD(close/open)\nOption B: ZSCORE(close)')` → `STD(close/open)` |
| UC12: Whitespace stripping | artifact | PASS | `fn('  STD(close)  \n')` → `STD(close)` |
| UC13: None input | artifact | PASS | `fn(None)` → `'None'` |
| UC14: Int input | artifact | PASS | `fn(42)` → `'42'` |
| UC15: Plain text (no DSL) | artifact | PASS | `fn('plain text no DSL')` → `'plain text no DSL'` |
| UC16: Vendored copy consistency | artifact | PASS | All 3 key patterns extract correctly from vendored copy |
| Full suite via pytest | artifact | PASS | 16/16 tests passed in 0.03s |
| Syntax verification (main) | artifact | PASS | `python -m py_compile` → MAIN OK |
| Syntax verification (vendored) | artifact | PASS | `python -m py_compile` → VENDORED OK |
| File sync (byte-identical) | artifact | PASS | `diff -q` → SYNC OK, no output (identical) |

## Overall Verdict

**PASS** — All 16 individual test cases, pytest suite (16/16), syntax compilation, and byte-identical vendored sync verification passed.

## Notes

- All test commands executed via `exec()` source extraction from `quantaalpha/factors/proposal.py`, bypassing import chain
- Vendored copy at `third_party/quantaalpha/quantaalpha/factors/proposal.py` is byte-identical to main file
- No failures, no errors, no skipped tests
