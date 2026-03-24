# T02: Add experiment.yaml config and factor library integration

**Slice:** S08 — ResourceManager 资源管理 (S7/D018)
**Milestone:** M003

## Description

Add the `resource_management` configuration section to `experiment.yaml` and integrate entry count checking into `library.py`. This task wires the configuration layer and the factor library layer to ResourceManager.

## Steps

1. **Add `resource_management` section to `experiment.yaml`**:
   - Find the end of the file (before `# ============================================================`)
   - Insert a new section following the existing `llm.provider_pool` pattern
   ```yaml
   # ============================================================
   # RESOURCE MANAGEMENT CONFIGURATION (D018)
   # Controls token budget, disk space, and cleanup policies
   # ============================================================
   resource_management:
     enabled: true
     
     # Token budget (daily hard cap)
     daily_token_limit: 5000000        # 5M tokens
     token_budget_check_interval: 1    # check every loop
     daily_token_reset_hour: 0          # midnight UTC
     
     # Disk space monitoring
     disk_space_min_gb: 5.0            # WARNING threshold
     disk_space_stop_gb: 2.0           # HARD STOP threshold
     
     # result.h5 auto-cleanup
     result_cleanup_enabled: true
     result_retention_days: 30         # keep 30 days
     result_cleanup_max_files: 1000    # guard against corruption
     
     # Factor library limits
     factor_library_max_entries: 10000
     sqlite_migration_threshold: 50000
   ```

2. **Validate YAML structure**:
   ```bash
   python -c "import yaml; cfg = yaml.safe_load(open('third_party/quantaalpha/configs/experiment.yaml')); assert 'resource_management' in cfg; print('OK: resource_management section present')"
   ```

3. **Modify `library.py` to integrate with ResourceManager**:
   - Add `_check_entry_limit()` method to `FactorLibraryManager`:
     - Load `factor_library_max_entries` from experiment.yaml
     - Count current entries
     - If at or above limit, log WARNING and return False
   - Call `_check_entry_limit()` in `add_factors_from_experiment()` before adding new factors
   - If limit exceeded, log warning and skip adding factors (don't crash)

4. **Validate library.py syntax**:
   ```bash
   python -m py_compile third_party/quantaalpha/quantaalpha/factors/library.py
   ```

## Must-Haves

- [ ] `resource_management:` section in `experiment.yaml` with all D018 parameters
- [ ] YAML parses successfully with `yaml.safe_load()`
- [ ] `FactorLibraryManager` has `_check_entry_limit()` method
- [ ] `add_factors_from_experiment()` calls `_check_entry_limit()` before adding
- [ ] Limit exceeded logs WARNING, does not crash

## Verification

- YAML structure validation:
  ```bash
  python -c "
  import yaml
  cfg = yaml.safe_load(open('third_party/quantaalpha/configs/experiment.yaml'))
  rm = cfg.get('resource_management', {})
  assert rm.get('enabled') == True
  assert rm.get('daily_token_limit') == 5000000
  assert rm.get('disk_space_min_gb') == 5.0
  assert rm.get('result_retention_days') == 30
  assert rm.get('factor_library_max_entries') == 10000
  print('OK: All resource_management fields present')
  "
  ```
- Syntax validation:
  ```bash
  python -m py_compile third_party/quantaalpha/quantaalpha/factors/library.py
  ```

## Observability Impact

- **Signals added/changed:**
  - WARNING log when factor library entry limit reached
- **How a future agent inspects this:**
  - Check `experiment.yaml` for `resource_management` section
  - Check library.py for `_check_entry_limit()` method
- **Failure state exposed:**
  - When entry limit exceeded: WARNING log, factors not added

## Inputs

- `third_party/quantaalpha/configs/experiment.yaml` — Add section here
- `third_party/quantaalpha/quantaalpha/factors/library.py` — Modify here
- `third_party/quantaalpha/quantaalpha/pipeline/resource_manager.py` — Read ResourceConfig defaults

## Expected Output

- `third_party/quantaalpha/configs/experiment.yaml` — Modified with resource_management section
- `third_party/quantaalpha/quantaalpha/factors/library.py` — Modified with entry limit check
