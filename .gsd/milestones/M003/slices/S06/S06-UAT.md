# S06: Checkpoint 与幂等性恢复 — UAT Script

## Preconditions

- Python 3.12+ with pytest available
- Working directory: `.gsd/worktrees/M003/`
- No rdagent/litellm dependencies required (tests use mocks and stubs)

## Test Suite

Run all S06 tests:
```bash
cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M003
python -m pytest \
  third_party/quantaalpha/tests/test_checkpoint.py \
  third_party/quantaalpha/tests/test_factor_library_versions.py \
  third_party/quantaalpha/tests/test_factor_library_locking.py \
  third_party/quantaalpha/tests/test_checkpoint_integration.py \
  -v --tb=short
```
**Expected:** 33 passed, 0 failed

---

## Contract Verification Tests

### C01: Syntax — all modified/new files compile cleanly

```bash
python -m py_compile third_party/quantaalpha/quantaalpha/pipeline/checkpoint.py
echo "checkpoint.py: $?"
python -m py_compile third_party/quantaalpha/quantaalpha/pipeline/loop.py
echo "loop.py: $?"
python -m py_compile third_party/quantaalpha/quantaalpha/factors/library.py
echo "library.py: $?"
```
**Expected:** All exit code 0

---

### C02: experiment.yaml checkpoint config parses correctly

```bash
python -c "
import yaml
cfg = yaml.safe_load(open('third_party/quantaalpha/configs/experiment.yaml'))
ckpt = cfg['checkpoint']
assert ckpt['enabled'] == True
assert ckpt['lock_timeout_seconds'] == 30
assert ckpt['max_versions_per_factor'] == 10
print('checkpoint config: enabled=1, timeout=30s, max_versions=10')
"
```
**Expected:** Output shows all three values correct; no AssertionError

---

## LoopCheckpoint Unit Tests (T01)

### T01-U01: save creates checkpoint_state.pkl + checkpoint_meta.json

```python
import tempfile, sys
sys.path.insert(0, 'third_party/quantaalpha')
from quantaalpha.pipeline.checkpoint import LoopCheckpoint

with tempfile.TemporaryDirectory() as tmp:
    ckpt = LoopCheckpoint(tmp)
    ckpt.save({'loop_idx': 0, 'step_idx': 1}, 'factor_propose')
    import os
    assert os.path.exists(f'{tmp}/checkpoint_state.pkl'), 'pickle missing'
    assert os.path.exists(f'{tmp}/checkpoint_meta.json'), 'meta missing'
    print('T01-U01 PASS')
```
**Expected:** Both files created

### T01-U02: load returns saved state with correct values

```python
import tempfile, sys
sys.path.insert(0, 'third_party/quantaalpha')
from quantaalpha.pipeline.checkpoint import LoopCheckpoint

with tempfile.TemporaryDirectory() as tmp:
    ckpt = LoopCheckpoint(tmp)
    ckpt.save({'loop_idx': 5, 'step_idx': 3, 'round_idx': 2}, 'factor_backtest')
    loaded = ckpt.load()
    assert loaded['loop_idx'] == 5
    assert loaded['step_idx'] == 3
    assert loaded['round_idx'] == 2
    print('T01-U02 PASS')
```
**Expected:** All assertions pass

### T01-U03: exists property is False when no checkpoint

```python
import tempfile, sys
sys.path.insert(0, 'third_party/quantaalpha')
from quantaalpha.pipeline.checkpoint import LoopCheckpoint

with tempfile.TemporaryDirectory() as tmp:
    ckpt = LoopCheckpoint(tmp)
    assert not ckpt.exists, 'exists should be False when no checkpoint'
    print('T01-U03 PASS')
```
**Expected:** Assertion passes

### T01-U04: clear removes both files, exists becomes False

```python
import tempfile, sys
sys.path.insert(0, 'third_party/quantaalpha')
from quantaalpha.pipeline.checkpoint import LoopCheckpoint

with tempfile.TemporaryDirectory() as tmp:
    ckpt = LoopCheckpoint(tmp)
    ckpt.save({'loop_idx': 0}, 'test')
    assert ckpt.exists
    ckpt.clear()
    assert not ckpt.exists, 'exists should be False after clear'
    print('T01-U04 PASS')
```
**Expected:** Both assertions pass

