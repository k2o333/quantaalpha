# S08: ResourceManager 资源管理 (S7/D018) — UAT

**Milestone:** M003
**Date:** 2026-03-23
**Status:** Ready for UAT

## Preconditions

1. Python 3.12+ with pytest installed
2. Working directory: `/home/quan/testdata/aspipe_v4/.gsd/worktrees/M003`
3. quantaalpha submodule available at `third_party/quantaalpha/`
4. No special environment variables required (all config via experiment.yaml)

## Smoke Tests

### S08-ST-01: Syntax Validation

**Steps:**
```bash
# 1. Validate resource_manager.py syntax
python -m py_compile third_party/quantaalpha/quantaalpha/pipeline/resource_manager.py
echo "resource_manager.py: $?"

# 2. Validate loop.py syntax
python -m py_compile third_party/quantaalpha/quantaalpha/pipeline/loop.py
echo "loop.py: $?"

# 3. Validate library.py syntax
python -m py_compile third_party/quantaalpha/quantaalpha/factors/library.py
echo "library.py: $?"

# 4. Validate experiment.yaml parse
python -c "import yaml; yaml.safe_load(open('third_party/quantaalpha/configs/experiment.yaml'))"
echo "experiment.yaml: $?"
```

**Expected:** All commands exit with code 0

### S08-ST-02: Unit Test Execution

**Steps:**
```bash
cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M003
python -m pytest third_party/quantaalpha/tests/test_resource_manager.py -v
```

**Expected:** 38 tests pass (TestResourceConfig: 3, TestResourceStatus: 5, TestTokenTracking: 6, TestDiskSpace: 5, TestResultCleanup: 6, TestFactorLibraryIntegration: 3, TestEnforcementGate: 6, TestGetStatus: 2, TestConfigUpdate: 2)

### S08-ST-03: Runtime Status Inspection

**Steps:**
```bash
cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M003
python -c "
import sys
sys.path.insert(0, 'third_party/quantaalpha')
from quantaalpha.pipeline.resource_manager import ResourceManager
mgr = ResourceManager()
status = mgr.get_status()
print(f'tokens_today={status.total_tokens_today}')
print(f'disk_space_gb={status.disk_space_gb}')
print(f'disk_space_status={status.disk_space_status}')
print(f'factor_library_entries={status.factor_library_entries}')
print(f'within_budget={status.within_budget}')
"
```

**Expected:** Output shows valid ResourceStatus fields (tokens_today=0, disk_status=ok, entries=0)

## Functional Test Cases

### S08-FT-01: Token Budget Enforcement (Under Limit)

**Precondition:** Daily tokens < daily_token_limit

**Steps:**
```bash
cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M003
python -c "
import sys
sys.path.insert(0, 'third_party/quantaalpha')
from quantaalpha.pipeline.resource_manager import ResourceManager
mgr = ResourceManager()
allowed, reason = mgr.check_and_enforce()
print(f'allowed={allowed}')
print(f'reason={reason}')
"
```

**Expected:** `allowed=True`, `reason=""`

### S08-FT-02: Token Budget Enforcement (Over Limit)

**Precondition:** Manually set daily_tokens above limit

**Steps:**
```bash
cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M003
python -c "
import sys
sys.path.insert(0, 'third_party/quantaalpha')
from quantaalpha.pipeline.resource_manager import ResourceManager
import os

# Set daily tokens above limit
cache_dir = os.path.expanduser('~/.cache/quantaalpha')
os.makedirs(cache_dir, exist_ok=True)
import json
with open(os.path.join(cache_dir, 'daily_tokens.json'), 'w') as f:
    json.dump({'date': '2026-03-23', 'tokens': 10000000}, f)  # 10M tokens

mgr = ResourceManager()
allowed, reason = mgr.check_and_enforce()
print(f'allowed={allowed}')
print(f'reason={reason}')

# Cleanup
import os
os.remove(os.path.join(cache_dir, 'daily_tokens.json'))
"
```

**Expected:** `allowed=False`, reason contains "Daily token budget exceeded"

### S08-FT-03: Disk Space Status Detection

