# S08: ResourceManager 资源管理 (S7/D018) — Slice Summary

**Milestone:** M003
**Completed:** 2026-03-23
**Duration:** ~22 minutes total across all tasks
**Status:** ✅ Complete

## Goal

Implement ResourceManager for 24H autonomous operation with D018 constraints:
- Daily Token Budget hard cap (default 5M tokens) with circuit-breaking
- Disk Space Monitoring with WARNING/CRITICAL thresholds (<5GB warning, <2GB stop)
- result.h5 Auto-cleanup (30-day retention)
- Factor Library Entry Count Limits

## Deliverables

### Core Implementation

| File | Description | Size |
|------|-------------|------|
| `resource_manager.py` | ResourceManager class with ResourceConfig, ResourceStatus dataclasses, all enforcement methods | ~22KB |
| `test_resource_manager.py` | 38 comprehensive unit tests | ~22KB |

### Configuration

| File | Change |
|------|--------|
| `configs/experiment.yaml` | Added `resource_management` section with all D018 parameters |
| `pipeline/loop.py` | Integrated ResourceManager.check_and_enforce() in AlphaAgentLoop.run() |
| `factors/library.py` | Added `_check_entry_limit()` and `_get_max_entries_limit()` methods |

## What Was Built

### T01: ResourceManager Core Class

**Created `third_party/quantaalpha/quantaalpha/pipeline/resource_manager.py`** with:

1. **`ResourceConfig` dataclass** — Configuration for all D018 parameters:
   - `daily_token_limit: 5000000` (5M tokens)
   - `disk_space_min_gb: 5.0` (WARNING threshold)
   - `disk_space_stop_gb: 2.0` (CRITICAL threshold)
   - `result_retention_days: 30`
   - `factor_library_max_entries: 10000`

2. **`ResourceStatus` dataclass** — Status snapshot with fields:
   - `total_tokens_today`, `daily_token_limit`
   - `disk_space_gb`, `disk_space_status` (ok/warning/critical)
   - `oldest_result_h5_age_days`
   - `factor_library_entries`, `factor_library_entry_limit`
   - `within_budget`, `within_disk`, `checked_at`

3. **`ResourceManager` class** with methods:
   - `__init__()` — Loads config from experiment.yaml or uses defaults
   - `_load_daily_tokens()` / `_save_daily_tokens()` — Midnight reset via UTC date comparison
   - `get_token_usage_report()` — Returns ProviderPool tokens + daily tracking
   - `get_disk_space_report()` — Uses `shutil.disk_usage()` with thresholds
   - `cleanup_old_results()` — Removes result.h5 files older than retention period
   - `get_factor_library_entry_count()` — Queries FactorLibraryManager
   - `get_status()` — Returns full ResourceStatus snapshot
   - `check_and_enforce()` — Main enforcement gate returning `(bool, str)`

4. **Graceful fallback** when ProviderPool unavailable (`within_budget=None`)

5. **Module-level `resource_manager` singleton** for easy access

### T02: experiment.yaml Configuration & Factor Library Integration

**Modified `configs/experiment.yaml`** — Added `resource_management` section:
```yaml
resource_management:
  enabled: true
  daily_token_limit: 5000000
  token_budget_check_interval: 100000
  daily_token_reset_hour: 0  # UTC midnight
  disk_space_min_gb: 5.0    # WARNING threshold
  disk_space_stop_gb: 2.0   # CRITICAL threshold
  result_cleanup_enabled: true
  result_retention_days: 30
  result_cleanup_max_files: 100
  factor_library_max_entries: 10000
  sqlite_migration_threshold: 50000
```

**Modified `factors/library.py`** — Added entry limit enforcement:
- `_check_entry_limit()` — Checks if library is at or above limit, returns False + WARNING if so
- `_get_max_entries_limit()` — Loads config from experiment.yaml via Path resolution
- Integrated into `add_factors_from_experiment()` — Early exit if limit exceeded

### T03: loop.py Integration

**Modified `pipeline/loop.py`** — Added ResourceManager integration:
- Lazy `_get_resource_manager()` method (matches S06 checkpoint pattern)
- `run()` calls `check_and_enforce()` before each iteration
- Graceful loop termination with WARNING logs when budget exceeded