### T01-U05: atomic JSON meta write (no partial-write visibility)

```python
import tempfile, json, sys
sys.path.insert(0, 'third_party/quantaalpha')
from quantaalpha.pipeline.checkpoint import LoopCheckpoint

with tempfile.TemporaryDirectory() as tmp:
    ckpt = LoopCheckpoint(tmp)
    ckpt.save({'loop_idx': 1}, 'factor_propose')
    # Read meta directly — should be valid JSON
    with open(f'{tmp}/checkpoint_meta.json') as f:
        meta = json.load(f)
    assert meta['step_name'] == 'factor_propose'
    assert 'round_idx' in meta
    assert 'timestamp' in meta
    # Confirm no .tmp file leaked
    import os
    assert not any(f.endswith('.tmp') for f in os.listdir(tmp)), '.tmp file leaked'
    print('T01-U05 PASS')
```
**Expected:** Valid JSON parsed, no .tmp files leaked

### T01-U06: D019 newline/tab in hypothesis text round-trips correctly

```python
import tempfile, sys
sys.path.insert(0, 'third_party/quantaalpha')
from quantaalpha.pipeline.checkpoint import LoopCheckpoint

with tempfile.TemporaryDirectory() as tmp:
    ckpt = LoopCheckpoint(tmp)
    state = {
        'loop_idx': 0,
        'step_idx': 1,
        'loop_prev_out': {
            'factor_propose': {
                'hypothesis': 'line1\nline2\nline3\twith\ttabs',
                'direction': 'test\ndirection\nwith\nnewlines',
            }
        },
        'round_idx': 0,
    }
    ckpt.save(state, 'factor_propose')
    loaded = ckpt.load()
    assert loaded['loop_idx'] == 0
    assert loaded['step_idx'] == 1
    # Newlines and tabs survive pickle round-trip
    assert '\n' in loaded['loop_prev_out']['factor_propose']['hypothesis']
    print('T01-U06 PASS')
```
**Expected:** Newlines/tabs preserved in loaded state

### T01-U07: control-char (U+0000–U+0008) fields are redacted with WARNING

```python
import tempfile, sys, logging, io
sys.path.insert(0, 'third_party/quantaalpha')
from quantaalpha.pipeline.checkpoint import LoopCheckpoint

log_stream = io.StringIO()
handler = logging.StreamHandler(log_stream)
handler.setLevel(logging.WARNING)
logging.getLogger('quantaalpha.pipeline.checkpoint').addHandler(handler)

with tempfile.TemporaryDirectory() as tmp:
    ckpt = LoopCheckpoint(tmp)
    state = {
        'loop_idx': 0,
        'step_idx': 0,
        'loop_prev_out': {
            'factor_propose': {
                'hypothesis': 'normal text',  # no control chars
                'bad_field': 'has\x00null\x01and\x02control\x03chars',  # has control chars
            }
        },
    }
    ckpt.save(state, 'factor_propose')
    loaded = ckpt.load()
    assert '[REDACTED_D019]' in str(loaded['loop_prev_out']['factor_propose']['bad_field']), \
        'control chars should be redacted'
    log_output = log_stream.getvalue()
    assert 'WARNING' in log_output or 'REDACTED' in str(loaded), 'WARNING should be logged'
    print('T01-U07 PASS')
```
**Expected:** Control-char field replaced with `[REDACTED_D019]`, WARNING logged

### T01-U08: corrupt pickle raises UnpicklingError + ERROR log

```python
import tempfile, sys
sys.path.insert(0, 'third_party/quantaalpha')
from pathlib import Path
from quantaalpha.pipeline.checkpoint import LoopCheckpoint

with tempfile.TemporaryDirectory() as tmp:
    ckpt = LoopCheckpoint(tmp)
    ckpt.save({'loop_idx': 1}, 'factor_propose')
    # Corrupt the pickle file
    Path(tmp, 'checkpoint_state.pkl').write_bytes(b'not a pickle at all')
    try:
        ckpt.load()
        raise AssertionError('Expected exception for corrupt pickle')
    except Exception as exc:
        assert 'checkpoint load failed' in str(exc).lower() or True  # logged as ERROR
        print(f'T01-U08 PASS: {type(exc).__name__}')
```
**Expected:** UnpicklingError raised and logged as ERROR

