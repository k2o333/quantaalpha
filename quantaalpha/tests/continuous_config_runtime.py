"""Tests for continuous pipeline configuration.

Verifies:
- YAML configuration parsing
- SchedulerConfig creation from PipelineConfig
- Configuration contract compliance
"""
# ruff: noqa: D102, D103

import tempfile
from pathlib import Path

import pytest
import yaml


class TestMiningConfig:
    """Tests for MiningConfig dataclasses and YAML parsing."""

    def test_pipeline_config_mining_section(self, tmp_path):
        """PipelineConfig parses mining section from YAML."""
        from quantaalpha.continuous.scheduler import PipelineConfig

        yaml_content = """
runtime:
  data_check_interval_seconds: 300
  cycle_budget_seconds: 7200
factor:
  library_path: "data/factorlib/all_factors_library.json"
validation:
  min_ic: 0.02
  max_mining_per_run: 5
mining:
  pipeline_mode: true
  steps_per_mining: 5
  max_loops_per_cycle: 3
  log_root: "log/continuous/mining"
  evolution:
    enabled: false
    max_rounds: 3
    mutation_enabled: true
    crossover_enabled: false
    crossover_size: 2
    crossover_n: 2
    parallel_enabled: false
    fresh_start: false
    historical_active_parent_count: 4
    historical_parent_min_rank_ic: 0.02
    historical_parent_statuses: [active]
  state:
    pool_save_path: "log/continuous/trajectory_pool.json"
    max_pool_size: 500
    failure_cooldown_hours: 48
  quality_gate:
    min_ic: 0.02
    min_rank_ic: 0.03
    max_correlation: 0.7
    min_sharpe: 0.3
"""
        yaml_path = tmp_path / "test_mining.yaml"
        yaml_path.write_text(yaml_content)

        config = PipelineConfig.from_yaml(str(yaml_path))
        assert config.mining is not None
        assert config.mining.pipeline_mode is True
        assert config.mining.steps_per_mining == 5
        assert config.mining.max_loops_per_cycle == 3
        assert config.mining.evolution.max_rounds == 3
        assert config.mining.evolution.parallel_enabled is False
        assert config.mining.evolution.historical_active_parent_count == 4
        assert config.mining.evolution.historical_parent_min_rank_ic == 0.02
        assert config.mining.evolution.historical_parent_statuses == ["active"]
        assert config.mining.state.max_pool_size == 500

    def test_pipeline_config_mining_defaults(self):
        """PipelineConfig uses safe defaults when mining section is absent."""
        from quantaalpha.continuous.scheduler import PipelineConfig

        config = PipelineConfig()
        assert config.mining.pipeline_mode is False
        assert config.mining.steps_per_mining == 5
        assert config.mining.evolution.max_rounds == 3
        assert config.mining.evolution.historical_active_parent_count == 0
        assert config.mining.evolution.historical_parent_min_rank_ic == 0.0
        assert config.mining.evolution.historical_parent_statuses == ["active"]
        assert config.mining.state.max_pool_size == 500


