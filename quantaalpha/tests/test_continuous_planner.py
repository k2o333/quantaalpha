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
        mock_pool.get_all.return_value = []

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
        mock_pool.get_all.return_value = []

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
        mock_pool.get_all.return_value = []

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
        mock_pool.get_all.return_value = []

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

    def test_get_seed_direction_uses_real_pool_api(self):
        """_get_seed_direction uses pool.get_all() not pool.trajectories."""
        import tempfile
        from pathlib import Path
        from quantaalpha.continuous.planner import ContinuousDirectionPlanner
        from quantaalpha.pipeline.evolution.trajectory import TrajectoryPool, StrategyTrajectory, RoundPhase
        from quantaalpha.factors.failure_tracker import FactorFailureTracker

        mock_failure_tracker = MagicMock()
        mock_failure_tracker.get_recently_failed_directions.return_value = []

        with tempfile.TemporaryDirectory() as tmpdir:
            pool_path = Path(tmpdir) / "pool.json"
            pool = TrajectoryPool(save_path=pool_path, fresh_start=True)

            traj = StrategyTrajectory(
                trajectory_id="seed_test_001",
                direction_id=0,
                round_idx=0,
                phase=RoundPhase.ORIGINAL,
                hypothesis="momentum based alpha signal",
                factors=[],
                backtest_metrics={"rank_ic": 0.05},
                feedback="good",
                parent_ids=[],
                extra_info={"evaluation": {"status": "active", "stability_score": 0.6}},
            )
            pool.add(traj)

            planner = ContinuousDirectionPlanner(
                failure_tracker=mock_failure_tracker,
                trajectory_pool=pool,
                diversity_window=3,
                last_failed_within_hours=48,
            )
            seed = planner._get_seed_direction()
            assert "momentum" in seed


class TestDirectionPlannerCaching:
    """Tests for Bug 6: DirectionPlanner should be cached across _get_mining_direction calls."""

    def test_direction_planner_cached_across_calls(self):
        """_get_mining_direction reuses the same DirectionPlanner instance.

        Bug 6: Previously each call created a new ContinuousDirectionPlanner,
        so _used_categories was reset every time and diversity constraints never triggered.
        """
        from unittest.mock import patch, MagicMock

        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler(
            pipeline_mode=True,
            direction_planner_cfg={"enabled": True, "diversity_window": 3, "last_failed_within_hours": 48},
            state_cfg={"log_root": "/tmp/test_planner_cache"},
        )

        # Mock state manager to return a valid failure tracker and pool
        mock_state_manager = MagicMock()
        mock_failure_tracker = MagicMock()
        mock_failure_tracker.get_recently_failed_directions.return_value = []
        mock_state_manager.get_failure_tracker.return_value = mock_failure_tracker

        mock_pool = MagicMock()
        mock_pool.get_all.return_value = []
        mock_state_manager.load_pool.return_value = mock_pool

        scheduler._state_manager = mock_state_manager

        # First call — should create and cache the planner
        result1 = scheduler._get_mining_direction()
        planner_after_first = scheduler._direction_planner

        assert planner_after_first is not None, "DirectionPlanner should be cached after first _get_mining_direction call"

        # Record a used category on the cached planner
        planner_after_first.record_used_category("price_volume")
        categories_after_first = list(planner_after_first._used_categories)

        # Second call — should REUSE the same planner instance
        result2 = scheduler._get_mining_direction()
        planner_after_second = scheduler._direction_planner

        assert planner_after_second is not None
        assert planner_after_second is planner_after_first, "DirectionPlanner should be the SAME instance across calls — _used_categories must accumulate for diversity constraints"
        # The category we recorded should still be present
        assert "price_volume" in planner_after_second._used_categories, f"Category 'price_volume' should persist in cached planner. Found: {planner_after_second._used_categories}"