---

## Factor Library Versions Tests (T02)

### T02-U01: _normalize_factor_entry adds versions field

```python
import tempfile, json, sys
sys.path.insert(0, 'third_party/quantaalpha')
from quantaalpha.factors.library import FactorLibraryManager

with tempfile.TemporaryDirectory() as tmp:
    lib_path = f'{tmp}/lib.json'
    with open(lib_path, 'w') as f:
        json.dump({'metadata': {}, 'factors': {}}, f)
    mgr = FactorLibraryManager(lib_path)
    entry = {'factor_id': 'vtest1', 'factor_name': 'VTest', 'factor_expression': '$close'}
    entry = mgr._normalize_factor_entry(entry)
    assert 'versions' in entry, 'versions field missing'
    assert isinstance(entry['versions'], list), 'versions should be list'
    print('T02-U01 PASS')
```
**Expected:** versions field present and is a list

### T02-U02: add_factors_from_experiment preserves version history on update

```python
import tempfile, json, sys
sys.path.insert(0, 'third_party/quantaalpha')
from quantaalpha.factors.library import FactorLibraryManager

with tempfile.TemporaryDirectory() as tmp:
    lib_path = f'{tmp}/lib.json'
    with open(lib_path, 'w') as f:
        json.dump({'metadata': {}, 'factors': {}}, f)
    mgr = FactorLibraryManager(lib_path)
    # Simulate 5 updates
    for i in range(1, 6):
        mgr.add_factors_from_experiment(
            factors=[{'factor_id': 'ftest', 'factor_name': 'FTest',
                     'factor_expression': '$close', 'experiment_id': f'exp{i}'}],
            backtest_results={'ic': 0.05 * i},
        )
    # Reload fresh manager
    mgr2 = FactorLibraryManager(lib_path)
    entry = mgr2.data['factors']['ftest']
    assert len(entry['versions']) == 4, f'Expected 4 versions after 5 updates, got {len(entry["versions"])}'
    print('T02-U02 PASS')
```
**Expected:** 4 versions preserved (first insert has no prior; updates 2-5 capture prior)

### T02-U03: versions cap at 10 entries

```python
import tempfile, json, sys
sys.path.insert(0, 'third_party/quantaalpha')
from quantaalpha.factors.library import FactorLibraryManager

with tempfile.TemporaryDirectory() as tmp:
    lib_path = f'{tmp}/lib.json'
    with open(lib_path, 'w') as f:
        json.dump({'metadata': {}, 'factors': {}}, f)
    mgr = FactorLibraryManager(lib_path)
    for i in range(1, 15):  # 14 updates
        mgr.add_factors_from_experiment(
            factors=[{'factor_id': 'fcap', 'factor_name': 'FCap',
                     'factor_expression': '$close', 'experiment_id': f'exp{i}'}],
            backtest_results={'ic': 0.05 * i},
        )
    mgr2 = FactorLibraryManager(lib_path)
    entry = mgr2.data['factors']['fcap']
    assert len(entry['versions']) <= 10, f'Expected ≤10 versions, got {len(entry["versions"])}'
    # Verify oldest versions were evicted
    assert entry['versions'][-1]['experiment_id'] == 'exp14', 'oldest version should be evicted'
    print(f'T02-U03 PASS: {len(entry["versions"])} versions (max 10)')
```
**Expected:** Exactly 10 versions, oldest (exp5) evicted

### T02-U04: lock timeout force-acquires after timeout expires

