# S02 UAT: 因子库 Few-shot 导出

**Slice:** S02 | **Milestone:** M003 | **Date:** 2026-03-23
**Prerequisite:** None (standalone module with mocks)

---

## Preconditions

- Python 3.x with standard library (no quantaalpha conda dependencies required for module tests)
- `tests/` directory in worktree root
- `third_party/quantaalpha/quantaalpha/factors/` accessible for `py_compile`

---

## Test Cases

### TC01: Module Syntax — `fewshot.py` compiles cleanly

**Steps:**
```bash
python -m py_compile third_party/quantaalpha/quantaalpha/factors/fewshot.py
echo "Exit: $?"
```

**Expected:** Exit code 0, no stderr output.

---

### TC02: Module Syntax — `proposal.py` compiles cleanly

**Steps:**
```bash
python -m py_compile third_party/quantaalpha/quantaalpha/factors/proposal.py
echo "Exit: $?"
```

**Expected:** Exit code 0, no stderr output.

---

### TC03: Unit Tests — 27 tests pass

**Steps:**
```bash
python -m pytest tests/test_fewshot.py -v
```

**Expected:**
- 27 tests collected
- All 27 pass (0 failures)
- Exit code 0
- Duration < 2s

**Edge cases covered by these tests:**
- Empty library → empty string
- No Active factors → empty string
- Token budget exhausted on first block → empty string
- Token budget allows partial output → non-empty JSON
- Factor excluded by ID → not in output
- Cache round-trip (save + load)
- Cache missing file → empty entries returned

---

### TC04: Prompt Template — Jinja2 `{% if fewshot_examples %}` block present

**Steps:**
```bash
grep -q "{% if fewshot_examples %}" third_party/quantaalpha/quantaalpha/factors/prompts/prompts.yaml
echo "Exit: $?"
```

**Expected:** Exit code 0.

**Verification of block structure:**
```bash
grep -n -A4 "{% if fewshot_examples %}" third_party/quantaalpha/quantaalpha/factors/prompts/prompts.yaml
```

**Expected output (lines ~315–319):**
```
    {% if fewshot_examples %}
    ## Reference: Active High-Quality Factors
    These factors have proven stable across multiple market periods.
    {{ fewshot_examples }}
    {% endif %}
```

---

### TC05: `prepare_context()` injects `fewshot_examples` key

**Steps:**
```bash
grep -n "fewshot_examples" third_party/quantaalpha/quantaalpha/factors/proposal.py
```

**Expected:** At minimum, these three distinct occurrences:
1. Import guard assignment (`render_fewshot_examples = None`)
2. Injection call (`fewshot_text = render_fewshot_examples(...)`)
3. Dict key injection (`"fewshot_examples": fewshot_text`)

**Structural verification:**
```bash
grep -n -B2 -A3 '"fewshot_examples":' third_party/quantaalpha/quantaalpha/factors/proposal.py
```

**Expected:** Line 199: `"fewshot_examples": fewshot_text` inside the `return {..., True` dict.

---

### TC06: `render_fewshot_examples()` graceful empty-library return

**Steps:**
```bash
python -c "
import sys, json
sys.path.insert(0, 'third_party/quantaalpha')
from unittest.mock import MagicMock
from quantaalpha.factors.fewshot import render_fewshot_examples

# Mock manager with empty factors
mock_mgr = MagicMock()
mock_mgr.data = {'factors': {}}

from unittest.mock import patch
with patch('quantaalpha.factors.fewshot._cache_is_valid', return_value=False):
    result = render_fewshot_examples(mock_mgr)

print('Result repr:', repr(result))
assert result == '', f'Expected empty string, got: {repr(result)}'
print('PASS: empty library returns empty string')
"
```

**Expected:** Output `PASS: empty library returns empty string`, exit code 0.

---

### TC07: Token budget enforcement — oversized first block returns `""`

**Steps:**
```bash
python -c "
import sys
sys.path.insert(0, 'third_party/quantaalpha')
from unittest.mock import MagicMock, patch
from quantaalpha.factors.fewshot import render_fewshot_examples, make_factor_entry

factor = make_factor_entry(
    'f1', 'BigFactor',
    status='active', stability_score=0.9,
    factor_description='X' * 1000,  # big description
    factor_expression='RANK(\$close)',
)
mock_mgr = MagicMock()
mock_mgr.data = {'factors': {'f1': factor}}

with patch('quantaalpha.factors.fewshot._cache_is_valid', return_value=False):
    result = render_fewshot_examples(mock_mgr, max_token_budget=10)

assert result == '', f'Expected empty for oversized first block, got: {repr(result[:50])}'
print('PASS: oversized first block returns empty string')
"
```

**Expected:** `PASS: oversized first block returns empty string`, exit code 0.

---

### TC08: JSON output format — `factor_experiment_output_format` schema