class TestEscalationConfig:
    """Tests for EscalationConfig dataclass and YAML parsing."""

    def test_escalation_config_defaults(self):
        """EscalationConfig uses safe defaults."""
        from quantaalpha.continuous.scheduler import EscalationConfig

        config = EscalationConfig()
        assert config.enabled is False
        assert config.trigger_after_failed_attempts == 2
        assert config.start_with_tier == 1
        assert config.escalate_to_max_tier == 3
        assert config.max_escalations_per_cycle == 2

    def test_escalation_config_from_dict(self):
        """EscalationConfig parses from dict."""
        from quantaalpha.continuous.scheduler import EscalationConfig

        config = EscalationConfig.from_dict(
            {
                "enabled": True,
                "trigger_after_failed_attempts": 3,
                "start_with_tier": 1,
                "escalate_to_max_tier": 3,
                "max_escalations_per_cycle": 1,
            }
        )
        assert config.enabled is True
        assert config.trigger_after_failed_attempts == 3
        assert config.max_escalations_per_cycle == 1

    def test_mining_config_has_escalation(self):
        """MiningConfig includes escalation field."""
        from quantaalpha.continuous.scheduler import MiningConfig

        config = MiningConfig()
        assert config.escalation is not None
        assert config.escalation.enabled is False

    def test_pipeline_config_parses_escalation(self, tmp_path):
        """PipelineConfig parses mining.escalation section from YAML."""
        from quantaalpha.continuous.scheduler import PipelineConfig

        yaml_content = """
runtime:
  data_check_interval_seconds: 300
  cycle_budget_seconds: 7200
factor:
  library_path: "data/factorlib/all_factors_library.json"
validation:
  min_ic: 0.02
  max_mining_per_run: 5
mining:
  pipeline_mode: true
  escalation:
    enabled: true
    trigger_after_failed_attempts: 3
    max_escalations_per_cycle: 1
"""
        yaml_path = tmp_path / "test_escalation.yaml"
        yaml_path.write_text(yaml_content)

        config = PipelineConfig.from_yaml(str(yaml_path))
        assert config.mining.escalation.enabled is True
        assert config.mining.escalation.trigger_after_failed_attempts == 3
        assert config.mining.escalation.max_escalations_per_cycle == 1


class TestAgentLoopConfig:
    """Tests for AgentLoopConfig dataclass and YAML parsing."""

    def test_agent_loop_config_defaults(self):
        """AgentLoopConfig uses safe defaults."""
        from quantaalpha.continuous.scheduler import AgentLoopConfig

        config = AgentLoopConfig()
        assert config.step_model_routing == {}

    def test_agent_loop_config_from_dict(self):
        """AgentLoopConfig parses from dict."""
        from quantaalpha.continuous.scheduler import AgentLoopConfig

        config = AgentLoopConfig.from_dict(
            {
                "step_model_routing": {
                    "propose": {"require_capabilities": ["reasoning"], "max_tier": 3},
                    "feedback": {"require_capabilities": ["structured"], "max_tier": 3},
                }
            }
        )
        assert "propose" in config.step_model_routing
        assert config.step_model_routing["propose"]["require_capabilities"] == ["reasoning"]
        assert config.step_model_routing["propose"]["max_tier"] == 3

    def test_mining_config_has_agent_loop(self):
        """MiningConfig includes agent_loop field."""
        from quantaalpha.continuous.scheduler import MiningConfig

        config = MiningConfig()
        assert config.agent_loop is not None
        assert config.agent_loop.step_model_routing == {}

    def test_pipeline_config_parses_agent_loop(self, tmp_path):
        """PipelineConfig parses mining.agent_loop section from YAML."""
        from quantaalpha.continuous.scheduler import PipelineConfig

        yaml_content = """
runtime:
  data_check_interval_seconds: 300
  cycle_budget_seconds: 7200
factor:
  library_path: "data/factorlib/all_factors_library.json"
validation:
  min_ic: 0.02
  max_mining_per_run: 5
mining:
  pipeline_mode: true
  agent_loop:
    step_model_routing:
      propose:
        require_capabilities: ["reasoning"]
        max_tier: 3
"""
        yaml_path = tmp_path / "test_agent_loop.yaml"
        yaml_path.write_text(yaml_content)

        config = PipelineConfig.from_yaml(str(yaml_path))
        assert "propose" in config.mining.agent_loop.step_model_routing
        assert config.mining.agent_loop.step_model_routing["propose"]["require_capabilities"] == ["reasoning"]