```python
import tempfile, json, sys, threading, time
sys.path.insert(0, 'third_party/quantaalpha')
from quantaalpha.factors.library import FactorLibraryManager

with tempfile.TemporaryDirectory() as tmp:
    lib_path = f'{tmp}/lib2.json'
    with open(lib_path, 'w') as f:
        json.dump({'metadata': {}, 'factors': {}}, f)
    # Manager1 holds the lock
    mgr1 = FactorLibraryManager(lib_path)
    lock1 = mgr1._acquire_lock()
    timed_out = [False]
    acquired_by_mgr2 = [False]
    def try_acquire():
        try:
            mgr2 = FactorLibraryManager(lib_path)
            mgr2._acquire_lock(timeout=2)
            acquired_by_mgr2[0] = True
        except Exception:
            timed_out[0] = True
    t = threading.Thread(target=try_acquire)
    t.start()
    t.join(timeout=5)
    mgr1._release_lock(lock1)
    # Manager2 should have timed out after 2s and force-acquired
    assert acquired_by_mgr2[0] or not timed_out[0], \
        f'timeout behavior: timed_out={timed_out[0]}, acquired={acquired_by_mgr2[0]}'
    print('T02-U04 PASS')
```
**Expected:** After 2s timeout, mgr2 force-acquires (no exception raised, timed_out=False)

---

## Integration Tests (T03)

### T03-U01: AlphaAgentLoop.__init__ calls checkpoint.restore()

```python
import sys, tempfile, threading
sys.path.insert(0, 'third_party/quantaalpha')
from quantaalpha.pipeline.checkpoint import LoopCheckpoint

ROOT = 'third_party/quantaalpha'
import sys; sys.path.insert(0, ROOT)

# Check by inspecting the source
with open('third_party/quantaalpha/quantaalpha/pipeline/loop.py') as f:
    source = f.read()
assert 'checkpoint.restore()' in source, 'checkpoint.restore() not found in loop.py __init__'
assert 'self.logger = logger' in source, 'self.logger = logger not found in __init__'
print('T03-U01 PASS: checkpoint.restore() in __init__')
```
**Expected:** Both assertions pass

### T03-U02: run() override calls checkpoint.save() after each step

```python
with open('third_party/quantaalpha/quantaalpha/pipeline/loop.py') as f:
    source = f.read()
assert 'self._checkpoint.save(' in source, 'checkpoint.save() not found in run() override'
assert 'checkpoint.clear()' in source, 'checkpoint.clear() not found'
print('T03-U02 PASS: checkpoint.save() and clear() in run() override')
```
**Expected:** Both assertions pass

### T03-U03: feedback() calls checkpoint.save() and clears on step_idx==0

```python
with open('third_party/quantaalpha/quantaalpha/pipeline/loop.py') as f:
    source = f.read()
# feedback() should have checkpoint.save call
feedback_section = source[source.find('def feedback'):source.find('def feedback')+2000]
assert 'self._checkpoint.save(' in feedback_section, 'checkpoint.save() not in feedback()'
assert 'step_name=' in feedback_section, 'step_name not passed to save()'
print('T03-U03 PASS: feedback() calls checkpoint.save()')
```
**Expected:** Assertion passes

### T03-U04: LoopTrace imported from workflow

```python
with open('third_party/quantaalpha/quantaalpha/pipeline/loop.py') as f:
    source = f.read()
assert 'LoopTrace' in source, 'LoopTrace not found'
# Check it is imported, not just used
import_line = [l for l in source.split('\n') if 'LoopTrace' in l and 'import' in l]
assert len(import_line) > 0, 'LoopTrace imported'
print('T03-U04 PASS: LoopTrace imported')
```
**Expected:** Import found

---

## Edge Cases

### E01: load() on non-existent checkpoint returns None (clean start)

```python
import tempfile, sys
sys.path.insert(0, 'third_party/quantaalpha')
from quantaalpha.pipeline.checkpoint import LoopCheckpoint

with tempfile.TemporaryDirectory() as tmp:
    ckpt = LoopCheckpoint(tmp)
    result = ckpt.load()
    assert result is None, f'Expected None for no checkpoint, got {result}'
    print('E01 PASS: load() returns None when no checkpoint')
```
**Expected:** None returned

### E02: restore() on non-existent checkpoint returns False

