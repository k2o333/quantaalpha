"""
Continuous Orchestration Module

Provides 24H autonomous scheduling for:
- Data monitoring (app4 data updates)
- Factor revalidation ("温故")
- Factor mining ("知新")
"""

from .orchestrator import MiningOrchestrator
from .scheduler import (
    DataMonitorTrigger,
    RevalidationScheduler,
    MiningScheduler,
    SchedulerConfig,
    SchedulerEvent,
    SchedulerContext,
    RevalidationResult,
    MiningResult,
)
from .run_store import RunStore, RunSummary
from .main import ContinuousOrchestrator, start, once

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