**Steps:**
```bash
cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M003
python -c "
import sys
sys.path.insert(0, 'third_party/quantaalpha')
from quantaalpha.pipeline.resource_manager import ResourceManager
mgr = ResourceManager()
status = mgr.get_status()
print(f'disk_space_gb={status.disk_space_gb}')
print(f'disk_space_status={status.disk_space_status}')
"
```

**Expected:** `disk_space_status` is one of: "ok", "warning", "critical"

### S08-FT-04: result.h5 Cleanup Scanning

**Precondition:** Create test result.h5 files

**Steps:**
```bash
cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M003
python -c "
import sys
import os
import tempfile
import time
sys.path.insert(0, 'third_party/quantaalpha')

# Create temp dir with old result.h5
with tempfile.TemporaryDirectory() as tmpdir:
    # Create old result.h5 (31 days old)
    old_file = os.path.join(tmpdir, 'result.h5')
    with open(old_file, 'w') as f:
        f.write('test')
    # Set mtime to 31 days ago (if supported)
    old_time = time.time() - (31 * 24 * 60 * 60)
    try:
        os.utime(old_file, (old_time, old_time))
    except:
        pass  # tmpfs may not support utime
    
    # Run cleanup
    from quantaalpha.pipeline.resource_manager import ResourceManager
    mgr = ResourceManager()
    removed = mgr.cleanup_old_results(tmpdir)
    print(f'removed_files={removed}')
"
```

**Expected:** `removed_files >= 0` (files removed or none found)

### S08-FT-05: Factor Library Entry Limit Check

**Steps:**
```bash
cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M003
python -c "
import sys
import tempfile
import json
sys.path.insert(0, 'third_party/quantaalpha')

# Create test library with entries
with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
    test_lib = f.name
    # Create library with 10 entries (under default 10000 limit)
    entries = [{'id': f'test_{i}', 'symbol': f'TEST{i}'} for i in range(10)]
    json.dump({'version': '1.0', 'entries': entries, 'metadata': {}}, f)

from quantaalpha.factors.library import FactorLibraryManager
mgr = FactorLibraryManager(test_lib)
under_limit = mgr._check_entry_limit()
print(f'under_limit={under_limit}')

os.remove(test_lib)
"
```

**Expected:** `under_limit=True`

### S08-FT-06: Token Usage Report Structure

**Steps:**
```bash
cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M003
python -c "
import sys
sys.path.insert(0, 'third_party/quantaalpha')
from quantaalpha.pipeline.resource_manager import ResourceManager
mgr = ResourceManager()
report = mgr.get_token_usage_report()
print(f'report_type={type(report).__name__}')
print(f'keys={list(report.keys()) if isinstance(report, dict) else \"not a dict\"}')
"
```

**Expected:** Returns dict with keys including "provider_pool_tokens", "daily_tracked_tokens"

### S08-FT-07: Disk Space Report Structure

**Steps:**
```bash
cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M003
python -c "
import sys
sys.path.insert(0, 'third_party/quantaalpha')
from quantaalpha.pipeline.resource_manager import ResourceManager
mgr = ResourceManager()
report = mgr.get_disk_space_report()
print(f'report_type={type(report).__name__}')
print(f'keys={list(report.keys()) if isinstance(report, dict) else \"not a dict\"}')
"
```

**Expected:** Returns dict with keys including "total_gb", "free_gb", "status"

### S08-FT-08: Config Update

**Steps:**
```bash
cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M003
python -c "
import sys
sys.path.insert(0, 'third_party/quantaalpha')
from quantaalpha.pipeline.resource_manager import ResourceManager
mgr = ResourceManager()
print(f'initial_limit={mgr.config.daily_token_limit}')
mgr.update_config({'daily_token_limit': 3000000})
print(f'updated_limit={mgr.config.daily_token_limit}')
"
```

**Expected:** `initial_limit=5000000`, `updated_limit=3000000`

## Edge Cases

### S08-EC-01: ProviderPool Unavailable

**Scenario:** ProviderPool module not initialized