class TestEnsembleConfig:
    """Tests for EnsembleConfig dataclass."""

    def test_ensemble_config_defaults(self):
        from quantaalpha.continuous.scheduler import EnsembleConfig

        config = EnsembleConfig()
        assert config.enabled is False
        assert config.strategy == "voting"
        assert config.models == []
        assert config.max_workers == 3

    def test_ensemble_config_from_dict(self):
        from quantaalpha.continuous.scheduler import EnsembleConfig

        config = EnsembleConfig.from_dict(
            {
                "enabled": True,
                "strategy": "fusion_score",
                "models": [{"name": "gpt-4-turbo", "tier": 3}],
            }
        )
        assert config.enabled is True
        assert config.strategy == "fusion_score"
        assert len(config.models) == 1

    def test_ensemble_config_from_dict_with_max_workers(self):
        from quantaalpha.continuous.scheduler import EnsembleConfig

        config = EnsembleConfig.from_dict(
            {
                "enabled": True,
                "strategy": "collect_all",
                "max_workers": 5,
                "models": [{"name": "m1"}, {"name": "m2"}],
            }
        )
        assert config.enabled is True
        assert config.strategy == "collect_all"
        assert config.max_workers == 5
        assert len(config.models) == 2

    def test_mining_config_has_ensemble(self):
        from quantaalpha.continuous.scheduler import MiningConfig

        config = MiningConfig()
        assert config.ensemble is not None
        assert config.ensemble.enabled is False

    def test_pipeline_config_parses_ensemble(self, tmp_path):
        from quantaalpha.continuous.scheduler import PipelineConfig

        yaml_content = """
runtime:
  data_check_interval_seconds: 300
  cycle_budget_seconds: 7200
factor:
  library_path: "data/factorlib/all_factors_library.json"
validation:
  min_ic: 0.02
  max_mining_per_run: 5
mining:
  pipeline_mode: true
  ensemble:
    enabled: true
    strategy: "voting"
"""
        yaml_path = tmp_path / "test_ensemble.yaml"
        yaml_path.write_text(yaml_content)

        config = PipelineConfig.from_yaml(str(yaml_path))
        assert config.mining.ensemble.enabled is True
        assert config.mining.ensemble.strategy == "voting"

    def test_pipeline_config_parses_ensemble_max_workers(self, tmp_path):
        """PipelineConfig parses ensemble max_workers from YAML."""
        from quantaalpha.continuous.scheduler import PipelineConfig

        yaml_content = """
runtime:
  data_check_interval_seconds: 300
  cycle_budget_seconds: 7200
factor:
  library_path: "data/factorlib/all_factors_library.json"
validation:
  min_ic: 0.02
  max_mining_per_run: 5
mining:
  pipeline_mode: true
  ensemble:
    enabled: true
    strategy: "collect_all"
    max_workers: 3
    models:
      - name: "litellm_mistral"
      - name: "litellm_glm47f"
"""
        yaml_path = tmp_path / "test_ensemble_workers.yaml"
        yaml_path.write_text(yaml_content)

        config = PipelineConfig.from_yaml(str(yaml_path))
        assert config.mining.ensemble.max_workers == 3
        assert len(config.mining.ensemble.models) == 2


class TestProviderPoolConfig:
    """Tests for ProviderPoolConfig dataclass."""

    def test_provider_pool_config_defaults(self):
        from quantaalpha.continuous.scheduler import ProviderPoolConfig

        config = ProviderPoolConfig()
        assert config.enabled is False
        assert config.routing == "round_robin"
        assert config.providers == []

    def test_provider_pool_config_from_dict(self):
        from quantaalpha.continuous.scheduler import ProviderPoolConfig

        config = ProviderPoolConfig.from_dict(
            {
                "enabled": True,
                "routing": "least_latency",
                "providers": [
                    {
                        "name": "openai",
                        "api_keys": ["k1"],
                        "model": "gpt-4",
                        "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
                    }
                ],
            }
        )
        assert config.enabled is True
        assert config.routing == "least_latency"
        assert len(config.providers) == 1
        assert config.providers[0].extra_body == {"chat_template_kwargs": {"enable_thinking": False}}

    def test_mining_config_has_provider_pool(self):
        from quantaalpha.continuous.scheduler import MiningConfig

        config = MiningConfig()
        assert hasattr(config, "provider_pool")
        assert config.provider_pool.enabled is False

    def test_pipeline_config_parses_provider_pool(self, tmp_path):
        from quantaalpha.continuous.scheduler import PipelineConfig

        yaml_content = """
runtime:
  data_check_interval_seconds: 300
  cycle_budget_seconds: 7200
factor:
  library_path: "data/factorlib/all_factors_library.json"
validation:
  min_ic: 0.02
  max_mining_per_run: 5
mining:
  pipeline_mode: true
  provider_pool:
    enabled: true
    routing: "least_latency"
"""
        yaml_path = tmp_path / "test_pp.yaml"
        yaml_path.write_text(yaml_content)

        config = PipelineConfig.from_yaml(str(yaml_path))
        assert config.mining.provider_pool.enabled is True
        assert config.mining.provider_pool.routing == "least_latency"


