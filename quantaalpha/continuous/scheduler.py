"""
Scheduling interfaces for the 24H orchestration center.

Defines the contract for three scheduler types:
- DataMonitorTrigger: Monitors app4 data updates
- RevalidationScheduler: Handles periodic factor revalidation ("温故")
- MiningScheduler: Triggers new factor mining ("知新")
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class SchedulerEvent(str, Enum):
    """Events emitted by schedulers."""

    DATA_UPDATE = "data_update"  # New data detected
    REVALIDATION_TRIGGER = "revalidation_trigger"  # Time to revalidate
    MINING_TRIGGER = "mining_trigger"  # Time to mine new factors
    STATUS_CHANGE = "status_change"  # Factor status changed


@dataclass
class App4BridgeConfig:
    """App4 bridge configuration for data monitoring."""

    enabled: bool = True
    interfaces: list[str] = field(default_factory=list)
    data_roots: list[str] = field(default_factory=list)
    freshness_threshold_hours: int = 24
    update_timeout_seconds: int = 120
    max_update_interfaces_per_cycle: int = 5


@dataclass
class FactorConfig:
    """Factor runtime configuration."""

    library_path: str = "third_party/quantaalpha/data/factorlib/all_factors_library.json"
    monitoring_output_path: str = "log/monitoring/"
    backtest_config_path: str = "config/backtest.yaml"


@dataclass
class ValidationConfig:
    """Validation thresholds configuration."""

    min_ic: float = 0.02
    min_rank_ic: float = 0.01
    max_revalidation_per_run: int = 10
    max_mining_per_run: int = 5


@dataclass
class ExecutionPeriod:
    """Single execution period (train/valid/test)."""

    start: str = ""
    end: str = ""


@dataclass
class ExecutionConfig:
    """Execution periods configuration."""

    train: ExecutionPeriod = field(default_factory=ExecutionPeriod)
    valid: ExecutionPeriod = field(default_factory=ExecutionPeriod)
    test: ExecutionPeriod = field(default_factory=ExecutionPeriod)


@dataclass
class PipelineConfig:
    """Full pipeline configuration parsed from pipeline.yaml."""

    # Runtime scheduling
    data_check_interval_seconds: int = 300
    revalidation_interval_hours: int = 24
    revalidation_days_threshold: int = 21
    mining_interval_hours: int = 12

    # App4 bridge
    app4_bridge: App4BridgeConfig = field(default_factory=App4BridgeConfig)

    # Factor runtime
    factor: FactorConfig = field(default_factory=FactorConfig)

    # Validation
    validation: ValidationConfig = field(default_factory=ValidationConfig)

    # Execution periods
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)

    # Global feature flags
    enable_data_monitor: bool = True
    enable_revalidation: bool = True
    enable_mining: bool = True

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "PipelineConfig":
        """
        Load pipeline configuration from a YAML file.

        Args:
            yaml_path: Path to the pipeline.yaml file.

        Returns:
            PipelineConfig instance with parsed values.
        """
        import yaml

        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)

        if data is None:
            return cls()

        # Parse runtime section
        runtime = data.get("runtime", {})
        data_check_interval = runtime.get("data_check_interval_seconds", 300)
        revalidation_interval = runtime.get("revalidation_interval_hours", 24)
        revalidation_days = runtime.get("revalidation_days_threshold", 21)
        mining_interval = runtime.get("mining_interval_hours", 12)

        # Parse app4_bridge section
        app4_data = data.get("app4_bridge", {})
        app4_bridge = App4BridgeConfig(
            enabled=app4_data.get("enabled", True),
            interfaces=app4_data.get("interfaces", []),
            data_roots=app4_data.get("data_roots", []),
            freshness_threshold_hours=app4_data.get("freshness_threshold_hours", 24),
            update_timeout_seconds=app4_data.get("update_timeout_seconds", 120),
            max_update_interfaces_per_cycle=app4_data.get("max_update_interfaces_per_cycle", 5),
        )

        # Parse factor section
        factor_data = data.get("factor", {})
        factor = FactorConfig(
            library_path=factor_data.get("library_path", "third_party/quantaalpha/data/factorlib/all_factors_library.json"),
            monitoring_output_path=factor_data.get("monitoring_output_path", "log/monitoring/"),
            backtest_config_path=factor_data.get("backtest_config_path", "config/backtest.yaml"),
        )

        # Parse validation section
        validation_data = data.get("validation", {})
        validation = ValidationConfig(
            min_ic=validation_data.get("min_ic", 0.02),
            min_rank_ic=validation_data.get("min_rank_ic", 0.01),
            max_revalidation_per_run=validation_data.get("max_revalidation_per_run", 10),
            max_mining_per_run=validation_data.get("max_mining_per_run", 5),
        )

        # Parse execution section
        execution_data = data.get("execution", {})
        execution = ExecutionConfig(
            train=ExecutionPeriod(
                start=execution_data.get("train", {}).get("start", ""),
                end=execution_data.get("train", {}).get("end", ""),
            ),
            valid=ExecutionPeriod(
                start=execution_data.get("valid", {}).get("start", ""),
                end=execution_data.get("valid", {}).get("end", ""),
            ),
            test=ExecutionPeriod(
                start=execution_data.get("test", {}).get("start", ""),
                end=execution_data.get("test", {}).get("end", ""),
            ),
        )

        # Parse features section
        features = data.get("features", {})

        return cls(
            data_check_interval_seconds=data_check_interval,
            revalidation_interval_hours=revalidation_interval,
            revalidation_days_threshold=revalidation_days,
            mining_interval_hours=mining_interval,
            app4_bridge=app4_bridge,
            factor=factor,
            validation=validation,
            execution=execution,
            enable_data_monitor=features.get("enable_data_monitor", True),
            enable_revalidation=features.get("enable_revalidation", True),
            enable_mining=features.get("enable_mining", True),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "runtime": {
                "data_check_interval_seconds": self.data_check_interval_seconds,
                "revalidation_interval_hours": self.revalidation_interval_hours,
                "revalidation_days_threshold": self.revalidation_days_threshold,
                "mining_interval_hours": self.mining_interval_hours,
            },
            "app4_bridge": {
                "enabled": self.app4_bridge.enabled,
                "interfaces": self.app4_bridge.interfaces,
                "data_roots": self.app4_bridge.data_roots,
                "freshness_threshold_hours": self.app4_bridge.freshness_threshold_hours,
                "update_timeout_seconds": self.app4_bridge.update_timeout_seconds,
                "max_update_interfaces_per_cycle": self.app4_bridge.max_update_interfaces_per_cycle,
            },
            "factor": {
                "library_path": self.factor.library_path,
                "monitoring_output_path": self.factor.monitoring_output_path,
                "backtest_config_path": self.factor.backtest_config_path,
            },
            "validation": {
                "min_ic": self.validation.min_ic,
                "min_rank_ic": self.validation.min_rank_ic,
                "max_revalidation_per_run": self.validation.max_revalidation_per_run,
                "max_mining_per_run": self.validation.max_mining_per_run,
            },
            "execution": {
                "train": {"start": self.execution.train.start, "end": self.execution.train.end},
                "valid": {"start": self.execution.valid.start, "end": self.execution.valid.end},
                "test": {"start": self.execution.test.start, "end": self.execution.test.end},
            },
            "features": {
                "enable_data_monitor": self.enable_data_monitor,
                "enable_revalidation": self.enable_revalidation,
                "enable_mining": self.enable_mining,
            },
        }


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

    # Global
    enable_data_monitor: bool = True
    enable_revalidation: bool = True
    enable_mining: bool = True

    @classmethod
    def from_pipeline_config(cls, pipeline_config: PipelineConfig) -> "SchedulerConfig":
        """
        Create SchedulerConfig from a PipelineConfig.

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
            enable_data_monitor=pipeline_config.enable_data_monitor,
            enable_revalidation=pipeline_config.enable_revalidation,
            enable_mining=pipeline_config.enable_mining,
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
    """
    Monitors data directory for updates.

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
        """
        Check for data updates and return list of events.

        Returns:
            List of SchedulerContext with DATA_UPDATE events for each detected change.
        """
        ...

    @abstractmethod
    def get_last_check_time(self) -> Optional[datetime]:
        """Get timestamp of last check."""
        ...


class RevalidationScheduler(ABC):
    """
    Schedules periodic factor revalidation.

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
        """
        Run one revalidation cycle.

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


class MiningScheduler(ABC):
    """
    Schedules periodic new factor mining.

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
        """
        Run one mining cycle.

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
    timestamp: datetime = field(default_factory=datetime.now)
