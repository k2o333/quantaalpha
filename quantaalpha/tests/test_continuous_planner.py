"""Tests for ContinuousDirectionPlanner."""

from unittest.mock import MagicMock, patch

import pytest


class TestDirectionCategory:
    """Tests for direction category detection."""

    def test_detect_price_volume_category(self):
        from quantaalpha.continuous.planner import detect_category

        assert detect_category("short-term momentum reversal") == "price_volume"
        assert detect_category("volatility breakout") == "price_volume"

    def test_detect_fundamental_category(self):
        from quantaalpha.continuous.planner import detect_category

        assert detect_category("earnings quality factor") == "fundamental"
        assert detect_category("dividend yield factor") == "fundamental"

    def test_detect_default_category(self):
        from quantaalpha.continuous.planner import detect_category

        assert detect_category("unknown strategy xyz") == "price_volume"  # default


class TestContinuousDirectionPlanner:
    """Tests for ContinuousDirectionPlanner."""

    def _make_planner(self, **kwargs):
        from quantaalpha.continuous.planner import ContinuousDirectionPlanner

        mock_failure_tracker = MagicMock()
        mock_failure_tracker.get_recently_failed_directions.return_value = []

        mock_pool = MagicMock()
        mock_pool.trajectories = []

        return ContinuousDirectionPlanner(
            failure_tracker=mock_failure_tracker,
            trajectory_pool=mock_pool,
            diversity_window=3,
            last_failed_within_hours=48,
            **kwargs,
        )

    def test_planner_initializes(self):
        planner = self._make_planner()
        assert planner._used_categories == []

    def test_record_used_category(self):
        planner = self._make_planner()
        planner.record_used_category("price_volume")
        assert "price_volume" in planner._used_categories

    def test_plan_next_direction_returns_result(self):
        """Returns a DirectionPlanResult."""
        planner = self._make_planner()

        with patch("quantaalpha.pipeline.planning.generate_parallel_directions") as mock_gen:
            mock_gen.return_value = ["momentum reversal"]

            result = planner.plan_next_direction()
            assert result.direction == "momentum reversal"
            assert result.category == "price_volume"

    def test_plan_next_direction_excludes_failed(self):
        """Excludes recently failed directions."""
        from quantaalpha.continuous.planner import ContinuousDirectionPlanner

        mock_failure_tracker = MagicMock()
        mock_failure_tracker.get_recently_failed_directions.return_value = ["momentum reversal"]

        mock_pool = MagicMock()
        mock_pool.trajectories = []

        planner = ContinuousDirectionPlanner(
            failure_tracker=mock_failure_tracker,
            trajectory_pool=mock_pool,
            diversity_window=3,
            last_failed_within_hours=48,
        )

        with patch("quantaalpha.pipeline.planning.generate_parallel_directions") as mock_gen:
            mock_gen.return_value = ["momentum reversal", "mean reversion"]

            result = planner.plan_next_direction()
            # Should skip "momentum reversal" (failed) and pick "mean reversion"
            assert result.direction == "mean reversion"

    def test_plan_next_direction_respects_diversity(self):
        """Excludes recently used categories when diversity window is full."""
        from quantaalpha.continuous.planner import ContinuousDirectionPlanner

        mock_failure_tracker = MagicMock()
        mock_failure_tracker.get_recently_failed_directions.return_value = []

        mock_pool = MagicMock()
        mock_pool.trajectories = []

        planner = ContinuousDirectionPlanner(
            failure_tracker=mock_failure_tracker,
            trajectory_pool=mock_pool,
            diversity_window=3,
            last_failed_within_hours=48,
        )
        # Fill diversity window with price_volume
        planner._used_categories = ["price_volume", "price_volume", "price_volume"]

        with patch("quantaalpha.pipeline.planning.generate_parallel_directions") as mock_gen:
            # First candidate is price_volume (excluded), second is fundamental (allowed)
            mock_gen.return_value = ["momentum reversal", "earnings surprise"]

            result = planner.plan_next_direction()
            assert result.direction == "earnings surprise"
            assert result.category == "fundamental"

    def test_plan_next_direction_force_different_category(self):
        """force_different_category excludes the most recent category."""
        from quantaalpha.continuous.planner import ContinuousDirectionPlanner

        mock_failure_tracker = MagicMock()
        mock_failure_tracker.get_recently_failed_directions.return_value = []

        mock_pool = MagicMock()
        mock_pool.trajectories = []

        planner = ContinuousDirectionPlanner(
            failure_tracker=mock_failure_tracker,
            trajectory_pool=mock_pool,
            diversity_window=3,
            last_failed_within_hours=48,
        )
        planner._used_categories = ["price_volume"]

        with patch("quantaalpha.pipeline.planning.generate_parallel_directions") as mock_gen:
            mock_gen.return_value = ["momentum reversal", "earnings surprise"]

            result = planner.plan_next_direction(force_different_category=True)
            assert result.direction == "earnings surprise"

    def test_plan_next_direction_fallback_on_error(self):
        """Returns fallback direction when planning fails."""
        planner = self._make_planner()

        with patch("quantaalpha.pipeline.planning.generate_parallel_directions", side_effect=Exception("LLM error")):
            result = planner.plan_next_direction()
            assert result.source == "fallback"
            assert result.direction is not None
