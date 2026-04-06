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
    interface_tiers: dict[str, list[str]] = field(default_factory=dict)
    data_roots: list[str] = field(default_factory=list)
    freshness_threshold_hours: int = 24
    update_timeout_seconds: int = 120
    max_update_interfaces_per_cycle: int = 5
    python_executable: str = ""


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
class CircuitBreakerConfig:
    """Configuration for the global circuit breaker mechanism."""

    max_consecutive_zero_pass_cycles: int = 3
    cooldown_multiplier: float = 3.0
    max_cooldown_count: int = 5
    reset_on_success: bool = True

    @classmethod
    def from_dict(cls, d: dict) -> "CircuitBreakerConfig":
        return cls(
            max_consecutive_zero_pass_cycles=d.get("max_consecutive_zero_pass_cycles", 3),
            cooldown_multiplier=d.get("cooldown_multiplier", 3.0),
            max_cooldown_count=d.get("max_cooldown_count", 5),
            reset_on_success=d.get("reset_on_success", True),
        )


@dataclass
class EvolutionConfig:
    """Configuration for evolution mode in continuous mining."""

    enabled: bool = False
    max_rounds: int = 3
    mutation_enabled: bool = True
    crossover_enabled: bool = False
    crossover_size: int = 2
    crossover_n: int = 2
    parallel_enabled: bool = False
    fresh_start: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "EvolutionConfig":
        return cls(
            enabled=d.get("enabled", False),
            max_rounds=d.get("max_rounds", 3),
            mutation_enabled=d.get("mutation_enabled", True),
            crossover_enabled=d.get("crossover_enabled", False),
            crossover_size=d.get("crossover_size", 2),
            crossover_n=d.get("crossover_n", 2),
            parallel_enabled=d.get("parallel_enabled", False),
            fresh_start=d.get("fresh_start", False),
        )


@dataclass
class StatePersistenceConfig:
    """Configuration for cross-cycle state persistence."""

    pool_save_path: str = "log/continuous/trajectory_pool.json"
    max_pool_size: int = 500
    failure_cooldown_hours: int = 48

    @classmethod
    def from_dict(cls, d: dict) -> "StatePersistenceConfig":
        return cls(
            pool_save_path=d.get("pool_save_path", "log/continuous/trajectory_pool.json"),
            max_pool_size=d.get("max_pool_size", 500),
            failure_cooldown_hours=d.get("failure_cooldown_hours", 48),
        )


@dataclass
class QualityGateConfig:
    """Configuration for quality gate in pipeline mining."""

    min_ic: float = 0.02
    min_rank_ic: float = 0.03
    max_correlation: float = 0.7
    min_sharpe: float = 0.3

    @classmethod
    def from_dict(cls, d: dict) -> "QualityGateConfig":
        return cls(
            min_ic=d.get("min_ic", 0.02),
            min_rank_ic=d.get("min_rank_ic", 0.03),
            max_correlation=d.get("max_correlation", 0.7),
            min_sharpe=d.get("min_sharpe", 0.3),
        )


@dataclass
class EscalationConfig:
    """Configuration for model escalation in continuous mining."""

    enabled: bool = False
    trigger_after_failed_attempts: int = 2
    start_with_tier: int = 1
    escalate_to_max_tier: int = 3
    max_escalations_per_cycle: int = 2

    @classmethod
    def from_dict(cls, d: dict) -> "EscalationConfig":
        if not d:
            return cls()
        return cls(
            enabled=d.get("enabled", False),
            trigger_after_failed_attempts=d.get("trigger_after_failed_attempts", 2),
            start_with_tier=d.get("start_with_tier", 1),
            escalate_to_max_tier=d.get("escalate_to_max_tier", 3),
            max_escalations_per_cycle=d.get("max_escalations_per_cycle", 2),
        )


@dataclass
class AgentLoopConfig:
    """Configuration for AlphaAgentLoop in continuous mining."""

    step_model_routing: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "AgentLoopConfig":
        if not d:
            return cls()
        return cls(
            step_model_routing=d.get("step_model_routing", {}),
        )