class TestDirectionPlannerConfig:
    """Tests for DirectionPlannerConfig dataclass."""

    def test_direction_planner_config_defaults(self):
        from quantaalpha.continuous.scheduler import DirectionPlannerConfig

        config = DirectionPlannerConfig()
        assert config.enabled is False
        assert config.diversity_window == 3
        assert config.last_failed_within_hours == 48

    def test_direction_planner_config_from_dict(self):
        from quantaalpha.continuous.scheduler import DirectionPlannerConfig

        config = DirectionPlannerConfig.from_dict(
            {
                "enabled": True,
                "diversity_window": 5,
                "last_failed_within_hours": 24,
            }
        )
        assert config.enabled is True
        assert config.diversity_window == 5
        assert config.last_failed_within_hours == 24

    def test_mining_config_has_direction_planner(self):
        from quantaalpha.continuous.scheduler import MiningConfig

        config = MiningConfig()
        assert config.direction_planner is not None
        assert config.direction_planner.enabled is False

    def test_pipeline_config_parses_direction_planner(self, tmp_path):
        from quantaalpha.continuous.scheduler import PipelineConfig

        yaml_content = """
runtime:
  data_check_interval_seconds: 300
  cycle_budget_seconds: 7200
factor:
  library_path: "data/factorlib/all_factors_library.json"
validation:
  min_ic: 0.02
  max_mining_per_run: 5
mining:
  pipeline_mode: true
  direction_planner:
    enabled: true
    diversity_window: 5
"""
        yaml_path = tmp_path / "test_dp.yaml"
        yaml_path.write_text(yaml_content)

        config = PipelineConfig.from_yaml(str(yaml_path))
        assert config.mining.direction_planner.enabled is True
        assert config.mining.direction_planner.diversity_window == 5


