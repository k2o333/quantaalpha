"""Integration tests for mining config flow through orchestrator."""

import tempfile
from pathlib import Path

import pytest


class TestOrchestratorMiningConfig:
    """Tests for mining config passing through MiningOrchestrator."""

    def test_orchestrator_passes_mining_config(self):
        """MiningOrchestrator passes mining config to DefaultMiningScheduler."""
        from quantaalpha.continuous.scheduler import SchedulerConfig, MiningConfig

        config = SchedulerConfig(
            mining=MiningConfig(
                pipeline_mode=True,
                steps_per_mining=3,
            ),
        )
        from quantaalpha.continuous.orchestrator import MiningOrchestrator

        orchestrator = MiningOrchestrator(config=config)
        scheduler = orchestrator.mining_scheduler

        assert scheduler._pipeline_mode is True
        assert scheduler._state_cfg.get("steps_per_mining") == 3

    def test_orchestrator_passes_quality_gate_config(self):
        """MiningOrchestrator passes quality_gate config to DefaultMiningScheduler."""
        from quantaalpha.continuous.scheduler import SchedulerConfig, MiningConfig, QualityGateConfig

        config = SchedulerConfig(
            mining=MiningConfig(
                pipeline_mode=True,
                quality_gate=QualityGateConfig(min_ic=0.03, min_rank_ic=0.04),
            ),
        )
        from quantaalpha.continuous.orchestrator import MiningOrchestrator

        orchestrator = MiningOrchestrator(config=config)
        scheduler = orchestrator.mining_scheduler

        assert scheduler._quality_gate_config["min_ic"] == 0.03
        assert scheduler._quality_gate_config["min_rank_ic"] == 0.04

    def test_orchestrator_passes_evolution_config(self):
        """MiningOrchestrator passes evolution config to DefaultMiningScheduler."""
        from quantaalpha.continuous.scheduler import (
            SchedulerConfig,
            MiningConfig,
            EvolutionConfig,
        )

        config = SchedulerConfig(
            mining=MiningConfig(
                pipeline_mode=True,
                evolution=EvolutionConfig(
                    enabled=True,
                    max_rounds=5,
                    crossover_enabled=True,
                ),
            ),
        )
        from quantaalpha.continuous.orchestrator import MiningOrchestrator

        orchestrator = MiningOrchestrator(config=config)
        scheduler = orchestrator.mining_scheduler

        assert scheduler._evolution_cfg["enabled"] is True
        assert scheduler._evolution_cfg["max_rounds"] == 5
        assert scheduler._evolution_cfg["crossover_enabled"] is True


class TestFullPipelineConfigFlow:
    """End-to-end: pipeline.yaml mining section flows to DefaultMiningScheduler."""

    def test_full_pipeline_config_from_yaml(self, tmp_path: Path):
        """End-to-end config flow from YAML to scheduler."""
        from quantaalpha.continuous.scheduler import PipelineConfig, SchedulerConfig

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
  steps_per_mining: 3
  evolution:
    enabled: true
    max_rounds: 2
  quality_gate:
    min_ic: 0.03