@dataclass
class ModelConfig:
    """Configuration for a single model in ensemble."""

    name: str = ""
    tier: int = 2

    @classmethod
    def from_dict(cls, d: dict) -> "ModelConfig":
        if not d:
            return cls()
        return cls(
            name=d.get("name", ""),
            tier=d.get("tier", 2),
        )


@dataclass
class EnsembleConfig:
    """Configuration for ensemble aggregation in continuous mining."""

    enabled: bool = False
    strategy: str = "voting"
    models: list[ModelConfig] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "EnsembleConfig":
        if not d:
            return cls()
        return cls(
            enabled=d.get("enabled", False),
            strategy=d.get("strategy", "voting"),
            models=[ModelConfig.from_dict(m) for m in d.get("models", [])],
        )


@dataclass
class ProviderEntryConfig:
    """Configuration for a single provider in the pool."""

    name: str = ""
    api_keys: list[str] = field(default_factory=list)
    base_url: str | None = None
    model: str | None = None
    tags: list[str] = field(default_factory=list)
    tier: int = 2

    @classmethod
    def from_dict(cls, d: dict) -> "ProviderEntryConfig":
        if not d:
            return cls()

        import os

        raw_keys = d.get("api_keys", [])
        resolved_keys = []

        for k in raw_keys:
            if isinstance(k, str) and k.startswith("${") and k.endswith("}"):
                env_var = k[2:-1]
                val = os.environ.get(env_var)
                if val:
                    resolved_keys.append(val)
            elif isinstance(k, str) and k.startswith("$"):
                env_var = k[1:]
                val = os.environ.get(env_var)
                if val:
                    resolved_keys.append(val)
            else:
                resolved_keys.append(k)

        if not resolved_keys:
            # Fallback to global .env setting if API key isn't provided in YAML
            try:
                from quantaalpha.llm.config import LLM_SETTINGS

                if getattr(LLM_SETTINGS, "openai_api_key", None):
                    resolved_keys = [LLM_SETTINGS.openai_api_key]
            except Exception:
                pass

        return cls(
            name=d.get("name", ""),
            api_keys=resolved_keys,
            base_url=d.get("base_url"),
            model=d.get("model"),
            tags=d.get("tags", []),
            tier=d.get("tier", 2),
        )


@dataclass
class ProviderPoolConfig:
    """Configuration for LLM provider pool."""

    enabled: bool = False
    routing: str = "round_robin"
    providers: list[ProviderEntryConfig] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "ProviderPoolConfig":
        if not d:
            return cls()
        return cls(
            enabled=d.get("enabled", False),
            routing=d.get("routing", "round_robin"),
            providers=[ProviderEntryConfig.from_dict(p) for p in d.get("providers", [])],
        )


@dataclass
class DirectionPlannerConfig:
    """Configuration for adaptive direction planning."""

    enabled: bool = False
    diversity_window: int = 3
    last_failed_within_hours: int = 48

    @classmethod
    def from_dict(cls, d: dict) -> "DirectionPlannerConfig":
        if not d:
            return cls()
        return cls(
            enabled=d.get("enabled", False),
            diversity_window=d.get("diversity_window", 3),
            last_failed_within_hours=d.get("last_failed_within_hours", 48),
        )