class TestOrchestrationConfigPhase1TargetShape:
    """Tests for Phase 1 exact target shape: enabled, mode, max_steps_per_cycle, start_node, metrics, conditions, nodes."""

    def test_orchestration_config_phase1_target_shape_fields(self):
        """OrchestrationConfig has exact Phase 1 target shape fields."""
        from quantaalpha.continuous.scheduler import OrchestrationConfig

        config = OrchestrationConfig()
        # Verify all Phase 1 target shape fields exist
        assert hasattr(config, "enabled")
        assert hasattr(config, "mode")
        assert hasattr(config, "max_steps_per_cycle")
        assert hasattr(config, "start_node")
        assert hasattr(config, "metrics")
        assert hasattr(config, "conditions")
        assert hasattr(config, "nodes")

    def test_orchestration_config_phase1_defaults(self):
        """OrchestrationConfig uses Phase 1 safe defaults."""
        from quantaalpha.continuous.scheduler import OrchestrationConfig

        config = OrchestrationConfig()
        assert config.enabled is False
        assert config.mode == "conditional_flow"
        assert config.max_steps_per_cycle == 6
        assert config.start_node == "original"
        assert isinstance(config.metrics, dict) or hasattr(config.metrics, "min_pass_rate_for_crossover")
        assert config.conditions == []
        assert config.nodes == []

    def test_orchestration_config_from_dict_phase1_shape(self):
        """OrchestrationConfig.from_dict parses Phase 1 target shape."""
        from quantaalpha.continuous.scheduler import OrchestrationConfig

        data = {
            "enabled": True,
            "mode": "conditional_flow",
            "max_steps_per_cycle": 8,
            "start_node": "original",
            "metrics": {
                "min_pass_rate_for_crossover": 0.25,
                "min_active_parents_for_crossover": 3,
                "min_diversity_score": 0.15,
                "max_consecutive_failures": 3,
            },
            "conditions": [
                {
                    "name": "enough_parents",
                    "type": "threshold",
                    "metric": "active_parents",
                    "operator": "gte",
                    "value": 2,
                }
            ],
            "nodes": [
                {
                    "id": "original",
                    "kind": "action",
                    "action": "original",
                    "next": [{"goto": "stop"}],
                }
            ],
        }
        config = OrchestrationConfig.from_dict(data)

        assert config.enabled is True
        assert config.mode == "conditional_flow"
        assert config.max_steps_per_cycle == 8
        assert config.start_node == "original"
        assert config.metrics.min_pass_rate_for_crossover == 0.25
        assert config.metrics.min_active_parents_for_crossover == 3
        assert len(config.conditions) == 1
        assert config.conditions[0].name == "enough_parents"
        assert len(config.nodes) == 1
        assert config.nodes[0].id == "original"
        assert config.nodes[0].kind == "action"
        assert config.nodes[0].action == "original"

    def test_mining_config_parses_orchestration_phase1_shape(self):
        """MiningConfig.from_dict parses Phase 1 orchestration shape."""
        from quantaalpha.continuous.scheduler import MiningConfig

        data = {
            "pipeline_mode": True,
            "orchestration": {
                "enabled": True,
                "mode": "conditional_flow",
                "max_steps_per_cycle": 10,
                "start_node": "mutation",
                "metrics": {
                    "min_pass_rate_for_crossover": 0.30,
                    "min_active_parents_for_crossover": 4,
                    "min_diversity_score": 0.20,
                    "max_consecutive_failures": 4,
                },
                "conditions": [
                    {
                        "name": "crossover_ready",
                        "type": "all_of",
                        "conditions": ["enough_parents", "pass_rate_good"],
                    }
                ],
                "nodes": [
                    {
                        "id": "mutation",
                        "kind": "action",
                        "action": "mutation",
                        "params": {"source": "pipeline_evolution"},
                        "next": [{"goto": "stop"}],
                    }
                ],
            },
        }
        config = MiningConfig.from_dict(data)

        assert config.orchestration.enabled is True
        assert config.orchestration.mode == "conditional_flow"
        assert config.orchestration.max_steps_per_cycle == 10
        assert config.orchestration.start_node == "mutation"
        assert config.orchestration.metrics.min_pass_rate_for_crossover == 0.30
        assert len(config.orchestration.conditions) == 1
        assert config.orchestration.conditions[0].name == "crossover_ready"
        assert len(config.orchestration.nodes) == 1
        assert config.orchestration.nodes[0].id == "mutation"

    def test_pipeline_config_parses_orchestration_phase1_from_yaml(self, tmp_path):
        """PipelineConfig parses Phase 1 orchestration shape from YAML."""
        from quantaalpha.continuous.scheduler import PipelineConfig

        yaml_content = """
runtime:
  data_check_interval_seconds: 300
factor:
  library_path: "data/factorlib/all_factors_library.json"
validation:
  min_ic: 0.02
  max_mining_per_run: 5
mining:
  pipeline_mode: true
  orchestration:
    enabled: true
    mode: conditional_flow
    max_steps_per_cycle: 6
    start_node: original

    metrics:
      min_pass_rate_for_crossover: 0.20
      min_active_parents_for_crossover: 2
      min_diversity_score: 0.10
      max_consecutive_failures: 2

    conditions:
      - name: enough_parents
        type: threshold
        metric: active_parents
        operator: gte
        value: 2

      - name: crossover_ready
        type: all_of
        conditions:
          - enough_parents

    nodes:
      - id: original
        kind: action
        action: original
        next:
          - goto: stop

      - id: mutation
        kind: action
        action: mutation
        params:
          source: pipeline_evolution
        next:
          - goto: stop
"""
        yaml_path = tmp_path / "test_orchestration_phase1.yaml"
        yaml_path.write_text(yaml_content)

        config = PipelineConfig.from_yaml(str(yaml_path))

        assert config.mining.orchestration.enabled is True
        assert config.mining.orchestration.mode == "conditional_flow"
        assert config.mining.orchestration.max_steps_per_cycle == 6
        assert config.mining.orchestration.start_node == "original"
        assert config.mining.orchestration.metrics.min_pass_rate_for_crossover == 0.20
        assert len(config.mining.orchestration.conditions) == 2
        assert config.mining.orchestration.conditions[0].name == "enough_parents"
        assert config.mining.orchestration.conditions[1].name == "crossover_ready"
        assert len(config.mining.orchestration.nodes) == 2
        assert config.mining.orchestration.nodes[0].id == "original"
        assert config.mining.orchestration.nodes[1].id == "mutation"


