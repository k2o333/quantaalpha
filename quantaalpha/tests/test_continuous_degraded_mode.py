"""Tests for degraded mode and direction planner integration."""

from unittest.mock import MagicMock, patch

import pytest


class TestDegradedMode:
    """Tests for degraded_mode in DefaultMiningScheduler."""

    def test_scheduler_accepts_degraded_mode(self):
        """DefaultMiningScheduler accepts degraded_mode parameter."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler(
            pipeline_mode=True,
            degraded_mode=True,
        )
        assert scheduler._degraded_mode is True

    def test_scheduler_degraded_mode_defaults_false(self):
        """DefaultMiningScheduler defaults degraded_mode to False."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler(pipeline_mode=True)
        assert scheduler._degraded_mode is False


class TestDirectionPlannerIntegration:
    """Tests for direction planner integration."""

    def test_scheduler_accepts_direction_planner_cfg(self):
        """DefaultMiningScheduler accepts direction_planner_cfg."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler(
            pipeline_mode=True,
            direction_planner_cfg={"enabled": True, "diversity_window": 5},
        )
        assert scheduler._direction_planner_cfg["enabled"] is True
        assert scheduler._direction_planner_cfg["diversity_window"] == 5

    def test_scheduler_direction_planner_defaults(self):
        """DefaultMiningScheduler defaults direction_planner_cfg to empty."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler(pipeline_mode=True)
        assert scheduler._direction_planner_cfg == {}
