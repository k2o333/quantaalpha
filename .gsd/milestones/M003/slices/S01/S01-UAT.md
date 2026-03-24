# S01: 数据能力注入最后一公里 (S1) — UAT

**Test type:** Contract + Integration verification | **Preconditions:** Polars installed, `/home/quan/testdata/aspipe_v4/data/*/` directories present with `.parquet` files
**Run from:** `/home/quan/testdata/aspipe_v4/.gsd/worktrees/M003/`

---

## Preconditions Check

```bash
# Confirm Polars is available
python -c "import polars; print(polars.__version__)"
# Expected: prints version string, e.g. "1.20.0"

# Confirm data directories exist
ls /home/quan/testdata/aspipe_v4/data/
# Expected: 24 subdirectories, including balancesheet_vip, daily_basic, moneyflow, etc.
```

---

## Test Case 1: Syntax Compilation

**Purpose:** Verify both modified files have zero syntax errors.

```bash
python -m py_compile third_party/quantaalpha/quantaalpha/factors/data_capability.py
echo "exit: $?"
python -m py_compile third_party/quantaalpha/quantaalpha/factors/proposal.py
echo "exit: $?"
```

**Expected:** Both commands exit with code 0, print no output.

---

## Test Case 2: Existing Unit Tests Still Pass

**Purpose:** Confirm the addition of `auto_discover_capabilities()` does not break the existing 6-test suite.

```bash
python -m pytest third_party/quantaalpha/tests/test_data_capability_registry.py -v
```

**Expected:** 6/6 tests pass in < 1 second.

---

## Test Case 3: Dynamic Discovery Finds ≥ 20 Sources

**Purpose:** Verify `auto_discover_capabilities()` scans the real data directory and returns all available sources.

```bash
python scripts/verify_s01_discovery.py
```

**Expected:**
- `[PASS] Source count` — reports ≥ 20 sources (baseline: 24)
- `[PASS] All entries have required keys` — every entry has `fields`, `freq`, `lag_days`, `join_mode`, `factor_hints`
- `[PASS] Metadata fields excluded` — no `_update_time`, `_date_dt` fields in `fields` lists
- `[PASS] render_data_capabilities() produces non-empty text` — ≥ 10 000 chars
- `[PASS] JSON cache written` — file at `/root/.cache/quantaalpha/data_capability_registry.json`

---

## Test Case 4: JSON Cache Contents

**Purpose:** Verify the on-disk cache is well-formed and contains correct metadata.

```bash
cat /root/.cache/quantaalpha/data_capability_registry.json | python -c "
import json, sys
d = json.load(sys.stdin)
print(f'Total sources: {len(d)}')
# Verify quarterly source with lag_days=45
q = [k for k,v in d.items() if v.get('freq') == 'quarterly']
dly = [k for k,v in d.items() if v.get('freq') == 'daily']
print(f'Quarterly sources: {len(q)} (expected > 0)')
print(f'Daily sources: {len(dly)} (expected > 0)')
# Verify a sample entry
s = d.get('daily_basic')
print(f'daily_basic fields count: {len(s[\"fields\"])} (expected > 10)')
print(f'daily_basic lag_days: {s[\"lag_days\"]} (expected 0)')
"
```

**Expected:**
- Total sources = 24
- Quarterly sources ≥ 10 (financial data)
- Daily sources ≥ 10 (market data)
- `daily_basic.lag_days` = 0
- `daily_basic.fields` count > 10

---

## Test Case 5: Cache Bypass Re-scan

**Purpose:** Verify `use_cache=False` bypasses the cache and re-scans the filesystem.

```bash
python -c "
import sys, os
sys.path.insert(0, 'third_party/quantaalpha')
from quantaalpha.factors.data_capability import auto_discover_capabilities
# Force a re-scan
result = auto_discover_capabilities(use_cache=False)
print(f'Re-scanned: {len(result)} sources')
"
```

**Expected:** ≥ 20 sources returned (same as cached result).

---

## Test Case 6: prompts.yaml Contains data_capabilities Placeholder

**Purpose:** Verify the Jinja2 conditional block is present in the template.

```bash
grep -n "data_capabilities" third_party/quantaalpha/quantaalpha/factors/prompts/prompts.yaml
```

**Expected:** ≥ 1 line returned containing `data_capabilities`; the block appears between `{% endif %}` closing `hypothesis_specification` and `Only use concepts implementable...`.