"""
        yaml_path = tmp_path / "test_flow.yaml"
        yaml_path.write_text(yaml_content)

        pipeline_config = PipelineConfig.from_yaml(str(yaml_path))
        scheduler_config = SchedulerConfig.from_pipeline_config(pipeline_config)

        assert scheduler_config.mining.pipeline_mode is True
        assert scheduler_config.mining.steps_per_mining == 3
        assert scheduler_config.mining.evolution.enabled is True
        assert scheduler_config.mining.evolution.max_rounds == 2
        assert scheduler_config.mining.quality_gate.min_ic == 0.03

    def test_orchestrator_passes_escalation_config(self):
        """MiningOrchestrator passes escalation config to DefaultMiningScheduler."""
        from quantaalpha.continuous.scheduler import (
            SchedulerConfig,
            MiningConfig,
            EscalationConfig,
        )
        from quantaalpha.continuous.orchestrator import MiningOrchestrator

        config = SchedulerConfig(
            mining=MiningConfig(
                pipeline_mode=True,
                escalation=EscalationConfig(
                    enabled=True,
                    trigger_after_failed_attempts=3,
                ),
            ),
        )
        orchestrator = MiningOrchestrator(config=config)
        scheduler = orchestrator.mining_scheduler

        assert scheduler._escalation_cfg["enabled"] is True
        assert scheduler._escalation_cfg["trigger_after_failed_attempts"] == 3

    def test_orchestrator_passes_agent_loop_config(self):
        """MiningOrchestrator passes agent_loop config to DefaultMiningScheduler."""
        from quantaalpha.continuous.scheduler import (
            SchedulerConfig,
            MiningConfig,
            AgentLoopConfig,
        )
        from quantaalpha.continuous.orchestrator import MiningOrchestrator

        config = SchedulerConfig(
            mining=MiningConfig(
                pipeline_mode=True,
                agent_loop=AgentLoopConfig(
                    step_model_routing={
                        "propose": {"require_capabilities": ["reasoning"], "max_tier": 3},
                    },
                ),
            ),
        )
        orchestrator = MiningOrchestrator(config=config)
        scheduler = orchestrator.mining_scheduler

        assert "propose" in scheduler._agent_loop_cfg.get("step_model_routing", {})

    def test_orchestrator_passes_ensemble_config(self):
        from quantaalpha.continuous.scheduler import (
            SchedulerConfig,
            MiningConfig,
            EnsembleConfig,
            ModelConfig,
        )
        from quantaalpha.continuous.orchestrator import MiningOrchestrator

        config = SchedulerConfig(
            mining=MiningConfig(
                pipeline_mode=True,
                ensemble=EnsembleConfig(
                    enabled=True,
                    strategy="voting",
                    models=[ModelConfig(name="gpt-4-turbo", tier=3)],
                ),
            ),
        )
        orchestrator = MiningOrchestrator(config=config)
        scheduler = orchestrator.mining_scheduler
        assert scheduler._ensemble_cfg["enabled"] is True
        assert scheduler._ensemble_cfg["strategy"] == "voting"

    def test_orchestrator_passes_provider_pool_config(self):
        from quantaalpha.continuous.scheduler import (
            SchedulerConfig,
            MiningConfig,
            ProviderPoolConfig,
        )
        from quantaalpha.continuous.orchestrator import MiningOrchestrator

        config = SchedulerConfig(
            mining=MiningConfig(
                pipeline_mode=True,
                provider_pool=ProviderPoolConfig(
                    enabled=True,
                    routing="least_latency",
                ),
            ),
        )
        orchestrator = MiningOrchestrator(config=config)
        scheduler = orchestrator.mining_scheduler
        assert scheduler._provider_pool_cfg["enabled"] is True
        assert scheduler._provider_pool_cfg["routing"] == "least_latency"

    def test_orchestrator_passes_direction_planner_config(self):
        from quantaalpha.continuous.scheduler import (
            SchedulerConfig,
            MiningConfig,
            DirectionPlannerConfig,
        )
        from quantaalpha.continuous.orchestrator import MiningOrchestrator

        config = SchedulerConfig(
            mining=MiningConfig(
                pipeline_mode=True,
                direction_planner=DirectionPlannerConfig(
                    enabled=True,
                    diversity_window=5,
                ),
            ),
        )
        orchestrator = MiningOrchestrator(config=config)
        scheduler = orchestrator.mining_scheduler
        assert scheduler._direction_planner_cfg["enabled"] is True
        assert scheduler._direction_planner_cfg["diversity_window"] == 5

    def test_orchestrator_passes_orchestration_config(self):
        """MiningOrchestrator passes orchestration config to DefaultMiningScheduler."""
        from unittest.mock import patch
        from quantaalpha.continuous.scheduler import (
            SchedulerConfig,
            MiningConfig,
            OrchestrationConfig,
            OrchestrationConditionConfig,
            OrchestrationNodeConfig,
            OrchestrationTransitionConfig,
        )
        from quantaalpha.continuous.orchestrator import MiningOrchestrator

        config = SchedulerConfig(
            mining=MiningConfig(
                pipeline_mode=True,
                orchestration=OrchestrationConfig(
                    enabled=True,
                    mode="conditional_flow",
                    max_steps_per_cycle=8,
                    start_node="original",
                    conditions=[
                        OrchestrationConditionConfig(
                            name="enough_parents",
                            type="threshold",
                            metric="active_parents",
                            operator="gte",
                            value=2,
                        ),
                    ],
                    nodes=[
                        OrchestrationNodeConfig(
                            id="original",
                            kind="action",
                            action="original",
                            next=[OrchestrationTransitionConfig(goto="stop")],
                        ),
                        OrchestrationNodeConfig(
                            id="mutation",
                            kind="action",
                            action="mutation",
                            next=[OrchestrationTransitionConfig(goto="stop")],
                        ),
                    ],
                ),
            ),
        )

        # Mock DefaultMiningScheduler to capture the init arguments
        with patch("quantaalpha.continuous.implementations.DefaultMiningScheduler") as mock_scheduler:
            mock_instance = mock_scheduler.return_value
            orchestrator = MiningOrchestrator(config=config)
            scheduler = orchestrator.mining_scheduler

            # Verify DefaultMiningScheduler was called with orchestration_cfg
            mock_scheduler.assert_called_once()
            call_kwargs = mock_scheduler.call_args[1]

            assert "orchestration_cfg" in call_kwargs
            orch_cfg = call_kwargs["orchestration_cfg"]
            assert orch_cfg["enabled"] is True
            assert orch_cfg["mode"] == "conditional_flow"
            assert orch_cfg["max_steps_per_cycle"] == 8
            assert orch_cfg["start_node"] == "original"
            assert len(orch_cfg["conditions"]) == 1
            assert orch_cfg["conditions"][0]["name"] == "enough_parents"
            assert len(orch_cfg["nodes"]) == 2
            assert orch_cfg["nodes"][0]["id"] == "original"
            assert orch_cfg["nodes"][1]["id"] == "mutation"


class TestOrchestrationPhase1Forwarding:
    """Tests for Phase 1 exact config shape forwarding through orchestrator to scheduler."""

    def test_orchestrator_forwards_phase1_orchestration_shape(self):
        """MiningOrchestrator forwards Phase 1 orchestration config shape to DefaultMiningScheduler."""
        from unittest.mock import patch
        from quantaalpha.continuous.scheduler import (
            SchedulerConfig,
            MiningConfig,
            OrchestrationConfig,
            OrchestrationMetricsConfig,
            OrchestrationConditionConfig,
            OrchestrationNodeConfig,
            OrchestrationTransitionConfig,
        )
        from quantaalpha.continuous.orchestrator import MiningOrchestrator

        config = SchedulerConfig(
            mining=MiningConfig(
                pipeline_mode=True,
                orchestration=OrchestrationConfig(
                    enabled=True,
                    mode="conditional_flow",
                    max_steps_per_cycle=8,
                    start_node="original",
                    metrics=OrchestrationMetricsConfig(
                        min_pass_rate_for_crossover=0.25,
                        min_active_parents_for_crossover=3,
                        min_diversity_score=0.15,
                        max_consecutive_failures=3,
                    ),
                    conditions=[
                        OrchestrationConditionConfig(
                            name="enough_parents",
                            type="threshold",
                            metric="active_parents",
                            operator="gte",
                            value=2,
                        )
                    ],
                    nodes=[
                        OrchestrationNodeConfig(
                            id="original",
                            kind="action",
                            action="original",
                            next=[OrchestrationTransitionConfig(condition="enough_parents", goto="stop")],
                        )
                    ],
                ),
            ),
        )

        # Mock DefaultMiningScheduler to capture the init arguments
        with patch("quantaalpha.continuous.implementations.DefaultMiningScheduler") as mock_scheduler:
            mock_instance = mock_scheduler.return_value
            orchestrator = MiningOrchestrator(config=config)
            scheduler = orchestrator.mining_scheduler

            # Verify DefaultMiningScheduler was called with orchestration_cfg
            mock_scheduler.assert_called_once()
            call_kwargs = mock_scheduler.call_args[1]

            assert "orchestration_cfg" in call_kwargs
            orch_cfg = call_kwargs["orchestration_cfg"]
            # Phase 1 target shape fields
            assert orch_cfg["enabled"] is True
            assert orch_cfg["mode"] == "conditional_flow"
            assert orch_cfg["max_steps_per_cycle"] == 8
            assert orch_cfg["start_node"] == "original"
            assert orch_cfg["metrics"]["min_pass_rate_for_crossover"] == 0.25
            assert len(orch_cfg["conditions"]) == 1
            assert orch_cfg["conditions"][0]["name"] == "enough_parents"
            assert len(orch_cfg["nodes"]) == 1
            assert orch_cfg["nodes"][0]["id"] == "original"
            assert orch_cfg["nodes"][0]["kind"] == "action"
            assert len(orch_cfg["nodes"][0]["next"]) == 1
            assert orch_cfg["nodes"][0]["next"][0]["if"] == "enough_parents"
            assert orch_cfg["nodes"][0]["next"][0]["goto"] == "stop"

    def test_real_scheduler_init_accepts_phase1_orchestration_cfg(self):
        """Real DefaultMiningScheduler.__init__ accepts Phase 1 orchestration_cfg without raising."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        orchestration_cfg = {
            "enabled": True,
            "mode": "conditional_flow",
            "max_steps_per_cycle": 6,
            "start_node": "original",
            "metrics": {
                "min_pass_rate_for_crossover": 0.20,
                "min_active_parents_for_crossover": 2,
                "min_diversity_score": 0.10,
                "max_consecutive_failures": 2,
            },
            "conditions": [],
            "nodes": [],
        }

        # This should not raise
        scheduler = DefaultMiningScheduler(
            pipeline_mode=True,
            orchestration_cfg=orchestration_cfg,
        )

        assert scheduler._orchestration_cfg["enabled"] is True
        assert scheduler._orchestration_cfg["mode"] == "conditional_flow"
        assert scheduler._orchestration_cfg["max_steps_per_cycle"] == 6
        assert scheduler._orchestration_cfg["start_node"] == "original"