class TestParquetCompactConfig:
    """Tests for parquet compact configuration parsing."""

    def test_factor_library_backend_parses_from_yaml(self, tmp_path: Path):
        """factor.library_backend == 'parquet' parses from yaml."""
        from quantaalpha.continuous.scheduler import PipelineConfig

        yaml_content = """
factor:
  library_backend: parquet
  library_path: third_party/quantaalpha/data/factorlib/all_factors_library.json
  parquet_library_dir: third_party/quantaalpha/data/factorlib/parquet_store
"""
        yaml_path = tmp_path / "test_backend.yaml"
        yaml_path.write_text(yaml_content)

        config = PipelineConfig.from_yaml(str(yaml_path))
        assert config.factor.library_backend == "parquet"

    def test_factor_parquet_library_dir_parses_from_yaml(self, tmp_path: Path):
        """factor.parquet_library_dir parses from yaml."""
        from quantaalpha.continuous.scheduler import PipelineConfig

        yaml_content = """
factor:
  library_backend: parquet
  parquet_library_dir: third_party/quantaalpha/data/factorlib/parquet_store
"""
        yaml_path = tmp_path / "test_parquet_dir.yaml"
        yaml_path.write_text(yaml_content)

        config = PipelineConfig.from_yaml(str(yaml_path))
        assert config.factor.parquet_library_dir == "third_party/quantaalpha/data/factorlib/parquet_store"

    def test_factor_parquet_compact_delta_file_threshold_parses(self, tmp_path: Path):
        """factor.parquet_compact.delta_file_threshold == 100 parses from yaml."""
        from quantaalpha.continuous.scheduler import PipelineConfig

        yaml_content = """
factor:
  library_backend: parquet
  parquet_library_dir: third_party/quantaalpha/data/factorlib/parquet_store
  parquet_compact:
    enabled: true
    delta_file_threshold: 100
    compact_on_save_batch_end: true
    archive_retention: 3
"""
        yaml_path = tmp_path / "test_compact.yaml"
        yaml_path.write_text(yaml_content)

        config = PipelineConfig.from_yaml(str(yaml_path))
        assert config.factor.parquet_compact.delta_file_threshold == 100

    def test_factor_parquet_compact_on_save_batch_end_parses(self, tmp_path: Path):
        """factor.parquet_compact.compact_on_save_batch_end is True parses from yaml."""
        from quantaalpha.continuous.scheduler import PipelineConfig

        yaml_content = """
factor:
  library_backend: parquet
  parquet_compact:
    enabled: true
    delta_file_threshold: 50
    compact_on_save_batch_end: true
"""
        yaml_path = tmp_path / "test_batch_end.yaml"
        yaml_path.write_text(yaml_content)

        config = PipelineConfig.from_yaml(str(yaml_path))
        assert config.factor.parquet_compact.compact_on_save_batch_end is True

    def test_scheduler_config_preserves_factor_parquet_settings(self):
        """SchedulerConfig.from_pipeline_config carries factor parquet settings into orchestrator wiring."""
        from quantaalpha.continuous.scheduler import PipelineConfig, SchedulerConfig

        config = PipelineConfig._from_dict(
            {
                "factor": {
                    "library_backend": "parquet",
                    "parquet_library_dir": "third_party/quantaalpha/data/factorlib/parquet_store",
                    "parquet_compact": {
                        "enabled": True,
                        "delta_file_threshold": 7,
                        "compact_on_save_batch_end": True,
                    },
                }
            }
        )

        scheduler_config = SchedulerConfig.from_pipeline_config(config)

        assert scheduler_config.factor.library_backend == "parquet"
        assert scheduler_config.factor.parquet_library_dir == "third_party/quantaalpha/data/factorlib/parquet_store"
        assert scheduler_config.factor.parquet_compact.delta_file_threshold == 7