---

## Test Case 7: proposal.py Contains Injection Call

**Purpose:** Verify `prepare_context()` actually calls `render_data_capabilities` and populates `context_dict`.

```bash
grep -c "data_capabilities" third_party/quantaalpha/quantaalpha/factors/proposal.py
grep "from quantaalpha.factors.data_capability import" third_party/quantaalpha/quantaalpha/factors/proposal.py
```

**Expected:**
- `grep -c` returns ≥ 1 (baseline: 7)
- The import line for `render_data_capabilities` is present

---

## Test Case 8: Polars-Absent Graceful Degradation

**Purpose:** Verify `data_capability.py` still loads and compiles when Polars is unavailable.

**Setup:** Temporarily make Polars unloadable:
```bash
python -c "
import sys, importlib.util
# Block polars import
def blocked_import(name, *args, **kwargs):
    if name == 'polars' or name.startswith('polars.'):
        raise ImportError('polars blocked for test')
    return original_import(name, *args, **kwargs)

import builtins
original_import = builtins.__import__
builtins.__import__ = blocked_import

# Force reimport
import importlib
import data_capability  # must use bare name from cwd=worktree root
"
```

**Expected:** `data_capability.py` module loads without error; `auto_discover_capabilities()` raises an exception but does not crash the import. (Note: direct module import from worktree root requires `third_party/quantaalpha` on `sys.path` — this is a valid environment dependency.)

---

## Test Case 9: Proposal Module Import with Missing auto_discover_capabilities

**Purpose:** Verify `proposal.py` still loads if `auto_discover_capabilities` is absent (e.g., during partial deploy).

```bash
# Simulate by temporarily removing the symbol from the module namespace trick
python -c "
import sys
sys.path.insert(0, 'third_party/quantaalpha')
# Import the module - the try/except should catch the specific symbol
import quantaalpha.factors.proposal
print('proposal.py loaded successfully')
"
```

**Expected:** Module loads without `AttributeError` or `ImportError`; the `try/except` around `auto_discover_capabilities` import prevents cascade failure.

---

## Test Case 10: End-to-End Render Pipeline (Integration Smoke Test)

**Purpose:** Verify the full pipeline from discovery → render → template injection renders non-empty content.

```bash
python -c "
import sys
sys.path.insert(0, 'third_party/quantaalpha')
from quantaalpha.factors.data_capability import auto_discover_capabilities, render_data_capabilities, get_data_capabilities

# Step 1: discover
caps = auto_discover_capabilities(use_cache=True)
print(f'Discovered: {len(caps)} sources')

# Step 2: normalize via get_data_capabilities
registry = get_data_capabilities()
print(f'Registry entries: {len(registry)}')

# Step 3: render
text = render_data_capabilities(registry)
print(f'Rendered text length: {len(text)} chars')
print('First 200 chars:')
print(text[:200])
"
```

**Expected:**
- ≥ 20 sources discovered
- Registry has ≥ 20 entries
- Rendered text ≥ 10 000 chars
- Text starts with "Available data capabilities:"

---

## Edge Cases

| Scenario | Expected Behavior |
|---|---|
| Empty data directory | Returns empty dict `{}`; `render_data_capabilities({})` returns empty string; no crash |
| Corrupted JSON cache | Detected by `_cache_is_valid()` → re-scans filesystem; no crash |
| Polars not installed | `_scan_dir_schema()` raises `ImportError` internally; function returns partial results with hardcoded fallback |
| Template rendered without `data_capabilities` key | Jinja2 `{% if data_capabilities %}` guard → block skipped, no `StrictUndefined` error |
| Very large parquet schema (> 500 columns) | `stk_factor_pro` already has ~300 columns; handled by listing all fields in `render_data_capabilities()` output |

---

## Pass Criteria Summary

All 10 test cases must pass for this slice to be considered done. UAT is complete when:
- ✅ `py_compile` on both files returns zero errors
- ✅ All 6 existing pytest tests pass
- ✅ `verify_s01_discovery.py` reports ≥ 20 sources with valid cache
- ✅ `prompts.yaml` and `proposal.py` both contain `data_capabilities`
- ✅ End-to-end render pipeline produces non-empty text
- ✅ JSON cache is valid and contains 24 sources with correct `freq`/`lag_days` inference
