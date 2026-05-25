from __future__ import annotations

from pathlib import Path


def test_trajectory_pool_reports_load_and_save_diagnostics(tmp_path: Path) -> None:
    from quantaalpha.pipeline.evolution.trajectory import RoundPhase, StrategyTrajectory, TrajectoryPool

    pool_path = tmp_path / "trajectory_pool.json"
    pool = TrajectoryPool(save_path=str(pool_path), fresh_start=False)

    assert pool.get_statistics()["load_diagnostics"] == {
        "save_path": str(pool_path),
        "exists": False,
        "fresh_start": False,
        "loaded_size": 0,
        "error": "",
    }

    pool.add(
        StrategyTrajectory(
            direction_id=1,
            phase=RoundPhase.ORIGINAL,
            round_idx=0,
            hypothesis="h",
            factors=[{"factor_name": "f", "expression": "$close / $open"}],
            backtest_metrics={"Rank IC": 0.04},
            feedback="ok",
            trajectory_id="traj_1",
        )
    )

    saved = pool.get_statistics()["save_diagnostics"]
    assert saved["save_path"] == str(pool_path)
    assert saved["saved_size"] == 1
    assert saved["error"] == ""

    reloaded = TrajectoryPool(save_path=str(pool_path), fresh_start=False)
    diagnostics = reloaded.get_statistics()["load_diagnostics"]

    assert diagnostics["save_path"] == str(pool_path)
    assert diagnostics["exists"] is True
    assert diagnostics["loaded_size"] == 1
    assert diagnostics["error"] == ""