class TestProviderPoolYamlRouting:
    """Test that ProviderPool routing is taken from YAML config, not hardcoded."""

    def test_provider_pool_uses_yaml_routing(self):
        """Test that _get_or_build_provider_pool respects routing from config."""
        from types import SimpleNamespace

        from quantaalpha.continuous.implementations import DefaultMiningScheduler
        from quantaalpha.llm.provider_pool import ProviderPool

        provider_pool_cfg = {
            "enabled": True,
            "routing": "round_robin",
            "providers": [
                {"name": "p1", "api_keys": ["k1"], "model": "m1"},
                {"name": "p2", "api_keys": ["k2"], "model": "m2"},
            ],
        }

        # Create a minimal object that has the attribute _get_or_build_provider_pool expects
        mock_scheduler = SimpleNamespace(
            _provider_pool_cfg=provider_pool_cfg,
            _cached_provider_pool=None,
        )
        # Bind the real method to our mock
        mock_scheduler._get_or_build_provider_pool = (
            DefaultMiningScheduler._get_or_build_provider_pool.__get__(mock_scheduler)
        )

        pool: ProviderPool = mock_scheduler._get_or_build_provider_pool()

        assert pool is not None
        assert pool.routing == "round_robin", (
            f"Expected routing='round_robin' from config, got routing='{pool.routing}'"
        )

    def test_provider_pool_defaults_to_least_latency_when_routing_not_configured(self):
        """Test that ProviderPool defaults to least_latency when routing is not in config."""
        from types import SimpleNamespace

        from quantaalpha.continuous.implementations import DefaultMiningScheduler
        from quantaalpha.llm.provider_pool import ProviderPool

        provider_pool_cfg = {
            "enabled": True,
            # Note: no "routing" key - should default to least_latency
            "providers": [
                {"name": "p1", "api_keys": ["k1"], "model": "m1"},
            ],
        }

        scheduler = SimpleNamespace()
        scheduler._provider_pool_cfg = provider_pool_cfg
        scheduler._provider_pool = None
        scheduler._get_or_build_provider_pool = DefaultMiningScheduler._get_or_build_provider_pool.__get__(scheduler)

        pool = scheduler._get_or_build_provider_pool()

        assert pool.routing == "least_latency", f"Expected default routing 'least_latency', got {pool.routing}"

    def test_original_action_registers_provider_pool_before_alpha_agent_loop(self, monkeypatch):
        """Original orchestration path must register ProviderPool for nested APIBackend retry switching."""
        import sys
        from types import ModuleType
        from unittest.mock import MagicMock, patch

        from quantaalpha.continuous.implementations import DefaultMiningScheduler
        from quantaalpha.llm.client import get_default_provider_pool, set_default_provider_pool

        provider_pool_cfg = {
            "enabled": True,
            "routing": "round_robin",
            "providers": [
                {"name": "p1", "api_keys": ["k1"], "model": "m1"},
                {"name": "p2", "api_keys": ["k2"], "model": "m2"},
            ],
        }
        scheduler = DefaultMiningScheduler(
            pipeline_mode=True,
            provider_pool_cfg=provider_pool_cfg,
            state_cfg={"steps_per_mining": 1},
            orchestration_cfg={"enabled": True},
        )

        loop = MagicMock()
        loop._get_successful_factor_ids.return_value = []
        fake_loop_module = ModuleType("quantaalpha.pipeline.loop")
        fake_loop_module.AlphaAgentLoop = MagicMock(return_value=loop)
        monkeypatch.setitem(sys.modules, "quantaalpha.pipeline.loop", fake_loop_module)
        set_default_provider_pool(None)
        try:
            with patch("quantaalpha.pipeline.loop.AlphaAgentLoop", return_value=loop):
                scheduler._execute_original_action({}, "original")

            pool = get_default_provider_pool()
            assert pool is not None
            assert pool.routing == "round_robin"
        finally:
            set_default_provider_pool(None)