### T04: Unit Tests

**Created `tests/test_resource_manager.py`** — 38 tests across 9 test classes:

| Test Class | Tests | Coverage |
|------------|-------|----------|
| TestResourceConfig | 3 | defaults, from_dict, partial dict |
| TestResourceStatus | 5 | fields, within_budget computation |
| TestTokenTracking | 6 | add_tokens, daily reset, budget enforcement |
| TestDiskSpace | 5 | ok/warning/critical states, enforcement |
| TestResultCleanup | 6 | scanning, preservation, nested files |
| TestFactorLibraryIntegration | 3 | under/at limit, no library |
| TestEnforcementGate | 6 | allowed, blocked token, blocked disk, graceful |
| TestGetStatus | 2 | returns ResourceStatus, fields accessible |
| TestConfigUpdate | 2 | update values, invalid key |

## Patterns Established

1. **Lazy import pattern for ProviderPool/FactorLibraryManager** — Avoids circular dependencies
2. **Midnight reset via UTC date comparison** — Daily token tracking with persistent state
3. **Atomic JSON persistence** — tempfname + rename pattern for daily_tokens.json
4. **Config Path resolution** — Using `Path(__file__).parent.parent.parent` for config loading
5. **Early-exit pattern for resource limit checks** — `_check_entry_limit()` returns early
6. **Lazy resource manager initialization** — Matching S06 checkpoint pattern in loop.py

## Observability Surfaces

**Runtime inspection:**
```bash
python -c "from quantaalpha.pipeline.resource_manager import ResourceManager; print(ResourceManager().get_status())"
```

**Token usage report:**
```bash
python -c "from quantaalpha.pipeline.resource_manager import ResourceManager; print(ResourceManager().get_token_usage_report())"
```

**Disk space report:**
```bash
python -c "from quantaalpha.pipeline.resource_manager import ResourceManager; print(ResourceManager().get_disk_space_report())"
```

**Persisted state:**
- `~/.cache/quantaalpha/daily_tokens.json` — `{"date": "2026-03-23", "tokens": N}`

**Log signals:**
- WARNING when disk space below threshold
- INFO when midnight reset occurs or cleanup runs
- WARNING when budget exceeded or limit reached

## Verification Results

| # | Command | Exit | Verdict |
|---|---------|------|---------|
| 1 | `python -m py_compile resource_manager.py` | 0 | ✅ |
| 2 | `python -m pytest test_resource_manager.py -v` | 0 | ✅ (38/38) |
| 3 | `import yaml; yaml.safe_load(...)` for experiment.yaml | 0 | ✅ |
| 4 | `python -m py_compile loop.py` | 0 | ✅ |
| 5 | `python -m py_compile library.py` | 0 | ✅ |
| 6 | `ResourceManager().get_status()` | 0 | ✅ |

**Failure-path verification:**
```
tokens_today=0, disk_gb=300.5, disk_status=ok, entries=0, within_budget=None
```

## Integration Closure

**Upstream surfaces consumed:**
- `quantaalpha.llm.provider_pool:provider_pool` singleton for token tracking
- `quantaalpha.factors.library:FactorLibraryManager` for entry count
- `configs/experiment.yaml` for configuration

**New wiring introduced:**
- `loop.py:AlphaAgentLoop.run()` calls `resource_manager.check_and_enforce()` before each iteration
- `library.py:add_factors_from_experiment()` checks `factor_library_max_entries`

**What remains before milestone usable end-to-end:**
- S09 (M001 lessons) and S10 (ADR-003 orchestration) build on ResourceManager
- 72-hour UAT in M003 final verification

## Key Decisions

1. **Lazy ProviderPool import** — Avoids circular dependency; ProviderPool may not be initialized
2. **Graceful fallback** — When ProviderPool unavailable, `within_budget=None` allows operations
3. **UTC midnight reset** — Consistent with international server deployments
4. **Path-based config loading** — Using `Path(__file__).parent.parent.parent / 'configs' / 'experiment.yaml'`

## Known Issues

None.

## Next Steps

- S09: M001 教训设计约束转化 (depends on S04, S05, S06)
- S10: ADR-003 Phase 3 外插模块设计 (depends on S04, S06, S08)
- M003 72-hour UAT verification
