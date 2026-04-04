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
