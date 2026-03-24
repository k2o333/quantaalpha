# S06: Checkpoint 与幂等性恢复 — Research

**Milestone:** M003 | **Slice:** S06 | **Status:** Research | **Date:** 2026-03-23

## Context Summary

S06 implements D017's three-part architecture: (1) `LoopCheckpoint`中断保存机制, (2) 因子库多版本历史留存, (3) 文件锁超时机制. The goal is crash recovery: a terminated process resumes from the last completed step rather than restarting entirely. This unblocks S09 (M001 design constraints → code constraints) which depends on checkpoint serialization safety.

## What Exists

### `LoopBase.run()` — existing snapshot mechanism
- **Location:** `quantaalpha/utils/workflow.py:90-134`
- Already calls `self.dump(path)` after every step completion
- Uses `pickle` serialization to `__session__/{loop_idx}/{step_idx}_{step_name}`
- Has NO checkpoint abstraction, NO human-readable metadata, NO crash-vs-clean-exit discrimination
- `LoopBase.dump()` calls `pickle.dump(self, f)` on the entire Loop object — large, slow, fragile with complex objects

### `AlphaAgentLoop` — the main pipeline
- **Location:** `quantaalpha/pipeline/loop.py:38-270`
- 5 steps per round: `factor_propose` → `factor_construct` → `factor_calculate` → `factor_backtest` → `feedback`
- `_save()` in `feedback` writes factors to library (no version history)
- Has `session_folder` attribute and existing `.dump()`/`.load()` methods
- No lock timeout, no step-level checkpoint metadata

### `FactorLibraryManager` — existing library
- **Location:** `quantaalpha/factors/library.py:32-719`
- `_acquire_lock()` uses `fcntl.flock(LOCK_EX)` with **no timeout** — blocks indefinitely
- `add_factors_from_experiment()` overwrites existing factor entries (no version history)
- `_normalize_factor_entry()` does NOT have a `versions` field
- `_save()` is atomic (tmp-file + `os.replace`) but lock has no timeout

### `experiment.yaml` — configuration
- **Location:** `quantaalpha/configs/experiment.yaml`
- No checkpoint config section exists yet

## What S06 Must Build

### Component 1: `pipeline/checkpoint.py` — LoopCheckpoint

New file with class `LoopCheckpoint`:

```python
class LoopCheckpoint:
    def __init__(self, checkpoint_dir: str | Path):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def save(self, loop_state: dict, step_name: str):
        # Writes checkpoint_meta.json (human-readable, D019 newline-safe)
        # Writes checkpoint_state.pkl (full loop state, D019 newline-validated)
        # D019 constraint: verify newline-containing fields serialize correctly

    def load(self) -> dict | None:
        # Returns loop_state dict or None if no checkpoint exists

    def restore(self, loop_instance: AlphaAgentLoop) -> bool:
        # Restores loop_instance.loop_idx, loop_instance.step_idx, loop_instance.loop_prev_out
        # Returns True if restored, False if no checkpoint

    def clear(self):
        # Removes checkpoint files on clean exit

    @property
    def exists(self) -> bool:
        return (self.checkpoint_dir / "checkpoint_meta.json").exists()
```

**Key design decisions:**
- `checkpoint_meta.json` uses JSON (human-readable, survives crashes) — stores step name, round, direction_id, trace length, timestamp
- `checkpoint_state.pkl` uses pickle for full loop state (existing pattern preserved)
- D019 constraint: before saving state, validate that all string fields in `loop_state` are safe for pickle (no raw control characters that could corrupt serialization)
- Checkpoint path: derived from `loop.session_folder` + `/checkpoint/` — aligns with existing `__session__/` structure
- `restore()` method specifically restores `loop_idx`, `step_idx`, `loop_prev_out` from the pickled state without instantiating a new loop

### Component 2: 因子库多版本历史

In `library.py`, three changes:

1. **`_normalize_factor_entry()`** — add `versions` field:
```python
entry.setdefault("versions", [])  # list of {backtest_results, timestamp, experiment_id}
```

2. **`add_factors_from_experiment()`** — preserve history on update:
```python
existing = self.data["factors"].get(factor_id)
if existing and existing.get("backtest_results"):
    versions = existing.get("versions", [])
    versions.append({
        "backtest_results": existing["backtest_results"],
        "timestamp": existing.get("metadata", {}).get("created_at"),
        "experiment_id": existing.get("metadata", {}).get("experiment_id"),
    })
    factor_entry["versions"] = versions[-10:]  # retain last 10
```

3. **`_acquire_lock()`** — add timeout with stale lock cleanup:
```python
def _acquire_lock(self, timeout: int = 30):
    # fcntl.flock(LOCK_EX | LOCK_NB) in a loop with 0.5s sleep
    # After timeout: force-acquire and log warning
    # Prevents deadlock when previous writer crashed without releasing lock
```

### Component 3: Integration into `AlphaAgentLoop`

In `loop.py`:
```python
# In __init__():
self._checkpoint = LoopCheckpoint(str(self.session_folder / "checkpoint"))
# Attempt restore from previous crash
self._checkpoint.restore(self)

# In run(): wrap step execution
# After each step completes successfully:
self._checkpoint.save(
    {
        "loop_idx": self.loop_idx,
        "step_idx": self.step_idx,
        "loop_prev_out": self.loop_prev_out,
        "round_idx": getattr(self, "round_idx", 0),
        "direction_id": getattr(self, "direction_id", 0),
        "trace_len": len(getattr(self, "trace", Trace(scen=None)).hist),
    },
    step_name=name,
)

# On clean exit (feedback step completing round):
if self.step_idx == 0:
    self._checkpoint.clear()
```

