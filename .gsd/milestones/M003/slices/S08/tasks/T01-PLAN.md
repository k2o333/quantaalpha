# T01: Create ResourceManager core class

**Slice:** S08 — ResourceManager 资源管理 (S7/D018)
**Milestone:** M003

## Description

Create the core `ResourceManager` class implementing D018 resource management constraints:
1. Daily token budget tracking with automatic midnight reset
2. Disk space monitoring using `shutil.disk_usage()`
3. result.h5 cleanup with age-based filtering
4. Factor library entry count enforcement

This task creates `resource_manager.py` which is the foundation for the entire slice.

## Steps

1. **Create `resource_manager.py`** in `third_party/quantaalpha/quantaalpha/pipeline/` with:
   - `ResourceConfig` dataclass: all D018 parameters (daily_token_limit, disk_space thresholds, retention days, entry limits)
   - `ResourceStatus` dataclass: status snapshot (total_tokens_today, disk_space_gb, disk_space_status, oldest_result_h5_age_days, factor_library_entries, within_budget, within_disk)
   - `ResourceManager` class:
     - `__init__()`: Load config from experiment.yaml or use defaults; initialize daily token counter
     - `_get_provider_pool()`: Lazy import to avoid circular dependency
     - `_load_daily_tokens()` / `_save_daily_tokens()`: Persist daily token count to `~/.cache/quantaalpha/daily_tokens.json`
     - `get_token_usage_report()`: Get ProviderPool tokens + daily tracking
     - `get_disk_space_report()`: Get disk space status using `shutil.disk_usage()`
     - `cleanup_old_results()`: Remove result.h5 files older than retention period
     - `get_factor_library_entry_count()`: Query FactorLibraryManager for entry count
     - `get_status()`: Return full ResourceStatus snapshot
     - `check_and_enforce()`: Main enforcement gate, returns `(allowed: bool, reason: str)`
   - Module-level `resource_manager` singleton

2. **Follow existing patterns:**
   - Use lazy import pattern from S04 `provider_pool.py`
   - Use dataclass `@dataclass` decorator
   - Cross-platform disk space via `shutil.disk_usage()`
   - JSON persistence for daily token tracking

3. **Validation:**
   ```bash
   python -m py_compile third_party/quantaalpha/quantaalpha/pipeline/resource_manager.py
   ```

## Must-Haves

- [ ] `ResourceConfig` dataclass with all D018 parameters (daily_token_limit, disk_space thresholds, retention, entry limits)
- [ ] `ResourceStatus` dataclass with status snapshot fields
- [ ] `ResourceManager.__init__()` loads config from experiment.yaml or defaults
- [ ] `ResourceManager._load_daily_tokens()` / `_save_daily_tokens()` for daily reset logic
- [ ] `ResourceManager.get_disk_space_report()` using `shutil.disk_usage()`
- [ ] `ResourceManager.cleanup_old_results()` with age-based filtering
- [ ] `ResourceManager.check_and_enforce()` returns `(bool, str)` for budget enforcement
- [ ] `ResourceManager.get_status()` returns ResourceStatus snapshot
- [ ] Module-level `resource_manager` singleton export
- [ ] Graceful fallback when ProviderPool unavailable

## Verification

- `python -m py_compile third_party/quantaalpha/quantaalpha/pipeline/resource_manager.py`
- Test status snapshot structure:
  ```bash
  python -c "
  from quantaalpha.pipeline.resource_manager import ResourceManager, ResourceStatus, ResourceConfig
  cfg = ResourceConfig()
  mgr = ResourceManager()
  status = mgr.get_status()
  print(f'type={type(status).__name__}')
  assert hasattr(status, 'total_tokens_today')
  assert hasattr(status, 'disk_space_gb')
  assert hasattr(status, 'disk_space_status')
  assert hasattr(status, 'factor_library_entries')
  print('OK: ResourceStatus has all required fields')
  "
  ```

## Observability Impact

- **Signals added/changed:**
  - `ResourceManager.get_status()` — new structured status surface
  - `ResourceManager.check_and_enforce()` — new enforcement gate returning `(allowed, reason)`
  - WARNING-level logs when disk space below threshold
  - INFO-level logs when cleanup runs
- **How a future agent inspects this:**
  - `python -c "from quantaalpha.pipeline.resource_manager import ResourceManager; print(ResourceManager().get_status())"`
  - `~/.cache/quantaalpha/daily_tokens.json` contains daily token persistence
- **Failure state exposed:**
  - When budget exceeded: `check_and_enforce()` returns `(False, "Daily token budget exceeded: X / Y")`
  - When disk critical: `disk_space_status="critical"` in status
  - When ProviderPool unavailable: graceful `None` handling with `within_budget=None`

## Inputs

- `third_party/quantaalpha/quantaalpha/llm/provider_pool.py` — Reference for lazy import pattern
- `third_party/quantaalpha/quantaalpha/factors/library.py` — Reference for FactorLibraryManager API
- `third_party/quantaalpha/configs/experiment.yaml` — Reference for config structure

## Expected Output

- `third_party/quantaalpha/quantaalpha/pipeline/resource_manager.py` — Core ResourceManager class implementation
