from __future__ import annotations

import unittest
from pathlib import Path
import sys

# Add PKG_ROOT to sys.path
ROOT = Path(__file__).resolve().parents[1]
PKG_ROOT = ROOT / "quantaalpha"
if str(PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quantaalpha.pipeline.evolution.trajectory import StrategyTrajectory, RoundPhase, select_parent_factors

class TestPlanningConstraints(unittest.TestCase):
    def test_trajectory_selection_with_status_constraint(self):
        # Good active factor
        t1 = StrategyTrajectory(
            trajectory_id="t1", direction_id=0, round_idx=1,
            phase=RoundPhase.MUTATION,
            backtest_metrics={"RankIC": 0.05},
            extra_info={"evaluation": {"status": "active", "stability_score": 0.8}}
        )
        # Better metrics but degraded status
        t2 = StrategyTrajectory(
            trajectory_id="t2", direction_id=1, round_idx=1,
            phase=RoundPhase.MUTATION,
            backtest_metrics={"RankIC": 0.10},
            extra_info={"evaluation": {"status": "degraded", "stability_score": 0.25}}
        )
        # Poor metrics, active status
        t3 = StrategyTrajectory(
            trajectory_id="t3", direction_id=2, round_idx=1,
            phase=RoundPhase.MUTATION,
            backtest_metrics={"RankIC": 0.02},
            extra_info={"evaluation": {"status": "active", "stability_score": 0.6}}
        )
        
        # Should prefer t1 over t2 despite t2 having higher RankIC, 
        # because t2 is degraded.
        # However, it depends on how select_parent_factors is implemented.
        # Let's see what it does.
        selected = select_parent_factors([t1, t2, t3], n=1)
        self.assertEqual(selected[0].trajectory_id, "t1")

    def test_trajectory_selection_rank_ic_threshold(self):
        # All active, select by RankIC
        t1 = StrategyTrajectory(
            trajectory_id="t1", direction_id=0, round_idx=1,
            phase=RoundPhase.MUTATION,
            backtest_metrics={"RankIC": 0.05},
            extra_info={"evaluation": {"status": "active", "stability_score": 0.8}}
        )
        t2 = StrategyTrajectory(
            trajectory_id="t2", direction_id=1, round_idx=1,
            phase=RoundPhase.MUTATION,
            backtest_metrics={"RankIC": 0.06},
            extra_info={"evaluation": {"status": "active", "stability_score": 0.8}}
        )
        selected = select_parent_factors([t1, t2], n=1)
        self.assertEqual(selected[0].trajectory_id, "t2")

if __name__ == "__main__":
    unittest.main()
