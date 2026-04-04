"""Tests for ContinuousStateManager - cross-cycle state persistence."""

import json
import os
import tempfile
from pathlib import Path

import pytest


class TestContinuousStateManager:
    """Tests for ContinuousStateManager save/load/purge."""

    def test_state_manager_save_and_load(self):
        """StateManager saves and loads trajectory pool atomically."""
        from quantaalpha.continuous.state import ContinuousStateManager
        from quantaalpha.pipeline.evolution.trajectory import (
            StrategyTrajectory,
            RoundPhase,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            pool_path = os.path.join(tmpdir, "trajectory_pool.json")
            manager = ContinuousStateManager(
                pool_save_path=pool_path,
                max_pool_size=100,
            )
            # Load should succeed even if file doesn't exist (fresh start)
            pool = manager.load_pool()
            assert pool is not None

            # Add a mock trajectory and save
            traj = StrategyTrajectory(
                trajectory_id="test_001",
                direction_id=0,
                round_idx=0,
                phase=RoundPhase.ORIGINAL,
                hypothesis="test hypothesis",
                factors=[],
                backtest_metrics={"RankIC": 0.05},
                feedback="good",
                parent_ids=[],
                extra_info={"evaluation": {"status": "active", "stability_score": 0.6}},
            )
            pool.add(traj)
            manager.save_pool(pool)

            # Verify file exists
            assert os.path.exists(pool_path)

            # Load and verify trajectory preserved
            manager2 = ContinuousStateManager(pool_save_path=pool_path, max_pool_size=100)
            pool2 = manager2.load_pool()
            assert len(pool2.get_all()) == 1
            assert pool2.get_all()[0].trajectory_id == "test_001"

    def test_state_manager_pool_cleanup(self):
        """StateManager purges lowest-ranking trajectories when pool exceeds max size."""
        from quantaalpha.continuous.state import ContinuousStateManager
        from quantaalpha.pipeline.evolution.trajectory import (
            StrategyTrajectory,
            RoundPhase,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            pool_path = os.path.join(tmpdir, "trajectory_pool.json")
            manager = ContinuousStateManager(
                pool_save_path=pool_path,
                max_pool_size=3,
            )

            # Add 5 trajectories with different metrics
            for i in range(5):
                traj = StrategyTrajectory(
                    trajectory_id=f"traj_{i:03d}",
                    direction_id=0,
                    round_idx=0,
                    phase=RoundPhase.ORIGINAL,
                    hypothesis=f"hypothesis {i}",
                    factors=[],
                    backtest_metrics={"RankIC": 0.01 * (i + 1)},
                    feedback=f"feedback {i}",
                    parent_ids=[],
                    extra_info={"evaluation": {"status": "active", "stability_score": 0.5}},
                )
                manager._pool = manager.load_pool()
                manager._pool.add(traj)

            manager.save_pool()
            manager.purge_pool()

            # Should have only 3 (max_pool_size) trajectories
            assert len(manager._pool.get_all()) == 3
            # Should keep the highest-ranking ones
            remaining_ids = {t.trajectory_id for t in manager._pool.get_all()}
            assert "traj_004" in remaining_ids  # RankIC=0.05
            assert "traj_003" in remaining_ids  # RankIC=0.04
            assert "traj_002" in remaining_ids  # RankIC=0.03
            assert "traj_000" not in remaining_ids  # RankIC=0.01, purged
            assert "traj_001" not in remaining_ids  # RankIC=0.02, purged

    def test_state_manager_handles_corrupted_file(self):
        """StateManager detects corrupted pool file and starts fresh."""
        from quantaalpha.continuous.state import ContinuousStateManager

        with tempfile.TemporaryDirectory() as tmpdir:
            pool_path = os.path.join(tmpdir, "trajectory_pool.json")
            # Write corrupted content
            with open(pool_path, "w") as f:
                f.write("{invalid json!!!")

            manager = ContinuousStateManager(
                pool_save_path=pool_path,
                max_pool_size=100,
            )
            pool = manager.load_pool()
            assert pool is not None
            # Corrupted file should be backed up
            assert os.path.exists(pool_path + ".corrupted")

    def test_state_manager_get_failure_tracker(self):
        """StateManager creates a FailureTracker."""
        from quantaalpha.continuous.state import ContinuousStateManager
        from quantaalpha.factors.failure_tracker import FactorFailureTracker

        manager = ContinuousStateManager(
            pool_save_path="/tmp/test_pool.json",
            max_pool_size=100,
        )
        tracker = manager.get_failure_tracker()
        assert isinstance(tracker, FactorFailureTracker)
