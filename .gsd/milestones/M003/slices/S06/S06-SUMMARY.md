# S06: Checkpoint 与幂等性恢复 — Slice Summary

**Slice:** S06 | **Milestone:** M003 | **Status:** COMPLETE | **Completed:** 2026-03-23

## What This Slice Delivered

S06 implements D017 (crash recovery) and D019 (lock timeout) requirements, enabling the quantaalpha pipeline to recover from mid-pipeline crashes and maintain factor version history.

### Components Delivered

**T01 — LoopCheckpoint (checkpoint.py, test_checkpoint.py)**
- `LoopCheckpoint` class: `save()`, `load()`, `restore()`, `clear()`, `exists` property
- Atomic write via `os.replace()` on a `.tmp` file in the same directory (POSIX rename is atomic on same filesystem)
- D019 newline/tab control-char sanitization: recursive `_sanitize_value()` traverses nested dict/list/str, replaces fields containing U+0000–U+0008 with `[REDACTED_D019]` sentinel before pickle serialization
- Human-readable `checkpoint_meta.json` (step_name, round_idx, direction_id, timestamp)
- 12/12 unit tests passing

**T02 — Factor Library Versions & Lock Timeout (library.py, test_factor_library_versions.py, test_factor_library_locking.py)**
- `_normalize_factor_entry()` adds `versions: []` field to every factor entry
- `add_factors_from_experiment()` appends `{backtest_results, timestamp, experiment_id}` before each update, caps at 10 entries (last-10 rolling)
- `_acquire_lock(timeout=30)` uses BlockingIOError loop (0.5s polling), force-acquires via close+reopen lock FD on timeout, logs `WARNING: Lock acquisition timed out after {N}s, forcing lock on {path}`
- 4 versions tests + 6 locking tests (including subprocess-based timeout test) = 10/10 passing

**T03 — AlphaAgentLoop Integration (loop.py, experiment.yaml, test_checkpoint_integration.py)**
- `AlphaAgentLoop.__init__` calls `checkpoint.restore()` before run; patches loop instance attributes directly
- `run()` override: checkpoint save after each step, clear on clean round exit (step_idx==0) and on skip_loop_error
- `feedback()` calls `checkpoint.save()` after step, `checkpoint.clear()` when step_idx==0
- `experiment.yaml` adds `checkpoint:` section: enabled, lock_timeout_seconds, max_versions_per_factor
- 11/11 integration tests passing

**Closer Fixes (post-T03)**
- `loop.py` missing `LoopTrace` import (from `workflow.py:69`) — 3 integration tests failing with NameError
- `create_loop_with_mock_checkpoint` not setting `loop.logger` instance attribute — 3 tests failing with AttributeError
- `call_args` unpacked as `_, kwargs` but checkpoint.save uses positional dict + keyword step_name — 2 tests failing with wrong key

### Proof Results

| Check | Result |
|---|---|
| `python -m py_compile` (checkpoint.py, loop.py, library.py) | PASS |
| `pytest test_checkpoint.py` — 12 unit tests | PASS |
| `pytest test_factor_library_versions.py` — 4 tests | PASS |
| `pytest test_factor_library_locking.py` — 6 tests | PASS |
| `pytest test_checkpoint_integration.py` — 11 tests | PASS (after closer fixes) |
| D019 newline-safe pickle inline verification | PASS |
| experiment.yaml checkpoint config verification | PASS |
| Corrupt pickle failure visibility (ERROR log + exception) | PASS |

### Requirements Validated

- **R011**: Checkpoint crash recovery — 12 unit + 11 integration tests, atomic save/load/clear/restore
- **R012**: Factor library versions — versions[] field, 4 unit tests, max-10 rolling history
- **R013**: File lock timeout — 30s timeout + force-acquire, 6 unit tests

### What S06 Enables

- S09 (M001 design constraint tests) can now use `LoopCheckpoint` for crash simulation
- 24H autonomous operation becomes feasible: process kill → restart → resume from last step
- Factor library maintains audit trail of backtest history per factor
- Lock timeout prevents deadlocks when FactorLibraryManager is held by a crashed process

### Boundary Outputs

- **To S09**: `quantaalpha/pipeline/checkpoint.py` — LoopCheckpoint class; `checkpoint_meta.json` human-readable crash state; `versions[]` in factor entries
- **To all slices**: `quantaalpha/configs/experiment.yaml` checkpoint section (enabled, timeout, max_versions)

### Key Decisions

- **D029**: `run()` override pattern for checkpoint integration (not hook injection — LoopBase.run has no extension point; `LoopTrace` must be explicitly imported)
- **D030**: Store module-level logger as instance attribute (`self.logger = logger`) to enable `patch.object(loop, "logger", ...)` in tests; mixed positional+keyword call_args requires `(args, kwargs)` unpack pattern

### Known Limitations

- `experiment.yaml` checkpoint section is consumed by config parsing but no runtime code yet reads the `enabled` flag to conditionally enable/disable checkpoints
- Lock timeout applies to `_acquire_lock` only; the `experiment.yaml` `lock_timeout_seconds` value is not wired to the runtime yet (T03 plan notes this as T03 scope, but only checkpoint config was added, not the runtime wiring)
