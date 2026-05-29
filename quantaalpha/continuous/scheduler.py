"""Scheduling interfaces for the 24H orchestration center.

Defines the contract for three scheduler types:
- DataMonitorTrigger: Monitors app4 data updates
- RevalidationScheduler: Handles periodic factor revalidation ("温故")
- MiningScheduler: Triggers new factor mining ("知新")
"""
# ruff: noqa: D101, D102

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from quantaalpha.continuous.artifact_policy import ArtifactPolicyConfig
from quantaalpha.continuous.workspace_retention import WorkspaceRetentionConfig
from quantaalpha.factor_ops.performance_history import PerformanceHistoryConfig


class SchedulerEvent(str, Enum):
    """Events emitted by schedulers."""

    DATA_UPDATE = "data_update"  # New data detected
    REVALIDATION_TRIGGER = "revalidation_trigger"  # Time to revalidate
    MINING_TRIGGER = "mining_trigger"  # Time to mine new factors
    STATUS_CHANGE = "status_change"  # Factor status changed


from quantaalpha.continuous.scheduler_config import (
    AgentLoopConfig,
    App4BridgeConfig,
    CircuitBreakerConfig,
    DirectionPlannerConfig,
    EnsembleConfig,
    EscalationConfig,
    EvolutionConfig,
    ExecutionConfig,
    ExecutionPeriod,
    FactorConfig,
    LLMEmbeddingConfig,
    LLMRetryConfig,
    LLMRuntimeConfig,
    MiningConfig,
    ModelConfig,
    OrchestrationConditionConfig,
    OrchestrationConfig,
    OrchestrationMetricsConfig,
    OrchestrationNodeConfig,
    OrchestrationTransitionConfig,
    ParquetCompactConfig,
    PipelineConfig,
    ProviderEntryConfig,
    ProviderPoolConfig,
    QualityGateConfig,
    StatePersistenceConfig,
    TrainingConfig,
    ValidationConfig,
)


@dataclass
class SchedulerConfig:
    """Configuration for all schedulers."""

    # Data monitoring
    data_check_interval_seconds: int = 300  # 5 minutes
    data_dirs: list[str] = field(default_factory=list)

    # Revalidation
    revalidation_interval_hours: int = 24  # Daily revalidation check
    revalidation_days_threshold: int = 21  # Revalidate if not validated in N days
    max_revalidation_per_run: int = 10

    # Mining
    mining_interval_hours: int = 12  # Mine new factors every 12 hours
    max_mining_per_run: int = 5

    # Runtime budgets
    cycle_budget_seconds: int = 3600  # 1 hour per cycle
    per_factor_timeout_seconds: int = 300  # 5 minutes per factor

    # Validation thresholds
    min_ic: float = 0.02
    min_rank_ic: float = 0.01

    # Global
    enable_data_monitor: bool = True
    enable_revalidation: bool = True
    enable_mining: bool = True

    # Mining pipeline config
    mining: MiningConfig = field(default_factory=MiningConfig)

    # Factor storage config
    factor: FactorConfig = field(default_factory=FactorConfig)
    workspace_retention: WorkspaceRetentionConfig = field(default_factory=WorkspaceRetentionConfig)
    artifact_policy: ArtifactPolicyConfig = field(default_factory=ArtifactPolicyConfig)
    continuous_lock_dir: str = "log/continuous/locks"

    @classmethod
    def from_pipeline_config(cls, pipeline_config: PipelineConfig) -> "SchedulerConfig":
        """Create SchedulerConfig from a PipelineConfig.

        Args:
            pipeline_config: Full pipeline configuration.

        Returns:
            SchedulerConfig instance.
        """
        return cls(
            data_check_interval_seconds=pipeline_config.data_check_interval_seconds,
            data_dirs=pipeline_config.app4_bridge.data_roots,
            revalidation_interval_hours=pipeline_config.revalidation_interval_hours,
            revalidation_days_threshold=pipeline_config.revalidation_days_threshold,
            max_revalidation_per_run=pipeline_config.validation.max_revalidation_per_run,
            mining_interval_hours=pipeline_config.mining_interval_hours,
            max_mining_per_run=pipeline_config.validation.max_mining_per_run,
            cycle_budget_seconds=pipeline_config.cycle_budget_seconds,
            per_factor_timeout_seconds=pipeline_config.per_factor_timeout_seconds,
            min_ic=pipeline_config.validation.min_ic,
            min_rank_ic=pipeline_config.validation.min_rank_ic,
            enable_data_monitor=pipeline_config.enable_data_monitor,
            enable_revalidation=pipeline_config.enable_revalidation,
            enable_mining=pipeline_config.enable_mining,
            mining=pipeline_config.mining,
            factor=pipeline_config.factor,
            workspace_retention=pipeline_config.workspace_retention,
            artifact_policy=pipeline_config.artifact_policy,
            continuous_lock_dir=getattr(pipeline_config, "continuous_lock_dir", "log/continuous/locks"),
        )