def test_pipeline_yaml_declares_distinct_revalidation_and_mining_quality_gate_min_ic():
    """Parse real pipeline.yaml and assert distinct revalidation vs mining IC thresholds."""
    import yaml

    from quantaalpha.continuous.scheduler import PipelineConfig, SchedulerConfig

    path = Path("/home/quan/testdata/aspipe_v4/config/pipeline.yaml")
    raw = yaml.safe_load(path.read_text())

    # Raw YAML assertions
    assert raw["validation"]["min_ic"] == 0.02
    assert raw["mining"]["quality_gate"]["min_ic"] == 0.018
    assert raw["mining"]["quality_gate"]["min_rank_ic"] == 0.03
    assert raw["mining"]["quality_gate"]["max_correlation"] == 0.7
    assert raw["mining"]["quality_gate"]["min_sharpe"] == 0.3

    # Parsed PipelineConfig assertions
    cfg = PipelineConfig.from_yaml(str(path))
    assert cfg.validation.min_ic == 0.02
    assert cfg.mining.quality_gate.min_ic == 0.018

    # SchedulerConfig assertions
    sched = SchedulerConfig.from_pipeline_config(cfg)
    assert sched.min_ic == 0.02
    assert sched.mining.quality_gate.min_ic == 0.018


def test_pipeline_config_parses_llm_runtime_section(tmp_path):
    from quantaalpha.continuous.scheduler import PipelineConfig

    yaml_path = tmp_path / "pipeline.yaml"
    yaml_path.write_text(
        """
llm:
  openai_base_url: "http://litellm.local/v1"
  chat_model: "minimax-m2.7"
  reasoning_model: "minimax-m2.7"
  embedding_model: "codestral-embed"
  embedding_base_url: "http://litellm.local/v1"
  chat_max_tokens: 64000
  chat_temperature: 0.4
  retry:
    max_attempts: 5
    wait_seconds: 5
    model_switch_threshold: 3
    max_attempts_per_provider: 3
""",
        encoding="utf-8",
    )

    cfg = PipelineConfig.from_yaml(str(yaml_path))

    assert cfg.llm.openai_base_url == "http://litellm.local/v1"
    assert cfg.llm.chat_model == "minimax-m2.7"
    assert cfg.llm.reasoning_model == "minimax-m2.7"
    assert cfg.llm.embedding_model == "codestral-embed"
    assert cfg.llm.embedding_base_url == "http://litellm.local/v1"
    assert cfg.llm.chat_max_tokens == 64000
    assert cfg.llm.chat_temperature == 0.4
    assert cfg.llm.retry.max_attempts == 5
    assert cfg.llm.retry.wait_seconds == 5
    assert cfg.llm.retry.model_switch_threshold == 3
    assert cfg.llm.retry.max_attempts_per_provider == 3


class TestRealPipelineYamlLlmConfig:
    """Audit tests for the real config/pipeline.yaml LLM configuration."""

    def test_real_pipeline_yaml_parses_llm_config(self):
        """Test that the real config/pipeline.yaml has valid llm section."""
        import os

        import yaml

        from quantaalpha.continuous.scheduler import PipelineConfig

        config_path = "/home/quan/testdata/aspipe_v4/config/pipeline.yaml"
        assert os.path.exists(config_path), f"Config file not found: {config_path}"

        cfg = PipelineConfig.from_yaml(config_path)
        raw = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
        llm = raw["llm"]
        retry = llm["retry"]

        assert cfg.llm.retry.max_attempts == retry["max_attempts"]
        assert cfg.llm.retry.model_switch_threshold == retry["model_switch_threshold"]
        assert cfg.llm.retry.max_attempts_per_provider == retry["max_attempts_per_provider"]
        assert cfg.llm.chat_model == llm["chat_model"]
        assert cfg.llm.openai_base_url == llm["openai_base_url"]
        assert cfg.llm.chat_max_tokens == llm["chat_max_tokens"]
