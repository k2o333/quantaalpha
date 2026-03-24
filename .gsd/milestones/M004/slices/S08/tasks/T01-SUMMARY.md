---
id: T01
parent: S08
milestone: M004
status: completed
verification_result: passed
completed_at: 2026-03-24
blocker_discovered: false
observability_surfaces:
  - "quantaalpha/continuous/orchestrator.py:MiningOrchestrator"
  - "quantaalpha/continuous/implementations.py:DefaultRevalidationScheduler"
  - "quantaalpha/continuous/implementations.py:DefaultMiningScheduler"
  - "quantaalpha/continuous/implementations.py:DefaultDataMonitor"
---

# T01: 三合一调度架构设计

**Status:** Completed

## What was done

Designed and implemented the complete three-in-one orchestration architecture:

### Files created

| File | Description |
|------|-------------|
| `continuous/orchestrator.py` | MiningOrchestrator class with unified lifecycle management |
| `continuous/scheduler.py` | Abstract interfaces for all scheduler types |
| `continuous/implementations.py` | Default implementations for all schedulers |
| `continuous/DESIGN.md` | Complete design documentation |

### Architecture

```
MiningOrchestrator
├── DataMonitorTrigger (数据监控)
│   └── DefaultDataMonitor (文件系统轮询)
├── RevalidationScheduler (温故)
│   └── DefaultRevalidationScheduler (APScheduler)
└── MiningScheduler (知新)
    └── DefaultMiningScheduler (APScheduler)
```

### Key design decisions

1. **Unified orchestrator**: Single entry point managing all three workflows
2. **Lazy initialization**: Schedulers created on demand to avoid import overhead
3. **Event-driven**: Callbacks for external systems to react to scheduler events
4. **Health monitoring**: `get_health_report()` for operational monitoring

## Diagnostics

```bash
# Verify module imports
python -c "from quantaalpha.continuous import MiningOrchestrator"

# Check health report
python -c "
from quantaalpha.continuous import MiningOrchestrator
orch = MiningOrchestrator()
print(orch.get_health_report())
"
```

## Verification Evidence

| Check | Command | Exit | Result |
|-------|---------|------|--------|
| Module compiles | `python -m py_compile continuous/orchestrator.py` | 0 | PASS |
| Import test | `python -c "from quantaalpha.continuous import *"` | 0 | PASS |
| Health report | `python -c "MiningOrchestrator().get_health_report()"` | 0 | PASS |
| Unit tests | `pytest tests/test_continuous.py -v` | 0 | 28 passed |

## Key Decisions

- **APScheduler for scheduling**: Lightweight, no external dependencies, sufficient for single-machine deployment
- **Polling for data monitoring**: Simple and reliable, can upgrade to inotify later
- **Singleton pattern for orchestrator**: One orchestrator instance per process
