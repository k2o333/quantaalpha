"""Tests for pipeline_mode integration in DefaultMiningScheduler."""

import pytest


class TestMiningSchedulerPipelineMode:
    """Tests for pipeline_mode parameter and behavior."""

    def test_mining_scheduler_pipeline_mode_init(self):
        """DefaultMiningScheduler accepts pipeline_mode parameter."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler(
            pipeline_mode=True,
            quality_gate_config={"min_ic": 0.02},
        )
        assert scheduler._pipeline_mode is True
        assert scheduler._quality_gate_config == {"min_ic": 0.02}

    def test_mining_scheduler_legacy_mode_unchanged(self):
        """DefaultMiningScheduler with pipeline_mode=False uses legacy path."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler(pipeline_mode=False)
        assert scheduler._pipeline_mode is False
        # Should have legacy methods
        assert hasattr(scheduler, "_generate_via_llm")
        assert hasattr(scheduler, "_generate_via_mutation")

    def test_mining_scheduler_pipeline_mode_defaults(self):
        """DefaultMiningScheduler defaults pipeline_mode to False."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler()
        assert scheduler._pipeline_mode is False

    def test_mining_scheduler_accepts_evolution_cfg(self):
        """DefaultMiningScheduler accepts evolution_cfg parameter."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler(
            pipeline_mode=True,
            evolution_cfg={"enabled": True, "max_rounds": 2},
        )
        assert scheduler._evolution_cfg == {"enabled": True, "max_rounds": 2}

    def test_mining_scheduler_accepts_state_cfg(self):
        """DefaultMiningScheduler accepts state_cfg parameter."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler(
            pipeline_mode=True,
            state_cfg={"steps_per_mining": 3, "max_pool_size": 200},
        )
        assert scheduler._state_cfg == {"steps_per_mining": 3, "max_pool_size": 200}
