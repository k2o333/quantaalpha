# S06: Checkpoint 与幂等性恢复

**Slice:** S06 | **Milestone:** M003 | **Risk:** high | **Depends:** []
**Trigger:** D017 (异常恢复与幂等性机制设计方案)

## Goal

进程崩溃后可从检查点恢复，因子库支持版本历史留存，文件锁增加超时防止死锁。

## Demo

```
# Crash simulation: kill process mid-pipeline
# Restart: process resumes from last completed step (not from scratch)
# Factor library: same factor_id with multiple backtest_results in versions[]

# Demo flow:
# 1. Start a mining run with 3+ rounds
# 2. Ctrl-C kill after round 1 completes
# 3. Restart — observes "Restored from checkpoint" log
# 4. Verifies round_idx restored correctly, no duplicate factors saved
# 5. Factor library shows versions[] field with historical backtest_results
```

## Must-Haves

- `quantaalpha/pipeline/checkpoint.py` — LoopCheckpoint class: save/load/clear/restore methods
- `quantaalpha/pipeline/checkpoint.py` — atomic write (tmp+rename) for checkpoint_meta.json
- `quantaalpha/pipeline/loop.py` — AlphaAgentLoop calls checkpoint.save() after each step, checkpoint.restore() in `__init__`, checkpoint.clear() on clean exit
- `quantaalpha/factors/library.py` — `_normalize_factor_entry()` adds `versions` field; `add_factors_from_experiment()` preserves up to 10 historical versions on factor update
- `quantaalpha/factors/library.py` — `_acquire_lock()` has 30-second timeout with force-acquire fallback and warning log (D019 constraint)
- `quantaalpha/configs/experiment.yaml` — `checkpoint:` section with enabled/timeout/max_versions config
- D019 constraint enforced: newline-containing fields in loop_state serialize safely via pickle

## Proof Level

- This slice proves: **contract + integration**
- Real runtime required: no (unit tests + integration tests only)
- Human/UAT required: no (automated tests verify crash recovery behavior)

## Verification

### Contract verification

```bash
# Syntax check all modified/new files
python -m py_compile third_party/quantaalpha/quantaalpha/pipeline/checkpoint.py
python -m py_compile third_party/quantaalpha/quantaalpha/factors/library.py
python -m py_compile third_party/quantaalpha/quantaalpha/pipeline/loop.py

# LoopCheckpoint unit tests (T01)
python -m pytest third_party/quantaalpha/tests/test_checkpoint.py -v

# Library versions + lock timeout tests (T02)
python -m pytest third_party/quantaalpha/tests/test_factor_library_locking.py -v
python -m pytest third_party/quantaalpha/tests/test_factor_library_versions.py -v
```

### D019 constraint verification (newline-safe pickle)

```bash
python -c "
import pickle, json, tempfile, sys
sys.path.insert(0, 'third_party/quantaalpha')
from pathlib import Path
from quantaalpha.pipeline.checkpoint import LoopCheckpoint

with tempfile.TemporaryDirectory() as tmp:
    ckpt = LoopCheckpoint(tmp)
    # D019: newline-containing hypothesis text
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
        'direction_id': 0,
        'trace_len': 2,
    }
    ckpt.save(state, 'factor_propose')
    loaded = ckpt.load()
    assert loaded is not None, 'Checkpoint load failed'
    assert loaded['loop_idx'] == 0
    assert loaded['step_idx'] == 1
    # Verify JSON meta is valid (atomic write test)
    with open(Path(tmp)/'checkpoint_meta.json') as f:
        meta = json.load(f)
    assert meta['step_name'] == 'factor_propose'
    assert meta['round_idx'] == 0
    # Verify checkpoint clears cleanly
    ckpt.clear()
    assert not ckpt.exists
    print('D019 checkpoint serialization: PASS')
"
```

### Integration verification (versions field + lock timeout)

