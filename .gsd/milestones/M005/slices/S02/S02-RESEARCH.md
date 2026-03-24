# S02: 强化 normalize_corrected_expression — Research

## What Exists

**`normalize_corrected_expression`** defined at `proposal.py:23-27` (worktree copy):

```python
def normalize_corrected_expression(expression) -> str:
    """Normalize quality-gate corrected expressions to a parser-safe string."""
    if isinstance(expression, dict):
        return expression.get("expression") or str(expression)
    return expression
```

**Call site** at `proposal.py:550`:
```python
if results.get("corrected_expression") and results["corrected_expression"] != expr:
    expr = normalize_corrected_expression(results["corrected_expression"])
```

**Data source**: `consistency_checker.py:114` — `result_dict.get("corrected_expression")` comes directly from LLM JSON response, raw and unvalidated.

**Vendored copy**: `third_party/quantaalpha/quantaalpha/factors/proposal.py` also defines this function (needs to be kept in sync).

---

## What LLM Returns (Dirty Patterns)

| Pattern | Example | Desired Output |
|---------|---------|----------------|
| Fenced code block | ```\nSTD(close / open)\n``` | `STD(close / open)` |
| `//` comment | `STD(close / open) // correlation` | `STD(close / open)` |
| `#` comment | `STD(close / open) # lagged` | `STD(close / open)` |
| Assignment pseudo | `dispersion = STD(...)` | `STD(...)` |
| Multi-line | `STD(close / open)\nMEAN(volume)` | `STD(close / open)` |
| Dict payload | `{"code": "STD(...)", "note": "..."}` | `STD(...)` |
| Multi-candidate | `Option A: STD(...)\nOption B: ZSCORE(...)` | First valid DSL |
| Whitespace/padding | `  STD(...)  \n` | `STD(...)` |

---

## Implementation Strategy

### Core Principle
**Extract, don't delete.** The RHS of a variable assignment (`factor = STD(...)`) contains the valid expression — skipping the line would lose it entirely. The function must extract the RHS when the LHS is a simple identifier.

### Pipeline

```
raw input
  ├─ str? yes → continue
  └─ dict? yes → extract "code"/"expression" key → str
  │
  ├─ Strip fenced code blocks  ```...```  (any variant)
  ├─ Strip leading/trailing whitespace
  │
  ├─ Split on newlines
  │   ├─ Per line: strip `//` and `#` comments
  │   ├─ Skip pure-`//` comment lines
  │   ├─ Assignment lines: extract RHS if LHS is identifier-only
  │   └─ Keep any line that looks like a DSL expression
  │
  ├─ If 0 lines remain → fallback to extracting first DSL pattern
  ├─ If multiple lines remain → pick first DSL-like line
  └─ Return single-line str
```

### DSL Expression Pattern
A valid DSL expression matches: uppercase function name followed by parentheses containing `$variable` references or numbers. Regex: `[A-Z][A-Z_]+\([^)]+\)` (e.g., `STD(...)`, `RANK(...)`, `TS_PCTCHANGE(...)`).

### Edge Cases

1. **Dict with code key**: `{"code": "STD(...)", "note": "..."}` → `STD(...)`
2. **Dict with expression key**: `{"expression": "STD(...)"}` → `STD(...)`
3. **Fenced block with language hint**: ````python\nSTD(...)\n```` → `STD(...)`
4. **Assignment with complex RHS**: `factor = STD(close / open)` → `STD(close / open)`
5. **Assignment with chained calls**: `result = RANK(STD(...))` → `RANK(STD(...))`
6. **Pure comment line**: `// This is wrong` → skip entirely
7. **Blank lines**: skip
8. **Multi-candidate output**: `Option A: STD(...)\nOption B: ZSCORE(...)` → `STD(...)`
9. **Fenced but no valid expression inside**: extract first `FUNC(...)` pattern from raw text
10. **Non-string input**: `None`, `int`, `float` → `str()`

---

## File Changes Required

| File | Change |
|------|--------|
| `quantaalpha/factors/proposal.py:23-27` | Replace with hardened multi-line function |
| `third_party/quantaalpha/quantaalpha/factors/proposal.py:23-27` | Same replacement (keep in sync) |

Both files must remain byte-identical for the function body. S01 already established this requirement.

---

## Validation Plan

Test cases to cover:

1. `normalize_corrected_expression({"code": "STD(close/open)", "note": "..."})` → `"STD(close/open)"`
2. `normalize_corrected_expression("```\nSTD(close/open)\n```")` → `"STD(close/open)"`
3. `normalize_corrected_expression("STD(close/open) // correlation")` → `"STD(close/open)"`
4. `normalize_corrected_expression("STD(close/open) # lagged")` → `"STD(close/open)"`
5. `normalize_corrected_expression("factor = STD(close/open)")` → `"STD(close/open)"`
6. `normalize_corrected_expression("dispersion = STD(...)\nMEAN(volume)")` → `"STD(...)"` (first valid)
7. `normalize_corrected_expression("// Wrong expression\nSTD(close)")` → `"STD(close)"`
8. `normalize_corrected_expression("Option A: STD(...)\nOption B: ZSCORE(...)")` → `"STD(...)"`
9. `normalize_corrected_expression("  STD(close)  ") → `"STD(close)"` (stripped)
10. `normalize_corrected_expression(None)` → `"None"`
11. `normalize_corrected_expression(42)` → `"42"`
12. `normalize_corrected_expression("plain text no DSL")` → `"plain text no DSL"` (pass-through)

**Syntax check after edit:**
```bash
python -m py_compile quantaalpha/factors/proposal.py
python -m py_compile third_party/quantaalpha/quantaalpha/factors/proposal.py
diff -q quantaalpha/factors/proposal.py third_party/quantaalpha/quantaalpha/factors/proposal.py
```

**Note**: Can't run `from quantaalpha.factors.proposal import normalize_corrected_expression` directly because of transitive jinja2 dependency. Unit test must import only the function directly by reading the source.

---

## Risk Assessment

- **Risk**: Medium — modifies a production function that runs on every consistency correction
- **Mitigation**: Write exhaustive unit tests; both copies of proposal.py must stay in sync
- **No upstream changes needed**: This is a pure local normalization function, no API changes

---

## Recommendation

Implement the hardened function immediately in both `proposal.py` copies. The function is self-contained (only needs `re` from stdlib) and has a clear, testable contract. Keep the S03 (prompt constraint) as a complementary upstream fix — even with perfect prompts, the normalization function is the last line of defense.
