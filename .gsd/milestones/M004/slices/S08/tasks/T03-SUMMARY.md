---
id: T03
parent: S08
milestone: M004
status: completed
verification_result: passed
completed_at: 2026-03-24
blocker_discovered: false
observability_surfaces:
  - "quantaalpha/continuous/scheduler.py:DataMonitorTrigger"
  - "quantaalpha/continuous/scheduler.py:RevalidationScheduler"
  - "quantaalpha/continuous/scheduler.py:MiningScheduler"
  - "quantaalpha/continuous/scheduler.py:SchedulerContext"
---

# T03: 模块间接口契约定义

**Status:** Completed

## What was done

Defined clean interfaces for all scheduler types and data structures.

### Interface Hierarchy

```
ABC (Abstract Base Classes)
├── DataMonitorTrigger
│   ├── start()
│   ├── stop()
│   ├── check_for_updates() → List[SchedulerContext]
│   └── get_last_check_time() → Optional[datetime]
│
├── RevalidationScheduler
│   ├── start()
│   ├── stop()
│   ├── run_revalidation() → RevalidationResult
│   └── get_next_scheduled_run() → Optional[datetime]
│
└── MiningScheduler
    ├── start()
    ├── stop()
    ├── run_mining() → MiningResult
    └── get_next_scheduled_run() → Optional[datetime]
```

### Data Classes

| Class | Purpose |
|-------|---------|
| `SchedulerConfig` | Configuration for all schedulers |
| `SchedulerContext` | Event context with payload |
| `SchedulerEvent` | Event type enum |
| `RevalidationResult` | Result of revalidation cycle |
| `MiningResult` | Result of mining cycle |

### Integration Points

| Integration | Location | Purpose |
|-------------|----------|---------|
| `FactorLibraryManager` | `DefaultRevalidationScheduler` | Query candidates, apply results |
| `query_active_factors_RAG()` | `DefaultMiningScheduler` | Get context for mining |
| `ProviderPool` | `DefaultMiningScheduler` | LLM requests (future) |

## Diagnostics

```bash
# Verify all interfaces importable
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

## Verification Evidence

| Check | Command | Exit | Result |
|-------|---------|------|--------|
| Interface imports | `python -c "from quantaalpha.continuous import *"` | 0 | PASS |
| ABC definitions | `python -c "from quantaalpha.continuous.scheduler import DataMonitorTrigger"` | 0 | PASS |
| py_compile | `python -m py_compile continuous/scheduler.py` | 0 | PASS |
| py_compile | `python -m py_compile continuous/orchestrator.py` | 0 | PASS |

## Key Decisions

- **ABC for schedulers**: Allows custom implementations (e.g., inotify-based monitor)
- **Dataclass for results**: Type-safe, immutable results for monitoring
- **Optional datetime**: `None` indicates not scheduled yet