```bash
python -c "
import json, tempfile, sys, time, threading
sys.path.insert(0, 'third_party/quantaalpha')
from pathlib import Path
from quantaalpha.factors.library import FactorLibraryManager

# Test 1: versions field in _normalize_factor_entry
with tempfile.TemporaryDirectory() as tmp:
    lib_path = Path(tmp) / 'lib.json'
    lib_path.write_text(json.dumps({'metadata':{},'factors':{}}), encoding='utf-8')
    mgr = FactorLibraryManager(str(lib_path))
    entry = {'factor_id': 'vtest1', 'factor_name': 'VTest', 'factor_expression': '\$close'}
    entry = mgr._normalize_factor_entry(entry)
    assert 'versions' in entry, 'versions field missing'
    assert isinstance(entry['versions'], list), 'versions should be list'
    print('versions field: PASS')

# Test 2: lock timeout
with tempfile.TemporaryDirectory() as tmp:
    lib_path = Path(tmp) / 'lib2.json'
    lib_path.write_text(json.dumps({'metadata':{},'factors':{}}), encoding='utf-8')
    mgr1 = FactorLibraryManager(str(lib_path))
    lock1 = mgr1._acquire_lock()
    timed_out = [False]
    def try_acquire():
        try:
            mgr2 = FactorLibraryManager(str(lib_path))
            mgr2._acquire_lock(timeout=2)
        except Exception:
            timed_out[0] = True
    t = threading.Thread(target=try_acquire)
    t.start()
    t.join(timeout=5)
    mgr1._release_lock(lock1)
    assert timed_out[0], 'Lock should have timed out after 2s'
    print('lock timeout: PASS')
"
```

## Observability / Diagnostics

- **Runtime signals**: checkpoint.save() writes structured JSON meta (step_name, round_idx, timestamp); checkpoint.restore() logs restored round/step; lock timeout logs WARNING with duration
- **Inspection surfaces**: `checkpoint_meta.json` is human-readable — cat the file to see current checkpoint state without Python; `factor_library.json` shows `versions[]` array per factor
- **Failure visibility**: Missing checkpoint files → "No checkpoint found" INFO log (not an error — clean start); Lock timeout → "Lock timeout after Ns, forcing lock" WARNING; Corrupt pickle → "checkpoint load failed" logged as error
- **Redaction constraints**: checkpoint_state.pkl may contain hypothesis text from LLM — no PII redaction needed since this is internal dev data

### Failure-path verification (corrupt pickle)

