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

    def test_pipeline_mode_run_mining_executes_pipeline_path(self):
        """pipeline_mode=True calls _run_pipeline_mining, not legacy path."""
        from unittest.mock import patch
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler(
            pipeline_mode=True,
            state_cfg={"steps_per_mining": 3, "max_pool_size": 100},
        )

        with patch.object(
            scheduler,
            "_run_pipeline_mining",
            return_value={
                "factors_generated": 2,
                "factors_validated": 2,
                "factors_added": 2,
                "factor_ids": ["factor_a", "factor_b"],
                "errors": [],
            },
        ) as mock_pipeline:
            result = scheduler.run_mining()

            mock_pipeline.assert_called_once()
            assert result.factors_generated == 2
            assert result.factors_added == 2
            assert result.factor_ids == ["factor_a", "factor_b"]

    def test_legacy_mode_run_mining_uses_generate_factors(self):
        """pipeline_mode=False calls _generate_factors, not pipeline path."""
        from unittest.mock import patch
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler(pipeline_mode=False)

        with patch.object(scheduler, "_retrieve_context", return_value="context"):
            with patch.object(scheduler, "_generate_factors", return_value=[]) as mock_generate:
                result = scheduler.run_mining()

                mock_generate.assert_called_once_with("context")
                assert result.factors_generated == 0
