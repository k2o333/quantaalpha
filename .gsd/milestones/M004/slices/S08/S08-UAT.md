---
id: S08-UAT
parent: S08
milestone: M004
status: ready_for_review
---

# S08 UAT: 24H 调度中心设计

**Test Type:** Design Review + Interface Verification  
**Preconditions:** Python 3.12+, quantaalpha module available

## Verification Checklist

### 1. Module Structure

**Preconditions:**
- `third_party/quantaalpha/quantaalpha/continuous/` directory exists

**Steps:**
1. Verify `__init__.py` exists and exports required symbols
2. Verify `orchestrator.py` contains `MiningOrchestrator` class
3. Verify `scheduler.py` contains all interface definitions
4. Verify `implementations.py` contains default implementations
5. Verify `DESIGN.md` exists with architecture documentation

**Expected Outcomes:**
- All 4 Python files exist
- `__init__.py` has correct exports

### 2. Interface Verification

**Preconditions:**
- Module can be imported

**Steps:**
```bash
cd third_party/quantaalpha
python -c "
from quantaalpha.continuous import (
    MiningOrchestrator,
    SchedulerConfig,
    SchedulerEvent,
    SchedulerContext,
    RevalidationResult,
    MiningResult,
    DataMonitorTrigger,
    RevalidationScheduler,
    MiningScheduler,
)
print('All interfaces importable')
"
```

**Expected Outcomes:**
- No ImportError
- All classes/funcs imported successfully

### 3. Orchestrator Lifecycle

**Preconditions:**
- Module imports work

**Steps:**
```bash
cd third_party/quantaalpha
python -c "
from quantaalpha.continuous import MiningOrchestrator, SchedulerConfig

# Test default instantiation
orch = MiningOrchestrator()
print(f'Status: {orch.get_status()}')

# Test custom config
config = SchedulerConfig(
    revalidation_interval_hours=24,
    mining_interval_hours=12,
)
orch2 = MiningOrchestrator(config)
print(f'Revalidation interval: {orch2.config.revalidation_interval_hours}h')
print(f'Mining interval: {orch2.config.mining_interval_hours}h')

# Test health report
health = orch2.get_health_report()
print(f'Health status: {health[\"status\"]}')
"
```

**Expected Outcomes:**
- Status: stopped (before start)
- Revalidation interval: 24h
- Mining interval: 12h
- Health status: stopped

### 4. Default Implementations

**Preconditions:**
- Module imports work

**Steps:**
```bash
cd third_party/quantaalpha
python -c "
from quantaalpha.continuous.implementations import (
    DefaultDataMonitor,
    DefaultRevalidationScheduler,
    DefaultMiningScheduler,
)

# Test data monitor
dm = DefaultDataMonitor(check_interval=60)
print(f'DataMonitor interval: {dm.check_interval}s')

# Test revalidation scheduler
rs = DefaultRevalidationScheduler(days_threshold=7, max_per_run=5)
print(f'Revalidation days: {rs.days_threshold}')

# Test mining scheduler
ms = DefaultMiningScheduler(max_per_run=3)
print(f'Mining max: {ms.max_per_run}')

print('All default implementations instantiated')
"
```

**Expected Outcomes:**
- All three scheduler types instantiate successfully
- Parameters are correctly set

### 5. Unit Tests

**Preconditions:**
- pytest available (`/root/miniforge3/envs/mining/bin/python -m pytest`)

**Steps:**
```bash
cd third_party/quantaalpha
/root/miniforge3/envs/mining/bin/python -m pytest quantaalpha/tests/test_continuous.py -v
```

**Expected Outcomes:**
- All 28 tests pass
- No errors or warnings

### 6. Design Document Review

**Preconditions:**
- `continuous/DESIGN.md` exists

**Steps:**
1. Open `continuous/DESIGN.md`
2. Verify it covers:
   - Architecture diagram
   - Technology stack decisions
   - Configuration defaults
   - Error handling strategy
   - Next steps

**Expected Outcomes:**
- Document is comprehensive
- Decisions are justified

## Test Cases

### TC-01: Module Import
```python
from quantaalpha.continuous import MiningOrchestrator
assert MiningOrchestrator is not None
```

### TC-02: Config Defaults
```python
from quantaalpha.continuous import SchedulerConfig
config = SchedulerConfig()
assert config.revalidation_interval_hours == 24
assert config.mining_interval_hours == 12
assert config.revalidation_days_threshold == 21
```

### TC-03: Orchestrator Status
```python
from quantaalpha.continuous import MiningOrchestrator
orch = MiningOrchestrator()
assert orch.get_status().value == "stopped"
```

### TC-04: Health Report Structure
```python
from quantaalpha.continuous import MiningOrchestrator
orch = MiningOrchestrator()
report = orch.get_health_report()
assert "status" in report
assert "data_monitor" in report
assert "revalidation" in report
assert "mining" in report
```

### TC-05: Disabled Scheduler Returns Error
```python
from quantaalpha.continuous import MiningOrchestrator, SchedulerConfig
config = SchedulerConfig(enable_revalidation=False)
orch = MiningOrchestrator(config)
result = orch.run_revalidation_cycle()
assert "not enabled" in result.errors[0]
```

### TC-06: Scheduler Next Run Time
```python
from quantaalpha.continuous.implementations import DefaultRevalidationScheduler
scheduler = DefaultRevalidationScheduler(interval_hours=6)
scheduler.start()
try:
    next_run = scheduler.get_next_scheduled_run()
    assert next_run is not None
finally:
    scheduler.stop()
```

### TC-07: Event Types
```python
from quantaalpha.continuous import SchedulerEvent
assert SchedulerEvent.DATA_UPDATE.value == "data_update"
assert SchedulerEvent.REVALIDATION_TRIGGER.value == "revalidation_trigger"
assert SchedulerEvent.MINING_TRIGGER.value == "mining_trigger"
```

### TC-08: Result Dataclasses
```python
from quantaalpha.continuous import RevalidationResult, MiningResult
rev_result = RevalidationResult(total_candidates=10, revalidated_count=8)
assert rev_result.total_candidates == 10
assert rev_result.revalidated_count == 8

mining_result = MiningResult(factors_generated=5, factors_added=3)
assert mining_result.factors_generated == 5
assert mining_result.factors_added == 3
```

## Edge Cases

### EC-01: Empty Data Dirs
```python
from quantaalpha.continuous.implementations import DefaultDataMonitor
monitor = DefaultDataMonitor()
events = monitor.check_for_updates()
assert events == []
```

### EC-02: No Schedulers Enabled
```python
from quantaalpha.continuous import MiningOrchestrator, SchedulerConfig
config = SchedulerConfig(
    enable_data_monitor=False,
    enable_revalidation=False,
    enable_mining=False,
)
orch = MiningOrchestrator(config)
events = orch.check_data_updates()
assert events == []
```

### EC-03: Invalid Scheduler State
```python
from quantaalpha.continuous.orchestrator import OrchestratorStatus
# Default state should be STOPPED
assert OrchestratorStatus.STOPPED.value == "stopped"
```

## Acceptance Criteria

1. ✅ All Python files compile without errors
2. ✅ All 28 unit tests pass
3. ✅ `MiningOrchestrator` instantiates with default config
4. ✅ Health report returns valid structure
5. ✅ Design document exists and is comprehensive
6. ✅ Disabled schedulers return appropriate error messages
7. ✅ Scheduler interfaces are ABC-based for extensibility

## Sign-off

- [ ] Module structure verified
- [ ] Interfaces tested
- [ ] Unit tests passed
- [ ] Design document reviewed
- [ ] Edge cases handled
