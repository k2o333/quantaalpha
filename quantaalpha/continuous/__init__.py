"""
Continuous Orchestration Module

Provides 24H autonomous scheduling for:
- Data monitoring (app4 data updates)
- Factor revalidation ("温故")
- Factor mining ("知新")
"""

from .orchestrator import MiningOrchestrator
from .run_store import RunStore, RunSummary
from .scheduler import (
    DataMonitorTrigger,
    MiningResult,
    MiningScheduler,
    RevalidationResult,
    RevalidationScheduler,
    SchedulerConfig,
    SchedulerContext,
    SchedulerEvent,
)

__all__ = [
    "MiningOrchestrator",
    "ContinuousOrchestrator",
    "DataMonitorTrigger",
    "RevalidationScheduler",
    "MiningScheduler",
    "SchedulerConfig",
    "SchedulerEvent",
    "SchedulerContext",
    "RevalidationResult",
    "MiningResult",
    "RunStore",
    "RunSummary",
    "start",
    "once",
]


def __getattr__(name: str):
    if name in {"ContinuousOrchestrator", "start", "once"}:
        from .main import ContinuousOrchestrator, once, start

        exports = {
            "ContinuousOrchestrator": ContinuousOrchestrator,
            "start": start,
            "once": once,
        }
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