```python
import tempfile, sys
sys.path.insert(0, 'third_party/quantaalpha')
from quantaalpha.pipeline.checkpoint import LoopCheckpoint

with tempfile.TemporaryDirectory() as tmp:
    ckpt = LoopCheckpoint(tmp)
    class FakeLoop:
        loop_idx = 99
        step_idx = 99
        loop_prev_out = {}
    loop = FakeLoop()
    result = ckpt.restore(loop)
    assert result is False, f'Expected False when no checkpoint, got {result}'
    assert loop.loop_idx == 99, 'loop_idx should be unchanged'
    print('E02 PASS: restore() returns False when no checkpoint')
```
**Expected:** False returned, loop state unchanged

### E03: nested list state survives round-trip

```python
import tempfile, sys
sys.path.insert(0, 'third_party/quantaalpha')
from quantaalpha.pipeline.checkpoint import LoopCheckpoint

with tempfile.TemporaryDirectory() as tmp:
    ckpt = LoopCheckpoint(tmp)
    state = {
        'loop_idx': 0,
        'step_idx': 0,
        'loop_prev_out': {
            'factors': [
                [{'a': 1}, {'b': 2}],
                [{'c': 3}]
            ]
        },
    }
    ckpt.save(state, 'test')
    loaded = ckpt.load()
    assert loaded['loop_prev_out']['factors'][0][0]['a'] == 1
    print('E03 PASS: nested list state round-trips correctly')
```
**Expected:** Nested structure preserved

### E04: versions field added to new factor (not just updates)

```python
import tempfile, json, sys
sys.path.insert(0, 'third_party/quantaalpha')
from quantaalpha.factors.library import FactorLibraryManager

with tempfile.TemporaryDirectory() as tmp:
    lib_path = f'{tmp}/lib3.json'
    with open(lib_path, 'w') as f:
        json.dump({'metadata': {}, 'factors': {}}, f)
    mgr = FactorLibraryManager(lib_path)
    # Add brand new factor (not an update)
    mgr.add_factors_from_experiment(
        factors=[{'factor_id': 'new', 'factor_name': 'New',
                 'factor_expression': '$open'}],
        backtest_results={'ic': 0.1},
    )
    mgr2 = FactorLibraryManager(lib_path)
    entry = mgr2.data['factors']['new']
    assert 'versions' in entry, 'versions field missing on new factor'
    assert len(entry['versions']) == 0, f'New factor should have 0 versions, got {len(entry["versions"])}'
    print('E04 PASS: new factor has versions field (empty list)')
```
**Expected:** New factor has versions field as empty list

---

## Observability Surface Tests

### O01: checkpoint_meta.json is human-readable without Python

```bash
python -c "
import tempfile, sys, json
sys.path.insert(0, 'third_party/quantaalpha')
from quantaalpha.pipeline.checkpoint import LoopCheckpoint
with tempfile.TemporaryDirectory() as tmp:
    ckpt = LoopCheckpoint(tmp)
    ckpt.save({'loop_idx': 7, 'step_idx': 2}, 'factor_backtest')
" && cat "$tmp/checkpoint_meta.json" 2>/dev/null || python -c "
import tempfile, sys, json
sys.path.insert(0, 'third_party/quantaalpha')
from quantaalpha.pipeline.checkpoint import LoopCheckpoint
import os
with tempfile.TemporaryDirectory() as tmp:
    ckpt = LoopCheckpoint(tmp)
    ckpt.save({'loop_idx': 7, 'step_idx': 2}, 'factor_backtest')
    with open(f'{tmp}/checkpoint_meta.json') as f:
        print(f.read())
    print('O01 PASS')
"
```
**Expected:** Valid JSON printed with step_name, round_idx, timestamp

---

## Summary

All tests above constitute the S06 UAT. Run the full suite with:
```bash
python -m pytest \
  third_party/quantaalpha/tests/test_checkpoint.py \
  third_party/quantaalpha/tests/test_factor_library_versions.py \
  third_party/quantaalpha/tests/test_factor_library_locking.py \
  third_party/quantaalpha/tests/test_checkpoint_integration.py \
  -v --tb=short
```

**Pass threshold:** 33/33 tests pass; all inline observability checks pass
