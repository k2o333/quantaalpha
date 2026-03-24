---
id: T01
parent: S08
milestone: M003
provides:
  - ResourceManager core class with D018 constraints
key_files:
  - third_party/quantaalpha/quantaalpha/pipeline/resource_manager.py
  - third_party/quantaalpha/tests/test_resource_manager.py
patterns_established:
  - Lazy import pattern for ProviderPool/FactorLibraryManager (avoids circular deps)
  - Midnight reset via UTC date comparison for daily token tracking
  - Atomic JSON persistence using tempfile+rename pattern
observability_surfaces:
  - ResourceManager.get_status() — returns structured ResourceStatus snapshot
  - ResourceManager.check_and_enforce() — returns (allowed: bool, reason: str)
  - ~/.cache/quantaalpha/daily_tokens.json — persisted daily token state
  - WARNING logs when disk space below threshold
  - INFO logs when cleanup runs
duration: 4m
verification_result: passed
completed_at: 2026-03-23
blocker_discovered: false
---

# T01: Create ResourceManager core class

**Created ResourceManager class implementing D018 resource management for 24H autonomous operation.**

## What Happened

Implemented the core `ResourceManager` class in `third_party/quantaalpha/quantaalpha/pipeline/resource_manager.py` with all required components:

1. **`ResourceConfig` dataclass** — Configuration for all D018 parameters (daily token limit, disk space thresholds, result retention days, factor library entry limits)

2. **`ResourceStatus` dataclass** — Status snapshot with fields: `total_tokens_today`, `daily_token_limit`, `disk_space_gb`, `disk_space_status`, `oldest_result_h5_age_days`, `factor_library_entries`, `factor_library_entry_limit`, `within_budget`, `within_disk`, `checked_at`

3. **`ResourceManager` class** with:
   - `__init__()` — Loads config from experiment.yaml or uses defaults
   - `_load_daily_tokens()` / `_save_daily_tokens()` — Midnight reset via UTC date comparison, persists to `~/.cache/quantaalpha/daily_tokens.json`
   - `get_token_usage_report()` — Returns ProviderPool tokens + daily tracking
   - `get_disk_space_report()` — Uses `shutil.disk_usage()` with warning/critical thresholds
   - `cleanup_old_results()` — Removes result.h5 files older than retention period
   - `get_factor_library_entry_count()` — Queries FactorLibraryManager
   - `get_status()` — Returns full ResourceStatus snapshot
   - `check_and_enforce()` — Main enforcement gate returning `(bool, str)`
   - Module-level `resource_manager` singleton

4. **Graceful fallback** when ProviderPool unavailable (`within_budget=None`)

Also created comprehensive test suite with 33 passing tests covering all components.

## Verification

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m py_compile third_party/quantaalpha/quantaalpha/pipeline/resource_manager.py` | 0 | ✅ pass | ~0.1s |
| 2 | `python -m pytest third_party/quantaalpha/tests/test_resource_manager.py -v` | 0 | ✅ pass (33/33) | ~0.3s |
| 3 | `import yaml; yaml.safe_load(open('third_party/quantaalpha/configs/experiment.yaml'))` | 0 | ✅ pass | ~0.1s |
| 4 | `python -m py_compile third_party/quantaalpha/quantaalpha/pipeline/loop.py` | 0 | ✅ pass | ~0.1s |
| 5 | `python -m py_compile third_party/quantaalpha/quantaalpha/factors/library.py` | 0 | ✅ pass | ~0.1s |
| 6 | `ResourceManager().get_status()` — verify ResourceStatus fields | 0 | ✅ pass | ~0.2s |

**Failure-path verification:**
```
tokens_today=0, disk_gb=300.52, disk_status=ok, entries=0, within_budget=None
```

## Diagnostics

**Runtime inspection:**
```bash
# Get current resource status
python -c "from quantaalpha.pipeline.resource_manager import ResourceManager; print(ResourceManager().get_status())"

# Check if operations allowed
python -c "from quantaalpha.pipeline.resource_manager import ResourceManager; print(ResourceManager().check_and_enforce())"

# Token usage report
python -c "from quantaalpha.pipeline.resource_manager import ResourceManager; print(ResourceManager().get_token_usage_report())"

# Disk space report
python -c "from quantaalpha.pipeline.resource_manager import ResourceManager; print(ResourceManager().get_disk_space_report())"
```

**Persisted state:**
- `~/.cache/quantaalpha/daily_tokens.json` — Contains `{"date": "2026-03-23", "tokens": N}`

**Log signals:**
- WARNING when disk space below threshold
- INFO when midnight reset occurs or cleanup runs
- WARNING when budget exceeded or limit reached

## Deviations

None — implementation matched the task plan closely.

## Known Issues

None.

## Files Created/Modified

- `third_party/quantaalpha/quantaalpha/pipeline/resource_manager.py` — Core ResourceManager implementation (~22KB)
- `third_party/quantaalpha/tests/test_resource_manager.py` — Comprehensive test suite (~22KB, 33 tests)
