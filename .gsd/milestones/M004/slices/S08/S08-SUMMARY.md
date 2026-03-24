---
id: S08
milestone: M004
status: completed
completed_at: 2026-03-24
verification_result: passed
observability_surfaces:
  - "quantaalpha/continuous/orchestrator.py:MiningOrchestrator"
  - "quantaalpha/continuous/implementations.py:*Scheduler"
  - "quantaalpha/continuous/scheduler.py:SchedulerConfig"
  - "quantaalpha/continuous/DESIGN.md"
---

# S08 Summary: 24H 调度中心设计

## Purpose

Design the three-in-one autonomous scheduling center for factor operations:
- **Data monitoring**: Watch app4 data updates
- **Revalidation ("温故")**: Periodic factor revalidation
- **Mining ("知新")**: Periodic new factor generation

## What was delivered

### New Files

| File | Description | Lines |
|------|-------------|-------|
| `continuous/__init__.py` | Module exports | 15 |
| `continuous/scheduler.py` | Abstract interfaces | 177 |
| `continuous/orchestrator.py` | Main orchestrator class | 355 |
| `continuous/implementations.py` | Default implementations | 450 |
| `continuous/DESIGN.md` | Design documentation | 250+ |
| `tests/test_continuous.py` | Unit tests (28 cases) | 480 |

### Architecture

```
MiningOrchestrator (统一入口)
├── DataMonitorTrigger (数据监控)
│   └── DefaultDataMonitor (文件系统轮询)
├── RevalidationScheduler (温故)
│   └── DefaultRevalidationScheduler (APScheduler)
└── MiningScheduler (知新)
    └── DefaultMiningScheduler (APScheduler)
```

### Key Interfaces

- `SchedulerConfig`: Configuration dataclass with sensible defaults
- `SchedulerContext`: Event context with payload
- `SchedulerEvent`: DATA_UPDATE, REVALIDATION_TRIGGER, MINING_TRIGGER, STATUS_CHANGE
- `RevalidationResult`: Statistics from revalidation cycles
- `MiningResult`: Statistics from mining cycles

### Technology Stack Decisions

| Category | Decision | Rationale |
|----------|-----------|-----------|
| Task scheduling | APScheduler | Zero dependencies, sufficient for single-machine |
| Process management | Supervisor | Simple config, `supervisorctl` interface |
| Data monitoring | Filesystem polling | Reliable, upgradeable to inotify |
| Vector store | ChromaDB | Already integrated in S06 |
| Configuration | Pydantic | Type safety, validation |

## Verification

- All Python files compile: `✓`
- All 28 unit tests pass: `✓`
- Module imports successfully: `✓`
- Health report generates: `✓`

## Patterns Established

1. **Lazy initialization**: Schedulers created on demand to avoid import overhead
2. **ABC for extensibility**: Custom implementations can replace defaults
3. **Event-driven callbacks**: External systems can subscribe to scheduler events
4. **Health monitoring**: `get_health_report()` for operational visibility

## Dependencies Consumed

| Slice | Dependency | Usage |
|-------|-----------|-------|
| S02 | `select_revalidation_candidates()` | Query revalidation candidates |
| S05 | Status machine | Update factor status after validation |
| S06 | `query_active_factors_RAG()` | Retrieve mining context |

## Key Decisions

1. **APScheduler over Celery**: v1 is single-machine; APScheduler is simpler
2. **Polling over inotify**: Reliable and can be upgraded later
3. **Results as dataclasses**: Type-safe, immutable statistics

## Next Steps (for future implementation)

1. Supervisor configuration file
2. Integration with `FactorLibraryManager`
3. `supervisord.conf` for process management
4. Health check HTTP endpoint

## Known Limitations

- `run_revalidation()` placeholder calls `_run_factor_backtest()` which always returns `True`
- `run_mining()` placeholder calls `_generate_factors()` which returns empty list
- Real backtest and LLM integration pending

## Handoff Notes

Future implementation should:
1. Integrate `run_revalidation()` with actual backtest module
2. Integrate `run_mining()` with actual LLM client
3. Add `supervisord.conf` for process management
4. Consider adding a health check HTTP endpoint