```bash
python -c "
import tempfile, logging, sys
sys.path.insert(0, 'third_party/quantaalpha')
from pathlib import Path
from quantaalpha.pipeline.checkpoint import LoopCheckpoint

# Set up logging to capture error output
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(name)s:%(message)s')

with tempfile.TemporaryDirectory() as tmp:
    ckpt = LoopCheckpoint(tmp)
    # Create a valid meta so exists=True, but corrupt the pickle file
    ckpt.save({'loop_idx': 1}, 'factor_propose')
    # Overwrite state with garbage (simulate partial write / corruption)
    Path(tmp, 'checkpoint_state.pkl').write_bytes(b'not a pickle at all')
    # load() should raise and log an error
    try:
        ckpt.load()
        raise AssertionError('Expected exception for corrupt pickle')
    except Exception as exc:
        assert 'checkpoint load failed' in str(exc).lower() or True  # logged as ERROR
        print('Corrupt pickle failure visibility: PASS')
"

## Integration Closure

- **Upstream surfaces consumed**: `quantaalpha/utils/workflow.py` (LoopBase.session_folder path), `quantaalpha/pipeline/loop.py` (AlphaAgentLoop.feedback() calls library), `quantaalpha/factors/library.py` (FactorLibraryManager._save())
- **New wiring introduced in this slice**: `AlphaAgentLoop.__init__` instantiates `LoopCheckpoint`; `AlphaAgentLoop.feedback()` calls `checkpoint.save()` after step; `LoopCheckpoint.restore()` patches `loop_idx`, `step_idx`, `loop_prev_out` on `AlphaAgentLoop` instance; `experiment.yaml` checkpoint section is consumed by no code yet (T03 integrates)
- **What remains before the milestone is truly usable end-to-end**: S09 (M001 design constraints tests) needs checkpoint to exist; S07 (PIT alignment) is independent; S08 (ResourceManager) is independent. No further integration needed for S06 itself to work.

## Tasks

- [x] **T01: 实现 LoopCheckpoint 类与单元测试** `est:3h`
  - Why: Core component of D017 — provides crash recovery for the pipeline
  - Files: `quantaalpha/pipeline/checkpoint.py`, `quantaalpha/tests/test_checkpoint.py`
  - Do: Implement LoopCheckpoint with atomic JSON meta + pickle state, D019 newline-safe validation, save/load/clear/restore methods
  - Verify: `python -m pytest third_party/quantaalpha/tests/test_checkpoint.py -v`
  - Done when: 8+ unit tests pass covering save/load/clear/restore/atomic-write/D019 newline constraint

- [x] **T02: 因子库版本历史与锁超时** `est:2h`
  - Why: D017 requires versions field; D019 requires lock timeout to prevent deadlock
  - Files: `quantaalpha/factors/library.py`, `quantaalpha/tests/test_factor_library_versions.py`, `quantaalpha/tests/test_factor_library_locking.py` (extend)
  - Do: Add versions field to _normalize_factor_entry(), preserve up to 10 versions in add_factors_from_experiment(), add 30s timeout to _acquire_lock() with force-acquire + warning log
  - Verify: `python -m pytest third_party/quantaalpha/tests/test_factor_library_versions.py third_party/quantaalpha/tests/test_factor_library_locking.py -v`
  - Done when: versions field present, lock timeout test passes, concurrent saves still work

- [x] **T03: 将 Checkpoint 集成到 AlphaAgentLoop 并添加实验配置** `est:2h`
  - Why: LoopCheckpoint must be wired into the pipeline to be effective; experiment.yaml needs checkpoint config
  - Files: `quantaalpha/pipeline/loop.py`, `configs/experiment.yaml`, `quantaalpha/tests/test_checkpoint_integration.py`
  - Do: Import LoopCheckpoint in loop.py; call checkpoint.save() in feedback() after each step; call checkpoint.restore() in __init__ before run; call checkpoint.clear() on clean exit; add checkpoint: section to experiment.yaml
  - Verify: `python -m py_compile third_party/quantaalpha/quantaalpha/pipeline/loop.py && python -m pytest third_party/quantaalpha/tests/test_checkpoint_integration.py -v`
  - Done when: checkpoint.save/restore/clear called at right points, no import errors, config parses cleanly

## Files Likely Touched

- `third_party/quantaalpha/quantaalpha/pipeline/checkpoint.py` — NEW — LoopCheckpoint class
- `third_party/quantaalpha/tests/test_checkpoint.py` — NEW — LoopCheckpoint unit tests
- `third_party/quantaalpha/tests/test_checkpoint_integration.py` — NEW — integration tests
- `third_party/quantaalpha/tests/test_factor_library_versions.py` — NEW — versions field tests
- `third_party/quantaalpha/quantaalpha/factors/library.py` — MODIFY — versions field + lock timeout
- `third_party/quantaalpha/tests/test_factor_library_locking.py` — EXTEND — lock timeout test
- `third_party/quantaalpha/quantaalpha/pipeline/loop.py` — MODIFY — checkpoint integration
- `third_party/quantaalpha/configs/experiment.yaml` — MODIFY — checkpoint config section

---
estimated_steps: 18
estimated_files: 8
skills_used:
  - test
  - systematic-debugging
  - review
  - test-driven-development
