# T02: 因子库版本历史与锁超时

**Slice:** S06 — Checkpoint 与幂等性恢复
**Milestone:** M003

## Description

在 `FactorLibraryManager` 中实现两个 D017 需求：(1) 因子库多版本历史 — 同一 factor_id 更新时保留最近 10 个 backtest_results；(2) 文件锁超时 — `_acquire_lock()` 30 秒超时后强制获取并记录警告（D019 约束，防止死锁）。

## Steps

1. **Modify `quantaalpha/factors/library.py`** — three changes:

   a. **`_normalize_factor_entry()`** (line ~446): add `versions` field with `setdefault`:
      ```python
      entry.setdefault("versions", [])  # list of {backtest_results, timestamp, experiment_id}
      ```
      Place before the `entry.setdefault("metadata", {})` line.

   b. **`add_factors_from_experiment()`** (line ~248): before `self.data["factors"][factor_id] = factor_entry`, preserve history on update:
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

   c. **`_acquire_lock()`** (line ~47): add 30-second timeout with force-acquire:
      ```python
      import time  # already imported at top of file

      def _acquire_lock(self, timeout: int = 30):
          self._ensure_lock_dir()
          lock_file = self._lock_dir / f"{self.library_path.name}.lock"
          lock_fd = open(lock_file, "w")
          start_time = time.time()
          while True:
              try:
                  fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                  return lock_fd
              except BlockingIOError:
                  if time.time() - start_time >= timeout:
                      # Force acquire after timeout
                      try:
                          lock_fd.close()
                      except Exception:
                          pass
                      lock_fd = open(lock_file, "w")
                      fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
                      logger.warning(
                          f"Lock acquisition timed out after {timeout}s, forcing lock on {lock_file}"
                      )
                      return lock_fd
                  time.sleep(0.5)
      ```

2. **Create `quantaalpha/tests/test_factor_library_versions.py`** — unit tests for versions field:
   - `test_normalize_adds_versions_field` — verify `_normalize_factor_entry()` adds `versions` as empty list
   - `test_versions_preserved_on_update` — save factor with backtest_results, update same factor_id, verify versions[-1] has old backtest_results
   - `test_versions_max_10` — update same factor 12 times, verify len(versions) == 10
   - `test_versions_contains_timestamp_and_experiment_id` — verify versions entry has correct metadata

3. **Extend `quantaalpha/tests/test_factor_library_locking.py`** — add lock timeout test:
   - `test_lock_timeout_force_acquire` — acquire lock, don't release, try second acquire with timeout=2, verify force acquire succeeds after timeout with WARNING log

4. **Verify syntax and run tests**:
   - `python -m py_compile third_party/quantaalpha/quantaalpha/factors/library.py`
   - `python -m pytest third_party/quantaalpha/tests/test_factor_library_versions.py -v`
   - `python -m pytest third_party/quantaalpha/tests/test_factor_library_locking.py -v`

## Must-Haves

- [ ] `_normalize_factor_entry()` adds `versions` field (empty list)
- [ ] `add_factors_from_experiment()` preserves up to 10 historical versions on factor update
- [ ] versions entry contains `backtest_results`, `timestamp`, `experiment_id`
- [ ] `_acquire_lock(timeout=30)` times out after 30 seconds and force-acquires with WARNING log
- [ ] All existing locking tests still pass (concurrent saves, atomic writes)
- [ ] 4 versions tests + 1 lock timeout test pass

## Verification

```bash
# Syntax check
python -m py_compile third_party/quantaalpha/quantaalpha/factors/library.py

# Run versions field tests
python -m pytest third_party/quantaalpha/tests/test_factor_library_versions.py -v

# Run lock tests (existing + new timeout test)
python -m pytest third_party/quantaalpha/tests/test_factor_library_locking.py -v

# Inline versions + timeout verification
python -c "
import json, tempfile, sys, time, threading
sys.path.insert(0, 'third_party/quantaalpha')
from pathlib import Path
from quantaalpha.factors.library import FactorLibraryManager

# versions field test
with tempfile.TemporaryDirectory() as tmp:
    lib_path = Path(tmp) / 'lib.json'
    lib_path.write_text(json.dumps({'metadata':{},'factors':{}}), encoding='utf-8')
    mgr = FactorLibraryManager(str(lib_path))
    entry = {'factor_id': 'vtest1', 'factor_name': 'VTest', 'factor_expression': '\$close'}
    entry = mgr._normalize_factor_entry(entry)
    assert 'versions' in entry, 'versions field missing'
    assert isinstance(entry['versions'], list), 'versions should be list'
    print('versions field: PASS')

# lock timeout test
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

## Observability Impact

- Signals added: Lock timeout emits `logger.warning()` with path and duration; force-acquire path logged at WARNING level
- How a future agent inspects: `grep -r "timed out" {logs}/` to find lock timeout events
- Failure state exposed: Stale lock → timeout warning logged, lock force-acquired, operations continue

## Inputs

- `third_party/quantaalpha/quantaalpha/factors/library.py` — source file to modify (_normalize_factor_entry at line ~446, add_factors_from_experiment at line ~248, _acquire_lock at line ~47)

## Expected Output

- `third_party/quantaalpha/quantaalpha/factors/library.py` — MODIFY: versions field + lock timeout
- `third_party/quantaalpha/tests/test_factor_library_versions.py` — NEW: 4 unit tests for versions field
- `third_party/quantaalpha/tests/test_factor_library_locking.py` — EXTEND: 1 new lock timeout test