### Component 4: experiment.yaml checkpoint config

```yaml
checkpoint:
  enabled: true
  checkpoint_dir: null  # null = auto from session_folder
  lock_timeout_seconds: 30
  max_versions_per_factor: 10
```

## Key Files to Modify

| File | Change |
|------|--------|
| `quantaalpha/pipeline/checkpoint.py` | **NEW** — LoopCheckpoint class |
| `quantaalpha/pipeline/loop.py` | Import LoopCheckpoint, add to `__init__`, call `save/restore/clear` |
| `quantaalpha/factors/library.py` | `versions` field in `_normalize_factor_entry()`, history in `add_factors_from_experiment()`, timeout in `_acquire_lock()` |
| `quantaalpha/configs/experiment.yaml` | Add `checkpoint:` section |
| `quantaalpha/tests/test_checkpoint.py` | **NEW** — unit tests for LoopCheckpoint |
| `quantaalpha/tests/test_factor_library_locking.py` | Add lock timeout test |

## Verification Plan

### Contract verification (S06-T01)
```bash
# Syntax check all modified files
python -m py_compile third_party/quantaalpha/quantaalpha/pipeline/checkpoint.py
python -m py_compile third_party/quantaalpha/quantaalpha/factors/library.py
python -m py_compile third_party/quantaalpha/quantaalpha/pipeline/loop.py

# Lock timeout test
python -m pytest third_party/quantaalpha/tests/test_factor_library_locking.py -v

# New checkpoint unit tests
python -m pytest third_party/quantaalpha/tests/test_checkpoint.py -v
```

### D019 constraint verification (S06-T02)
```bash
# Verify newline-containing fields in checkpoint serialize safely
python -c "
import pickle, json
from pathlib import Path
from quantaalpha.pipeline.checkpoint import LoopCheckpoint
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    ckpt = LoopCheckpoint(tmp)
    # Simulate state with newlines in hypothesis/feedback text
    state = {
        'loop_idx': 0,
        'step_idx': 1,
        'loop_prev_out': {
            'factor_propose': {'hypothesis': 'line1\nline2\nline3\twith\ttabs'}
        },
        'round_idx': 0,
        'trace_len': 2,
    }
    ckpt.save(state, 'factor_propose')
    loaded = ckpt.load()
    assert loaded is not None, 'Checkpoint load failed'
    # Verify JSON meta is valid
    with open(Path(tmp)/'checkpoint_meta.json') as f:
        meta = json.load(f)
    assert meta['step_name'] == 'factor_propose'
    print('D019 checkpoint serialization: PASS')
"
```

### Integration verification (S06-T03)
```bash
# Verify versions field added to factor entries
python -c "
import json, tempfile, sys
sys.path.insert(0, 'third_party/quantaalpha')
from pathlib import Path
# ... verify versions field in normalized entry
"

# Verify lock timeout prevents indefinite blocking
# (thread acquires lock, doesn't release; second thread times out)
```

## Forward Intelligence

1. **Pickle fragility**: The existing `LoopBase.dump()` pickles the entire loop object including potentially complex objects (LLM backends, threads). `LoopCheckpoint.save()` should extract a serializable subset of state (`loop_idx`, `step_idx`, `loop_prev_out`, `trace`, `round_idx`, etc.) rather than `self` directly.

2. **D019 newline constraint**: The original M001 bug was about JSON control characters in LLM responses. Checkpoint pickle files can contain strings with newlines (e.g., hypothesis text with newlines). Verify `pickle.dumps()` handles these without corruption. If issues arise, base64-encode affected fields.

3. **Stale lock cleanup**: When `_acquire_lock()` times out, the force-acquire path must handle the case where the stale lock file itself is corrupted. The force path should: `lock_fd.close()` → re-open → `fcntl.flock(LOCK_EX)` unconditionally.

4. **S09 dependency**: S09 needs checkpoint to exist before it can write design constraints tests. The `versions` field in factor entries provides a natural hook for S09 to verify that historical versions are preserved correctly.

5. **Atomic writes**: `checkpoint_meta.json` should also use an atomic write pattern (tmp file + rename) to avoid reading a partially-written file on crash.

## Don't Hand-Roll

- **Atomic file writes**: Use the same tmp-file + `os.rename`/`os.replace` pattern already proven in `library.py:_save()`
- **File locking**: Already uses `fcntl` — just add timeout loop and `LOCK_NB` flag
- **Session folder**: Use existing `self.session_folder` from `LoopBase`, already set by `logger.log_trace_path / "__session__"`
- **Trace serialization**: `Trace` objects may contain complex objects — extract primitive fields only

## Sources

- `quantaalpha/utils/workflow.py` — existing LoopBase.run(), dump(), load()
- `quantaalpha/pipeline/loop.py` — AlphaAgentLoop 5-step pipeline, feedback() saves to library
- `quantaalpha/factors/library.py` — FactorLibraryManager, atomic save, no lock timeout, no version history
- `quantaalpha/configs/experiment.yaml` — config structure
- `quantaalpha/tests/test_factor_library_locking.py` — existing lock test patterns
- `docs/archived/drafts/factormining/structure/2026-03-22-continuous-mining-plan-supplement.md` — S5 specification
- D017 decision in `.gsd/DECISIONS.md`
- D019 constraint: "Checkpoint 序列化需验证含换行符字段的兼容性"
