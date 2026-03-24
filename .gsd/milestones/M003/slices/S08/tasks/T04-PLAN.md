# T04: Create unit tests and final verification

**Slice:** S08 — ResourceManager 资源管理 (S7/D018)
**Milestone:** M003

## Description

Create comprehensive unit tests for ResourceManager following the S04 ProviderPool test patterns. Tests cover all enforcement mechanisms: token budget, disk space, result cleanup, and factor library limits. This task completes the slice verification.

## Steps

1. **Create `test_resource_manager.py`** in `third_party/quantaalpha/tests/` following S04 patterns:
   - Mock rdagent imports to avoid import chain
   - Use `unittest.mock` for isolation
   - Test all public methods

2. **Implement test classes (20+ tests)**:

   ```python
   class TestResourceConfig:
       def test_defaults(self): # ResourceConfig has correct defaults
       def test_from_dict(self): # from_dict creates correct config
       def test_validation(self): # Invalid values raise ValueError
   
   class TestResourceStatus:
       def test_status_fields(self): # All fields present in snapshot
       def test_status_computation(self): # within_budget computed correctly
   
   class TestTokenTracking:
       def test_daily_reset_same_day(self): # Tokens persist on same day
       def test_daily_reset_new_day(self): # Tokens reset on new day
       def test_budget_enforcement_under(self): # Under budget returns True
       def test_budget_enforcement_over(self): # Over budget returns False
   
   class TestDiskSpace:
       def test_space_ok(self): # Above threshold returns ok
       def test_space_warning(self): # Below min returns warning
       def test_space_critical(self): # Below stop returns critical
   
   class TestResultCleanup:
       def test_cleanup_old_files(self): # Old files removed
       def test_cleanup_preserves_new(self): # New files kept
       def test_cleanup_dry_run(self): # dry_run doesn't delete
       def test_cleanup_max_files(self): # Respects max_files guard
   
   class TestFactorLibraryIntegration:
       def test_entry_count_under_limit(self): # Under limit allows add
       def test_entry_count_at_limit(self): # At limit logs warning
   
   class TestEnforcementGate:
       def test_allowed_under_budget(self): # check_and_enforce allows
       def test_blocked_over_token(self): # Blocked on token budget
       def test_blocked_critical_disk(self): # Blocked on critical disk
       def test_graceful_no_provider_pool(self): # Handles missing pool
   ```

3. **Run tests and verify**:
   ```bash
   cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M003
   python -m pytest third_party/quantaalpha/tests/test_resource_manager.py -v
   ```

4. **Final verification**: Run all slice tests:
   ```bash
   python -m py_compile third_party/quantaalpha/quantaalpha/pipeline/resource_manager.py
   python -m py_compile third_party/quantaalpha/quantaalpha/pipeline/loop.py
   python -m py_compile third_party/quantaalpha/quantaalpha/factors/library.py
   python -m pytest third_party/quantaalpha/tests/test_resource_manager.py -v
   ```

## Must-Haves

- [ ] `test_resource_manager.py` with 20+ tests
- [ ] TestResourceConfig: 3 tests (defaults, from_dict, validation)
- [ ] TestResourceStatus: 2 tests (fields, computation)
- [ ] TestTokenTracking: 4 tests (daily reset, budget enforcement)
- [ ] TestDiskSpace: 3 tests (ok, warning, critical)
- [ ] TestResultCleanup: 4 tests (old files, new files, dry_run, max_files)
- [ ] TestFactorLibraryIntegration: 2 tests (under/at limit)
- [ ] TestEnforcementGate: 4 tests (allowed, blocked token, blocked disk, graceful)
- [ ] All tests pass with pytest

## Verification

- Run full test suite:
  ```bash
  cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M003
  python -m pytest third_party/quantaalpha/tests/test_resource_manager.py -v
  ```
- Verify test count:
  ```bash
  python -m pytest third_party/quantaalpha/tests/test_resource_manager.py --collect-only | grep "test_"
  ```
  Expected: 22+ tests collected

## Observability Impact

- **Signals added/changed:**
  - Tests provide coverage metrics for all ResourceManager methods
  - pytest output shows pass/fail per test class
- **How a future agent inspects this:**
  - Run `pytest tests/test_resource_manager.py` for regression coverage
  - Check test class names for specific feature coverage
- **Failure state exposed:**
  - pytest shows which test failed and why
  - Mock assertions verify correct method calls

## Inputs

- `third_party/quantaalpha/quantaalpha/pipeline/resource_manager.py` — Test all methods
- `third_party/quantaalpha/tests/test_provider_pool.py` — Reference for test patterns
- `third_party/quantaalpha/tests/conftest.py` — Reference for fixtures

## Expected Output

- `third_party/quantaalpha/tests/test_resource_manager.py` — 20+ unit tests