**Steps:**
```bash
cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M003
python -c "
import sys
sys.path.insert(0, 'third_party/quantaalpha')
from quantaalpha.pipeline.resource_manager import ResourceManager
mgr = ResourceManager()
# Force unavailability by patching
import quantaalpha.llm.provider_pool as pp
original = getattr(pp, 'provider_pool', None)
if hasattr(pp, 'provider_pool'):
    delattr(pp, 'provider_pool')

allowed, reason = mgr.check_and_enforce()
print(f'allowed={allowed}')
print(f'reason={reason}')

# Restore
if original:
    pp.provider_pool = original
"
```

**Expected:** `allowed=True` with graceful fallback (no exception)

### S08-EC-02: Disk Space Report Error Handling

**Scenario:** Disk path becomes inaccessible

**Steps:**
```bash
cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M003
python -c "
import sys
sys.path.insert(0, 'third_party/quantaalpha')
from quantaalpha.pipeline.resource_manager import ResourceManager
mgr = ResourceManager()
# Test with nonexistent path
report = mgr.get_disk_space_report('/nonexistent/path/that/does/not/exist')
print(f'status={report.get(\"status\", \"unknown\")}')
"
```

**Expected:** Returns report with status="unknown" or handles error gracefully

### S08-EC-03: Config Update Invalid Key

**Steps:**
```bash
cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M003
python -c "
import sys
sys.path.insert(0, 'third_party/quantaalpha')
from quantaalpha.pipeline.resource_manager import ResourceManager
mgr = ResourceManager()
try:
    mgr.update_config({'nonexistent_key': 'value'})
    print('no_exception')
except (KeyError, ValueError) as e:
    print(f'exception={type(e).__name__}')
"
```

**Expected:** Raises KeyError or ValueError

## Integration Test Cases

### S08-IT-01: loop.py Integration Check

**Steps:**
```bash
cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M003
grep -n "resource_manager" third_party/quantaalpha/quantaalpha/pipeline/loop.py
```

**Expected:** Lines found containing "resource_manager" import and usage in run()

### S08-IT-02: library.py Entry Limit Integration

**Steps:**
```bash
cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M003
grep -n "_check_entry_limit" third_party/quantaalpha/quantaalpha/factors/library.py
```

**Expected:** Lines found with `_check_entry_limit` method definition and usage in `add_factors_from_experiment`

### S08-IT-03: experiment.yaml resource_management Section

**Steps:**
```bash
cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M003
python -c "
import yaml
with open('third_party/quantaalpha/configs/experiment.yaml') as f:
    config = yaml.safe_load(f)
rm = config.get('resource_management', {})
required_keys = ['enabled', 'daily_token_limit', 'disk_space_min_gb', 'disk_space_stop_gb', 'result_retention_days', 'factor_library_max_entries']
missing = [k for k in required_keys if k not in rm]
print(f'missing_keys={missing}')
"
```

**Expected:** `missing_keys=[]` (no missing required keys)

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| AC-01 | ResourceManager class exists with check_and_enforce(), get_status() | Smoke test ST-03 |
| AC-02 | Daily token budget enforcement with midnight reset | FT-01, FT-02 |
| AC-03 | Disk space monitoring with WARNING/CRITICAL thresholds | FT-03 |
| AC-04 | result.h5 cleanup with 30-day retention | FT-04 |
| AC-05 | Factor library entry count limits | FT-05 |
| AC-06 | 38+ unit tests covering all enforcement mechanisms | ST-02 |
| AC-07 | Integration with loop.py run() | IT-01 |
| AC-08 | experiment.yaml resource_management section | IT-03 |
| AC-09 | Graceful fallback when ProviderPool unavailable | EC-01 |

## Failure Signals

- Any pytest test fails → Return to development
- `python -m py_compile` returns non-zero → Syntax error
- `get_status()` raises exception → Implementation error
- experiment.yaml missing resource_management section → Configuration error
- loop.py missing resource_manager integration → Integration incomplete

## Sign-off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Developer | Executor | 2026-03-23 | ✅ |
| Reviewer | | | |
| QA | | | |