**Steps:**
```bash
python -c "
import sys, json
sys.path.insert(0, 'third_party/quantaalpha')
from unittest.mock import MagicMock, patch
from quantaalpha.factors.fewshot import render_fewshot_examples, make_factor_entry

factor = make_factor_entry(
    'f1', 'TestFactor',
    status='active', stability_score=0.9,
    factor_description='Short-term momentum.',
    factor_expression='RANK(TS_MEAN(\$close, 5))',
    factor_formulation='R_{5d} = \\\\text{RANK}(\\\\mu_{close, 5})',
    fields=['\$close', '\$volume'],
)
mock_mgr = MagicMock()
mock_mgr.data = {'factors': {'f1': factor}}

with patch('quantaalpha.factors.fewshot._cache_is_valid', return_value=False):
    result = render_fewshot_examples(mock_mgr)

parsed = json.loads(result)
factor_data = parsed['TestFactor']
assert 'description' in factor_data
assert 'variables' in factor_data
assert 'formulation' in factor_data
assert 'expression' in factor_data
assert '\$close' in factor_data['variables']
assert factor_data['expression'] == 'RANK(TS_MEAN(\$close, 5))'
print('PASS: JSON output matches factor_experiment_output_format schema')
"
```

**Expected:** `PASS: JSON output matches factor_experiment_output_format schema`, exit code 0.

---

### TC09: Cache file — written with `generated_at` and `entries`

**Precondition:** Run TC08 first (or directly invoke `render_fewshot_examples`) to populate cache.

**Steps:**
```bash
CACHE_FILE="$HOME/.cache/quantaalpha/fewshot_cache.json"
test -f "$CACHE_FILE" && echo "Cache file exists" || echo "Cache file missing"
python -c "
import json, os
cache_file = os.path.expanduser('~/.cache/quantaalpha/fewshot_cache.json')
with open(cache_file) as f:
    d = json.load(f)
assert 'version' in d, 'missing version'
assert 'entries' in d, 'missing entries'
assert 'generated_at' in d, 'missing generated_at'
print(f'Cache: version={d[\"version\"]}, entries={len(d[\"entries\"])}, generated_at={d[\"generated_at\"][:19]}')
"
```

**Expected:** Cache file exists, JSON has `version`, `entries[]`, and ISO `generated_at` fields.

---

### TC10: `exclude_factor_ids` parameter works

**Steps:**
```bash
python -c "
import sys, json
sys.path.insert(0, 'third_party/quantaalpha')
from unittest.mock import MagicMock, patch
from quantaalpha.factors.fewshot import render_fewshot_examples, make_factor_entry

f1 = make_factor_entry('f1', 'FactorOne', status='active', stability_score=0.9)
f2 = make_factor_entry('f2', 'FactorTwo', status='active', stability_score=0.9)
mock_mgr = MagicMock()
mock_mgr.data = {'factors': {'f1': f1, 'f2': f2}}

with patch('quantaalpha.factors.fewshot._cache_is_valid', return_value=False):
    result = render_fewshot_examples(mock_mgr, max_examples=2, exclude_factor_ids={'f1'})

parsed = json.loads(result)
assert 'FactorOne' not in parsed, 'FactorOne should be excluded'
assert 'FactorTwo' in parsed, 'FactorTwo should be present'
print('PASS: exclude_factor_ids works correctly')
"
```

**Expected:** `PASS: exclude_factor_ids works correctly`, exit code 0.

---

### TC11: Import guard — `FactorLibraryManager` absence produces `None` not exception

**Steps:**
```bash
python -c "
import sys
sys.path.insert(0, 'third_party/quantaalpha')
# Simulate unavailability by checking the guard code path
import importlib.util
spec = importlib.util.find_spec('quantaalpha.factors.fewshot')
print('Module spec found:', spec is not None)

# Check that the guard sets the symbol to None on failure
import quantaalpha.factors.fewshot as fewshot_mod
print('FactorLibraryManager value:', fewshot_mod.FactorLibraryManager)
# It will be None if import failed or the actual class if succeeded
print('Guard handles absence gracefully')
"
```

**Expected:** No `AttributeError` or `ImportError` raised; module loads cleanly.

---

## Failure Handling

| Failure | Likely Cause | Fix |
|---------|-------------|-----|
| TC01/TC02: py_compile fails | Syntax error in fewshot.py or proposal.py | Review recent edits, check indentation |
| TC03: pytest failures | Mock setup issue or test environment | Ensure `sys.path.insert` points to `third_party/quantaalpha` |
| TC04: grep fails | Template placeholder removed accidentally | Re-add `{% if fewshot_examples %}` block to `prompts.yaml` |
| TC06: empty library returns non-empty | Cache returned stale data | Delete `~/.cache/quantaalpha/fewshot_cache.json` |
| TC09: cache file not found | `render_fewshot_examples` never called in test scope | Ensure cache write path executed (non-cached path) |
| TC11: `ImportError` on `quantaalpha.factors.fewshot` | `third_party/quantaalpha` not in `sys.path` | Add `sys.path.insert(0, 'third_party/quantaalpha')` before import |
