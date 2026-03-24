---
id: T02
parent: S02
milestone: M005
provides:
  - Vendored `proposal.py` at `third_party/quantaalpha/quantaalpha/factors/proposal.py` (byte-identical to main)
  - `factors/__init__.py` package marker in vendored tree
  - Dual-file synchronization invariant established (both files diff to nothing)
key_files:
  - third_party/quantaalpha/quantaalpha/factors/proposal.py
  - third_party/quantaalpha/quantaalpha/factors/__init__.py
  - quantaalpha/factors/proposal.py
patterns_established:
  - Vendored copy is always a byte-for-byte mirror of the main file (cp to sync, diff to verify)
observability_surfaces:
  - `diff -q quantaalpha/factors/proposal.py third_party/quantaalpha/quantaalpha/factors/proposal.py` — no output means in-sync
  - `python -m py_compile` on both files — no output means valid Python
  - pytest test suite runs against the main file; vendored copy inherits via byte-identity
duration: ~1 min
verification_result: passed
completed_at: 2026-03-24T18:37:00+08:00
blocker_discovered: false
---

# T02: 建立 vendored proposal.py 并同步文件

**在 `third_party/quantaalpha/quantaalpha/factors/` 建立 vendored `proposal.py`，与主文件保持 byte-identical。**

## What Happened

Verified the main `proposal.py` has the hardened `normalize_corrected_expression` (multi-line ~80-line handler confirmed via grep), then created the `factors/` subdirectory in the vendored tree (`third_party/quantaalpha/quantaalpha/factors/`), copied the main file there, verified both files compile cleanly, confirmed byte-identical via `diff -q`, and created the `__init__.py` package marker. Also ran all 16 pytest tests (they pass) and spot-checked the vendored function directly via AST+exec — fenced block, assignment RHS, and dict key extraction all work correctly.

## Verification

All slice verification gates passed: both files have zero syntax errors, `diff -q` shows no differences, and all 16 pytest tests pass.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m py_compile quantaalpha/factors/proposal.py && echo "SYNTAX OK"` | 0 | ✅ pass | <1s |
| 2 | `python -m py_compile third_party/quantaalpha/quantaalpha/factors/proposal.py && echo "SYNTAX OK"` | 0 | ✅ pass | <1s |
| 3 | `diff -q quantaalpha/factors/proposal.py third_party/quantaalpha/quantaalpha/factors/proposal.py && echo "IDENTICAL"` | 0 | ✅ pass (no output = identical) | <1s |
| 4 | `python -m pytest tests/test_normalize_corrected_expression.py -v` | 0 | ✅ pass (16/16) | 0.03s |
| 5 | AST+exec spot-check on vendored copy (fenced block, assignment RHS, dict key) | 0 | ✅ pass (all 3 return `'STD(close/open)'`) | <1s |

## Diagnostics

To verify the vendored `normalize_corrected_expression` directly:
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
        print(fn('\`\`\`\nSTD(close/open)\n\`\`\`'))
        break
"
```

## Deviations

None — all steps followed the plan exactly.

## Known Issues

None.

## Files Created/Modified

- `third_party/quantaalpha/quantaalpha/factors/proposal.py` — new file, byte-identical copy of `quantaalpha/factors/proposal.py`
- `third_party/quantaalpha/quantaalpha/factors/__init__.py` — new file, empty package marker