@dataclass
class MiningConfig:
    """Configuration for pipeline-based mining."""

    pipeline_mode: bool = False
    steps_per_mining: int = 5
    max_loops_per_cycle: int = 3
    log_root: str = "log/continuous/mining"
    evolution: EvolutionConfig = field(default_factory=EvolutionConfig)
    state: StatePersistenceConfig = field(default_factory=StatePersistenceConfig)
    quality_gate: QualityGateConfig = field(default_factory=QualityGateConfig)
    escalation: EscalationConfig = field(default_factory=EscalationConfig)
    agent_loop: AgentLoopConfig = field(default_factory=AgentLoopConfig)
    ensemble: EnsembleConfig = field(default_factory=EnsembleConfig)
    provider_pool: ProviderPoolConfig = field(default_factory=ProviderPoolConfig)
    direction_planner: DirectionPlannerConfig = field(default_factory=DirectionPlannerConfig)

    @classmethod
    def from_dict(cls, d: dict) -> "MiningConfig":
        if not d:
            return cls()
        return cls(
            pipeline_mode=d.get("pipeline_mode", False),
            steps_per_mining=d.get("steps_per_mining", 5),
            max_loops_per_cycle=d.get("max_loops_per_cycle", 3),
            log_root=d.get("log_root", "log/continuous/mining"),
            evolution=EvolutionConfig.from_dict(d.get("evolution", {})),
            state=StatePersistenceConfig.from_dict(d.get("state", {})),
            quality_gate=QualityGateConfig.from_dict(d.get("quality_gate", {})),
            escalation=EscalationConfig.from_dict(d.get("escalation", {})),
            agent_loop=AgentLoopConfig.from_dict(d.get("agent_loop", {})),
            ensemble=EnsembleConfig.from_dict(d.get("ensemble", {})),
            provider_pool=ProviderPoolConfig.from_dict(d.get("provider_pool", {})),
            direction_planner=DirectionPlannerConfig.from_dict(d.get("direction_planner", {})),
        )


