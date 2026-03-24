---
id: T02
parent: S08
milestone: M003
provides:
  - resource_management section in experiment.yaml
  - FactorLibraryManager._check_entry_limit() method
  - Factor library entry limit enforcement in add_factors_from_experiment()
key_files:
  - third_party/quantaalpha/configs/experiment.yaml
  - third_party/quantaalpha/quantaalpha/factors/library.py
patterns_established:
  - Lazy config loading from experiment.yaml using Path resolution
  - Early-exit pattern for resource limit checks
observability_surfaces:
  - WARNING log when factor library entry limit reached
  - _check_entry_limit() returns False to skip factor addition
duration: 10m
verification_result: passed
completed_at: 2026-03-23
blocker_discovered: false
---

# T02: Add experiment.yaml config and factor library integration

**Added `resource_management` configuration section to `experiment.yaml` and integrated entry limit checking into `FactorLibraryManager`.**

## What Happened

1. **Added `resource_management` section to `experiment.yaml`**:
   - Inserted new configuration section with all D018 parameters following existing patterns
   - Includes: `enabled`, `daily_token_limit: 5000000`, `disk_space_min_gb: 5.0`, `disk_space_stop_gb: 2.0`, `result_retention_days: 30`, `factor_library_max_entries: 10000`, `sqlite_migration_threshold: 50000`
   - Section placed after checkpoint configuration block

2. **Modified `FactorLibraryManager` in `library.py`**:
   - Added `_check_entry_limit()` method that:
     - Loads `factor_library_max_entries` from `experiment.yaml` via Path resolution
     - Counts current entries in library
     - Returns `False` and logs WARNING if at or above limit
     - Returns `True` if under limit or no limit configured
   - Added `_get_max_entries_limit()` helper method for config loading
   - Modified `add_factors_from_experiment()` to call `_check_entry_limit()` early in the method
   - When limit exceeded, logs warning and returns early without adding factors

## Verification

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m py_compile third_party/quantaalpha/quantaalpha/pipeline/resource_manager.py` | 0 | ✅ pass | ~0.1s |
| 2 | `python -m pytest third_party/quantaalpha/tests/test_resource_manager.py -v` | 0 | ✅ pass (33/33) | ~0.3s |
| 3 | `python -c "import yaml; yaml.safe_load(...)"` — YAML parse | 0 | ✅ pass | ~0.1s |
| 4 | `python -m py_compile third_party/quantaalpha/quantaalpha/pipeline/loop.py` | 0 | ✅ pass | ~0.1s |
| 5 | `python -m py_compile third_party/quantaalpha/quantaalpha/factors/library.py` | 0 | ✅ pass | ~0.1s |
| 6 | `ResourceManager().get_status()` — verify ResourceStatus fields | 0 | ✅ pass | ~0.2s |
| 7 | YAML resource_management field validation | 0 | ✅ pass | ~0.1s |
| 8 | `_check_entry_limit()` method test | 0 | ✅ pass | ~0.1s |

## Diagnostics

**Runtime inspection:**
```bash
# Verify resource_management config loaded correctly
cd third_party/quantaalpha
python -c "
from quantaalpha.factors.library import FactorLibraryManager
mgr = FactorLibraryManager('/tmp/test_lib.json')
print(f'Limit: {mgr._get_max_entries_limit()}')
print(f'Check: {mgr._check_entry_limit()}')
"

# Test entry limit enforcement
python -c "
from quantaalpha.factors.library import FactorLibraryManager
mgr = FactorLibraryManager('/tmp/test_lib.json')
# Should return True when under limit
result = mgr._check_entry_limit()
print(f'Under limit: {result}')
"
```

## Deviations

None — implementation matched the task plan closely.

## Known Issues

None.

## Files Modified

- `third_party/quantaalpha/configs/experiment.yaml` — Added `resource_management` section with all D018 parameters
- `third_party/quantaalpha/quantaalpha/factors/library.py` — Added `_check_entry_limit()` and `_get_max_entries_limit()` methods, integrated into `add_factors_from_experiment()`
