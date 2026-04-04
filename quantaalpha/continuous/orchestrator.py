"""
MiningOrchestrator: 24H autonomous scheduling center.

Orchestrates three workflows:
1. Data Monitor ("数据监控"): Watches app4 data updates
2. Revalidation ("温故"): Periodic factor revalidation
3. Mining ("知新"): Periodic new factor generation

The orchestrator manages lifecycle of all schedulers and provides
unified status and error reporting.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from .scheduler import (
    MiningResult,
    RevalidationResult,
    SchedulerConfig,
    SchedulerContext,
    SchedulerEvent,
)

logger = logging.getLogger(__name__)


class OrchestratorStatus(str, Enum):
    """Overall orchestrator status."""

    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class OrchestratorStats:
    """Statistics from orchestrator operations."""

    # Revalidation stats
    total_revalidations: int = 0
    last_revalidation: Optional[datetime] = None
    last_revalidation_result: Optional[RevalidationResult] = None

    # Mining stats
    total_mining_runs: int = 0
    last_mining_run: Optional[datetime] = None
    last_mining_result: Optional[MiningResult] = None

    # Data monitor stats
    total_data_updates_detected: int = 0
    last_data_check: Optional[datetime] = None

    # Error tracking
    error_count: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None


class MiningOrchestrator:
    """
    Main orchestrator for 24H autonomous factor operations.

    Usage:
        config = SchedulerConfig(
            revalidation_interval_hours=24,
            mining_interval_hours=12,
            enable_revalidation=True,
            enable_mining=True,
        )
        orchestrator = MiningOrchestrator(config)
        orchestrator.start()
        # Run indefinitely...
        orchestrator.stop()
    """

    def __init__(
        self,
        config: Optional[SchedulerConfig] = None,
        data_monitor=None,
        revalidation_scheduler=None,
        mining_scheduler=None,
        data_bridge=None,
        execution_periods: Optional[dict] = None,
        library_path: Optional[str] = None,
        monitor_engine=None,
    ):
        """
        Initialize the orchestrator.

        Args:
            config: Scheduler configuration. Uses defaults if not provided.
            data_monitor: DataMonitorTrigger implementation.
            revalidation_scheduler: RevalidationScheduler implementation.
            mining_scheduler: MiningScheduler implementation.
            monitor_engine: Optional FactorMonitorEngine for post-validation monitoring.
        """
        self.config = config or SchedulerConfig()
        self.status = OrchestratorStatus.STOPPED
        self.stats = OrchestratorStats()

        # Scheduler instances (can be injected for testing)
        self._data_monitor = data_monitor
        self._revalidation_scheduler = revalidation_scheduler
        self._mining_scheduler = mining_scheduler
        self._data_bridge = data_bridge
        self._execution_periods = execution_periods or {}
        self._library_path = library_path
        self._monitor_engine = monitor_engine

        # Event callbacks
        self._event_callbacks: list[callable] = []

    @property
    def data_monitor(self):
        """Lazy-load data monitor."""
        if self._data_monitor is None and self.config.enable_data_monitor:
            from .implementations import DefaultDataMonitor

            self._data_monitor = DefaultDataMonitor(
                check_interval=self.config.data_check_interval_seconds,
                data_dirs=self.config.data_dirs,
            )
        return self._data_monitor

    @property
    def revalidation_scheduler(self):
        """Lazy-load revalidation scheduler."""
        if self._revalidation_scheduler is None and self.config.enable_revalidation:
            from .implementations import DefaultRevalidationScheduler

            self._revalidation_scheduler = DefaultRevalidationScheduler(
                days_threshold=self.config.revalidation_days_threshold,
                max_per_run=self.config.max_revalidation_per_run,
                library_path=self._library_path,
                data_bridge=self._data_bridge,
                execution_periods=self._execution_periods,
                min_ic=self.config.min_ic,
                per_factor_timeout_seconds=self.config.per_factor_timeout_seconds,
            )
        return self._revalidation_scheduler

    @property
    def mining_scheduler(self):
        """Lazy-load mining scheduler."""
        if self._mining_scheduler is None and self.config.enable_mining:
            from .implementations import DefaultMiningScheduler

            self._mining_scheduler = DefaultMiningScheduler(
                max_per_run=self.config.max_mining_per_run,
                library_path=self._library_path,
                data_bridge=self._data_bridge,
                execution_periods=self._execution_periods,
                min_ic=self.config.min_ic,
                min_rank_ic=self.config.min_rank_ic,
                per_factor_timeout_seconds=self.config.per_factor_timeout_seconds,
                monitor_engine=self._monitor_engine,
                pipeline_mode=self.config.mining.pipeline_mode,
                quality_gate_config={
                    "min_ic": self.config.mining.quality_gate.min_ic,
                    "min_rank_ic": self.config.mining.quality_gate.min_rank_ic,
                    "max_correlation": self.config.mining.quality_gate.max_correlation,
                    "min_sharpe": self.config.mining.quality_gate.min_sharpe,
                },
                evolution_cfg={
                    "enabled": self.config.mining.evolution.enabled,
                    "max_rounds": self.config.mining.evolution.max_rounds,
                    "mutation_enabled": self.config.mining.evolution.mutation_enabled,
                    "crossover_enabled": self.config.mining.evolution.crossover_enabled,
                    "crossover_size": self.config.mining.evolution.crossover_size,
                    "crossover_n": self.config.mining.evolution.crossover_n,
                    "parallel_enabled": self.config.mining.evolution.parallel_enabled,
                    "fresh_start": self.config.mining.evolution.fresh_start,
                },
                state_cfg={
                    "pool_save_path": self.config.mining.state.pool_save_path,
                    "max_pool_size": self.config.mining.state.max_pool_size,
                    "failure_cooldown_hours": self.config.mining.state.failure_cooldown_hours,
                    "steps_per_mining": self.config.mining.steps_per_mining,
                    "log_root": self.config.mining.log_root,
                },
            )
        return self._mining_scheduler

    def start(self) -> None:
        """Start all enabled schedulers."""
        if self.status == OrchestratorStatus.RUNNING:
            logger.warning("Orchestrator already running")
            return

        logger.info("Starting MiningOrchestrator")

        try:
            if self.config.enable_data_monitor and self.data_monitor:
                self.data_monitor.start()
                logger.info("Data monitor started")

            if self.config.enable_revalidation and self.revalidation_scheduler:
                self.revalidation_scheduler.start()
                logger.info("Revalidation scheduler started")

            if self.config.enable_mining and self.mining_scheduler:
                self.mining_scheduler.start()
                logger.info("Mining scheduler started")

            self.status = OrchestratorStatus.RUNNING
            logger.info("MiningOrchestrator started successfully")

        except Exception as e:
            self.status = OrchestratorStatus.ERROR
            self._record_error(f"Failed to start orchestrator: {e}")
            raise

    def stop(self) -> None:
        """Stop all schedulers gracefully."""
        logger.info("Stopping MiningOrchestrator")

        if self.data_monitor:
            try:
                self.data_monitor.stop()
            except Exception as e:
                logger.error(f"Error stopping data monitor: {e}")

        if self.revalidation_scheduler:
            try:
                self.revalidation_scheduler.stop()
            except Exception as e:
                logger.error(f"Error stopping revalidation scheduler: {e}")

        if self.mining_scheduler:
            try:
                self.mining_scheduler.stop()
            except Exception as e:
                logger.error(f"Error stopping mining scheduler: {e}")

        self.status = OrchestratorStatus.STOPPED
        logger.info("MiningOrchestrator stopped")

    def run_revalidation_cycle(self, candidates: list = None) -> RevalidationResult:
        """
        Manually trigger a revalidation cycle.

        Args:
            candidates: Optional list of pre-selected factor candidates.
                      If provided, these are used instead of querying the library.

        Returns:
            Result of the revalidation run.
        """
        if not self.revalidation_scheduler:
            return RevalidationResult(errors=["Revalidation scheduler not enabled"])

        logger.info("Running manual revalidation cycle")
        result = self.revalidation_scheduler.run_revalidation(candidates=candidates)

        self.stats.total_revalidations += 1
        self.stats.last_revalidation = datetime.now()
        self.stats.last_revalidation_result = result

        if result.errors:
            self.stats.error_count += len(result.errors)

        return result

    def run_mining_cycle(self) -> MiningResult:
        """
        Manually trigger a mining cycle.

        Returns:
            Result of the mining run.
        """
        if not self.mining_scheduler:
            return MiningResult(errors=["Mining scheduler not enabled"])

        logger.info("Running manual mining cycle")
        result = self.mining_scheduler.run_mining()

        self.stats.total_mining_runs += 1
        self.stats.last_mining_run = datetime.now()
        self.stats.last_mining_result = result

        if result.errors:
            self.stats.error_count += len(result.errors)

        return result

    def check_data_updates(self) -> list[SchedulerContext]:
        """
        Check for data updates.

        Returns:
            List of detected data update events.
        """
        if not self.data_monitor:
            return []

        events = self.data_monitor.check_for_updates()
        self.stats.last_data_check = datetime.now()
        self.stats.total_data_updates_detected += len(events)

        for event in events:
            self._emit_event(event)

        return events

    def get_status(self) -> OrchestratorStatus:
        """Get current orchestrator status."""
        return self.status

    def get_stats(self) -> OrchestratorStats:
        """Get orchestrator statistics."""
        return self.stats

    def get_health_report(self) -> dict:
        """
        Get a health report for all subsystems.

        Returns:
            Dict with health status of each component.
        """
        return {
            "status": self.status.value,
            "timestamp": datetime.now().isoformat(),
            "data_monitor": {
                "enabled": self.config.enable_data_monitor,
                "running": self.data_monitor is not None,
                "last_check": (self.stats.last_data_check.isoformat() if self.stats.last_data_check else None),
            },
            "revalidation": {
                "enabled": self.config.enable_revalidation,
                "running": self.revalidation_scheduler is not None,
                "total_runs": self.stats.total_revalidations,
                "last_run": (self.stats.last_revalidation.isoformat() if self.stats.last_revalidation else None),
                "next_run": (self._get_next_run_safe(self.revalidation_scheduler)),
            },
            "mining": {
                "enabled": self.config.enable_mining,
                "running": self.mining_scheduler is not None,
                "total_runs": self.stats.total_mining_runs,
                "last_run": (self.stats.last_mining_run.isoformat() if self.stats.last_mining_run else None),
                "next_run": (self._get_next_run_safe(self.mining_scheduler)),
            },
            "errors": {
                "count": self.stats.error_count,
                "last_error": self.stats.last_error,
                "last_error_time": (self.stats.last_error_time.isoformat() if self.stats.last_error_time else None),
            },
        }

    def on_event(self, callback: callable) -> None:
        """Register an event callback."""
        self._event_callbacks.append(callback)

    def _emit_event(self, context: SchedulerContext) -> None:
        """Emit event to all registered callbacks."""
        for callback in self._event_callbacks:
            try:
                callback(context)
            except Exception as e:
                logger.error(f"Error in event callback: {e}")

    def _get_next_run_safe(self, scheduler) -> Optional[str]:
        """Safely get next run time from scheduler."""
        if scheduler is None:
            return None
        try:
            next_run = scheduler.get_next_scheduled_run()
            return next_run.isoformat() if next_run else None
        except Exception:
            return None

    def _record_error(self, error: str) -> None:
        """Record an error."""
        self.stats.error_count += 1
        self.stats.last_error = error
        self.stats.last_error_time = datetime.now()
        logger.error(f"Orchestrator error: {error}")