@dataclass
class SchedulerContext:
    """Context passed to scheduler callbacks."""

    event: SchedulerEvent
    timestamp: datetime = field(default_factory=datetime.now)
    payload: dict[str, Any] = field(default_factory=dict)

    # Source information
    source_module: str = ""
    factor_ids: list[str] = field(default_factory=list)


class DataMonitorTrigger(ABC):
    """Monitors data directory for updates.

    Implementations should:
    1. Watch configured directories for new/modified Parquet files
    2. Emit DATA_UPDATE events when changes are detected
    3. Track last-check timestamps to avoid duplicate triggers
    """

    @abstractmethod
    def start(self) -> None:
        """Start monitoring data directories."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop monitoring."""
        ...

    @abstractmethod
    def check_for_updates(self) -> list[SchedulerContext]:
        """Check for data updates and return list of events.

        Returns:
            List of SchedulerContext with DATA_UPDATE events for each detected change.
        """
        ...

    @abstractmethod
    def get_last_check_time(self) -> Optional[datetime]:
        """Get timestamp of last check."""
        ...


class RevalidationScheduler(ABC):
    """Schedules periodic factor revalidation.

    Implementations should:
    1. Query factor library for candidates needing revalidation
    2. Trigger backtest for each candidate
    3. Update factor status based on results
    """

    @abstractmethod
    def start(self) -> None:
        """Start the revalidation scheduler."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop the scheduler."""
        ...

    @abstractmethod
    def run_revalidation(self) -> RevalidationResult:
        """Run one revalidation cycle.

        Returns:
            RevalidationResult with statistics.
        """
        ...

    @abstractmethod
    def get_next_scheduled_run(self) -> Optional[datetime]:
        """Get next scheduled run time."""
        ...


@dataclass
class RevalidationResult:
    """Result of a revalidation cycle."""

    total_candidates: int = 0
    revalidated_count: int = 0
    status_changes: dict[str, str] = field(default_factory=dict)  # factor_id -> new_status
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    governance_events: list[dict[str, Any]] = field(default_factory=list)


class MiningScheduler(ABC):
    """Schedules periodic new factor mining.

    Implementations should:
    1. Trigger RAG retrieval for context
    2. Invoke LLM to generate new factors
    3. Run backtest validation
    4. Add successful factors to library
    """

    @abstractmethod
    def start(self) -> None:
        """Start the mining scheduler."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop the scheduler."""
        ...

    @abstractmethod
    def run_mining(self) -> MiningResult:
        """Run one mining cycle.

        Returns:
            MiningResult with statistics.
        """
        ...

    @abstractmethod
    def get_next_scheduled_run(self) -> Optional[datetime]:
        """Get next scheduled run time."""
        ...


@dataclass
class MiningResult:
    """Result of a mining cycle."""

    factors_generated: int = 0
    factors_validated: int = 0
    factors_added: int = 0
    factor_ids: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    quality_gate_lifecycle: dict[str, int] = field(default_factory=dict)
    best_metrics: dict[str, Any] = field(default_factory=dict)
    historical_parent_injection_counts: dict[str, dict[str, Any]] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    governance_events: list[dict[str, Any]] = field(default_factory=list)
