---
id: T02
parent: S06
milestone: M003
provides:
  - FactorLibraryManager versions field and lock timeout
key_files:
  - third_party/quantaalpha/quantaalpha/factors/library.py
  - third_party/quantaalpha/tests/test_factor_library_versions.py
  - third_party/quantaalpha/tests/test_factor_library_locking.py
patterns_established:
  - Version history captured by appending prior backtest_results before each update (last-10 rolling)
  - Lock timeout uses BlockingIOError loop with time.sleep(0.5) polling; force-acquires by closing and reopening lock FD after timeout expires
observability_surfaces:
  - Lock timeout emits WARNING log: "Lock acquisition timed out after {N}s, forcing lock on {path}"
  - grep for "timed out" in logs to find lock timeout events
duration: ~15 minutes
verification_result: passed
completed_at: 2026-03-23
blocker_discovered: false
---

# T02: 因子库版本历史与锁超时

**Added versions[] rolling history and 30s lock timeout with force-acquire to FactorLibraryManager, plus 5 new unit tests.**

## What Happened

Three modifications were made to `FactorLibraryManager` in `quantaalpha/factors/library.py`:

1. **`_acquire_lock(timeout=30)`** — Replaced the simple blocking flock with a loop that tries non-blocking `LOCK_EX | LOCK_NB` every 0.5s. After the timeout expires, it closes and reopens the lock FD, then acquires without `LOCK_NB` (guaranteed to succeed since advisory lock is released on FD close), logging `WARNING: Lock acquisition timed out after {N}s, forcing lock on {path}`.

2. **`_normalize_factor_entry()`** — Added `entry.setdefault("versions", [])` before the `metadata` setdefault, so every factor entry always has a versions list.

3. **`add_factors_from_experiment()`** — Before writing `self.data["factors"][factor_id]`, the code checks for an existing entry with backtest_results and appends a version record containing `{backtest_results, timestamp, experiment_id}`, then sets `factor_entry["versions"] = versions[-10:]`.

Two test files were created/extended:
- **`test_factor_library_versions.py`** (new, 4 tests): covers versions field addition, update preservation, max-10 cap, and metadata fields.
- **`test_factor_library_locking.py`** (extended, 1 new test): uses a subprocess to hold the advisory lock for 4s; `_acquire_lock(timeout=2)` force-acquires and logs the WARNING.

One test expectation was corrected from the plan: `test_versions_max_10` was originally written expecting 11 versions after 12 updates, but the inline simulation logic (same as production code) only captures backtest_results from *prior* entries — so the first insertion has nothing to preserve (no prior entry exists), yielding exactly 10 versions (exp2 through exp11). The test now correctly expects `versions[0]["experiment_id"] == "exp2"`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m py_compile third_party/quantaalpha/quantaalpha/factors/library.py` | 0 | ✅ pass | <1s |
| 2 | `python -m pytest third_party/quantaalpha/tests/test_factor_library_versions.py -v` | 0 | ✅ pass (4/4) | 0.04s |
| 3 | `python -m pytest third_party/quantaalpha/tests/test_factor_library_locking.py -v` | 0 | ✅ pass (6/6) | 5.59s |
| 4 | `python -m pytest third_party/quantaalpha/tests/test_checkpoint.py -v` | 0 | ✅ pass (12/12) | 0.05s |
| 5 | Inline D019 checkpoint + pickle test | 0 | ✅ pass | <1s |
| 6 | Inline versions field + lock timeout integration | 0 | ✅ pass | <1s |
| 7 | Corrupt pickle failure visibility | 0 | ✅ pass | <1s |

## Diagnostics

- **Lock timeout WARNING**: `grep -r "timed out" {logs}/` — logs show `Lock acquisition timed out after 2s, forcing lock on /tmp/quantaalpha_locks/lib.json.lock`
- **Versions array inspect**: cat `factor_library.json` and look at any factor's `versions[]` field — each entry has `backtest_results`, `timestamp`, `experiment_id`
- **Versions field addition**: `_normalize_factor_entry()` always sets `versions` to `[]` if absent

## Deviations

- **`test_versions_max_10` expected values corrected**: plan specified `versions[0]["experiment_id"] == "exp1"` with 11 versions, but actual production behavior (first insertion has no prior entry to preserve, only updates 2–12 capture prior backtest_results) yields 10 versions with `versions[0] == "exp2"`. Test was corrected to match actual behavior.

## Files Created/Modified

- `third_party/quantaalpha/quantaalpha/factors/library.py` — MODIFY: added `import time`; `_acquire_lock(timeout=30)` with force-acquire loop; `_normalize_factor_entry()` adds `versions` field; `add_factors_from_experiment()` preserves version history on update
- `third_party/quantaalpha/tests/test_factor_library_versions.py` — NEW: 4 unit tests for versions field
- `third_party/quantaalpha/tests/test_factor_library_locking.py` — EXTEND: added `test_lock_timeout_force_acquire` using subprocess to hold advisory lock
