from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quantaalpha.factors.parquet_library import ParquetFactorLibrary
from quantaalpha.pipeline.evolution.controller import EvolutionConfig, EvolutionController
from quantaalpha.pipeline.evolution.trajectory import RoundPhase, StrategyTrajectory


def _write_factor(
    store_path: Path,
    *,
    factor_id: str,
    expression: str,
    status: str = "active",
    rank_ic: float = 0.04,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    ParquetFactorLibrary(str(store_path)).write_factor_delta(
        {
            "factor_id": factor_id,
            "factor_name": f"name_{factor_id}",
            "factor_expression": expression,
            "factor_expression_normalized": expression,
            "expression_hash": factor_id,
            "evaluation_status": status,
            "created_at": now,
            "updated_at": now,
            "sequence": int(datetime.now(timezone.utc).timestamp() * 1_000_000),
            "op": "upsert",
            "tags_json": "{}",
            "metadata_json": json.dumps(
                {
                    "factor_description": f"description_{factor_id}",
                    "stability_score": 0.8,
                }
            ),
            "backtest_results_json": json.dumps({"Rank IC": rank_ic}),
        }
    )


def _runtime_trajectory(trajectory_id: str, expression: str, rank_ic: float) -> StrategyTrajectory:
    return StrategyTrajectory(
        trajectory_id=trajectory_id,
        direction_id=0,
        round_idx=0,
        phase=RoundPhase.ORIGINAL,
        factors=[{"name": trajectory_id, "expression": expression}],
        backtest_metrics={"RankIC": rank_ic},
    )


def test_crossover_injects_configured_parquet_active_parents(tmp_path):
    store_path = tmp_path / "factorlib"
    _write_factor(store_path, factor_id="hist_high", expression="RANK(close)", rank_ic=0.06)
    _write_factor(store_path, factor_id="hist_mid", expression="RANK(volume)", rank_ic=0.04)

    controller = EvolutionController(
        EvolutionConfig(
            num_directions=2,
            mutation_enabled=False,
            crossover_enabled=True,
            crossover_size=2,
            crossover_n=1,
            parquet_library_dir=str(store_path),
            historical_active_parent_count=2,
            historical_parent_min_rank_ic=0.02,
        )
    )
    controller.pool.add(_runtime_trajectory("runtime_a", "RANK(open)", 0.005))
    controller.pool.add(_runtime_trajectory("runtime_b", "RANK(high)", 0.004))

    controller._prepare_crossover_groups()

    assert controller._crossover_groups
    selected_ids = {parent.trajectory_id for parent in controller._crossover_groups[0]}
    assert "library:hist_high" in selected_ids
    assert any(parent.extra_info.get("source") == "parquet_library" for parent in controller._crossover_groups[0])


def test_historical_parent_injection_filters_status_metric_and_duplicates(tmp_path):
    store_path = tmp_path / "factorlib"
    _write_factor(store_path, factor_id="active_high", expression="RANK(close)", rank_ic=0.05)
    _write_factor(store_path, factor_id="stale_high", expression="RANK(volume)", status="stale", rank_ic=0.07)
    _write_factor(store_path, factor_id="active_low", expression="RANK(amount)", rank_ic=0.01)
    _write_factor(store_path, factor_id="duplicate_expr", expression="RANK(open)", rank_ic=0.09)

    controller = EvolutionController(
        EvolutionConfig(
            num_directions=1,
            mutation_enabled=False,
            crossover_enabled=True,
            parquet_library_dir=str(store_path),
            historical_active_parent_count=4,
            historical_parent_min_rank_ic=0.02,
        )
    )
    runtime = _runtime_trajectory("runtime_a", "RANK(open)", 0.005)

    historical = controller._load_historical_parent_candidates([runtime])

    assert [parent.trajectory_id for parent in historical] == ["library:active_high"]
    assert historical[0].get_primary_metric() == 0.05
    assert historical[0].factors[0]["expression"] == "RANK(close)"