@dataclass
class PipelineConfig:
    """Full pipeline configuration parsed from pipeline.yaml."""

    # Runtime scheduling
    data_check_interval_seconds: int = 300
    revalidation_interval_hours: int = 24
    revalidation_days_threshold: int = 21
    mining_interval_hours: int = 12
    cycle_budget_seconds: int = 3600
    per_factor_timeout_seconds: int = 300

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

    # Circuit breaker
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)

    # Mining
    mining: MiningConfig = field(default_factory=MiningConfig)

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

        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict | None) -> "PipelineConfig":
        """Internal: construct PipelineConfig from a dict (no file I/O)."""
        if data is None:
            return cls()

        # Parse runtime section
        runtime = data.get("runtime", {})
        data_check_interval = runtime.get("data_check_interval_seconds", 300)
        revalidation_interval = runtime.get("revalidation_interval_hours", 24)
        revalidation_days = runtime.get("revalidation_days_threshold", 21)
        mining_interval = runtime.get("mining_interval_hours", 12)
        cycle_budget = runtime.get("cycle_budget_seconds", 3600)
        per_factor_timeout = runtime.get("per_factor_timeout_seconds", 300)

        # Parse app4_bridge section
        app4_data = data.get("app4_bridge", {})
        app4_bridge = App4BridgeConfig(
            enabled=app4_data.get("enabled", True),
            interfaces=app4_data.get("interfaces", []),
            interface_tiers=app4_data.get("interface_tiers", {}),
            data_roots=app4_data.get("data_roots", []),
            freshness_threshold_hours=app4_data.get("freshness_threshold_hours", 24),
            update_timeout_seconds=app4_data.get("update_timeout_seconds", 120),
            max_update_interfaces_per_cycle=app4_data.get("max_update_interfaces_per_cycle", 5),
            python_executable=app4_data.get("python_executable", ""),
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

        # Parse circuit_breaker section
        cb_config = CircuitBreakerConfig.from_dict(data.get("circuit_breaker", {}))

        # Parse mining section
        mining_data = data.get("mining", {})
        mining = MiningConfig.from_dict(mining_data)

        return cls(
            data_check_interval_seconds=data_check_interval,
            revalidation_interval_hours=revalidation_interval,
            revalidation_days_threshold=revalidation_days,
            mining_interval_hours=mining_interval,
            cycle_budget_seconds=cycle_budget,
            per_factor_timeout_seconds=per_factor_timeout,
            app4_bridge=app4_bridge,
            factor=factor,
            validation=validation,
            execution=execution,
            enable_data_monitor=features.get("enable_data_monitor", True),
            enable_revalidation=features.get("enable_revalidation", True),
            enable_mining=features.get("enable_mining", True),
            circuit_breaker=cb_config,
            mining=mining,
        )

    @classmethod
    def from_yaml_dict(cls, data: dict | None) -> "PipelineConfig":
        """Public: construct PipelineConfig from a dict (paths already resolved to absolute)."""
        return cls._from_dict(data)

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "runtime": {
                "data_check_interval_seconds": self.data_check_interval_seconds,
                "revalidation_interval_hours": self.revalidation_interval_hours,
                "revalidation_days_threshold": self.revalidation_days_threshold,
                "mining_interval_hours": self.mining_interval_hours,
                "cycle_budget_seconds": self.cycle_budget_seconds,
                "per_factor_timeout_seconds": self.per_factor_timeout_seconds,
            },
            "app4_bridge": {
                "enabled": self.app4_bridge.enabled,
                "interfaces": self.app4_bridge.interfaces,
                "interface_tiers": self.app4_bridge.interface_tiers,
                "data_roots": self.app4_bridge.data_roots,
                "freshness_threshold_hours": self.app4_bridge.freshness_threshold_hours,
                "update_timeout_seconds": self.app4_bridge.update_timeout_seconds,
                "max_update_interfaces_per_cycle": self.app4_bridge.max_update_interfaces_per_cycle,
                "python_executable": self.app4_bridge.python_executable,
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
            "circuit_breaker": {
                "max_consecutive_zero_pass_cycles": self.circuit_breaker.max_consecutive_zero_pass_cycles,
                "cooldown_multiplier": self.circuit_breaker.cooldown_multiplier,
                "max_cooldown_count": self.circuit_breaker.max_cooldown_count,
                "reset_on_success": self.circuit_breaker.reset_on_success,
            },
            "mining": {
                "pipeline_mode": self.mining.pipeline_mode,
                "steps_per_mining": self.mining.steps_per_mining,
                "max_loops_per_cycle": self.mining.max_loops_per_cycle,
                "log_root": self.mining.log_root,
                "evolution": {
                    "enabled": self.mining.evolution.enabled,
                    "max_rounds": self.mining.evolution.max_rounds,
                    "mutation_enabled": self.mining.evolution.mutation_enabled,
                    "crossover_enabled": self.mining.evolution.crossover_enabled,
                },
                "state": {
                    "pool_save_path": self.mining.state.pool_save_path,
                    "max_pool_size": self.mining.state.max_pool_size,
                },
                "quality_gate": {
                    "min_ic": self.mining.quality_gate.min_ic,
                    "min_rank_ic": self.mining.quality_gate.min_rank_ic,
                },
                "escalation": {
                    "enabled": self.mining.escalation.enabled,
                    "trigger_after_failed_attempts": self.mining.escalation.trigger_after_failed_attempts,
                    "max_escalations_per_cycle": self.mining.escalation.max_escalations_per_cycle,
                },
                "agent_loop": {
                    "step_model_routing": self.mining.agent_loop.step_model_routing,
                },
                "ensemble": {
                    "enabled": self.mining.ensemble.enabled,
                    "strategy": self.mining.ensemble.strategy,
                    "models": [{"name": m.name, "tier": m.tier} for m in self.mining.ensemble.models],
                },
                "provider_pool": {
                    "enabled": self.mining.provider_pool.enabled,
                    "routing": self.mining.provider_pool.routing,
                    "providers": [
                        {
                            "name": p.name,
                            "api_keys": p.api_keys,
                            "base_url": p.base_url,
                            "model": p.model,
                            "tags": p.tags,
                            "tier": p.tier,
                        }
                        for p in self.mining.provider_pool.providers
                    ],
                },
                "direction_planner": {
                    "enabled": self.mining.direction_planner.enabled,
                    "diversity_window": self.mining.direction_planner.diversity_window,
                    "last_failed_within_hours": self.mining.direction_planner.last_failed_within_hours,
                },
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
            cycle_budget_seconds=pipeline_config.cycle_budget_seconds,
            per_factor_timeout_seconds=pipeline_config.per_factor_timeout_seconds,
            min_ic=pipeline_config.validation.min_ic,
            min_rank_ic=pipeline_config.validation.min_rank_ic,
            enable_data_monitor=pipeline_config.enable_data_monitor,
            enable_revalidation=pipeline_config.enable_revalidation,
            enable_mining=pipeline_config.enable_mining,
            mining=pipeline_config.mining,
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
