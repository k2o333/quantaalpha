from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

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
    ic: float = 0.01,
    annualized_return: float = 0.08,
    information_ratio: float = 0.7,
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
            "backtest_results_json": json.dumps(
                {
                    "IC": ic,
                    "Rank IC": rank_ic,
                    "annualized_return": annualized_return,
                    "information_ratio": information_ratio,
                }
            ),
        }
    )


def _runtime_trajectory(trajectory_id: str, expression: str, rank_ic: float) -> StrategyTrajectory:
    return StrategyTrajectory(
        trajectory_id=trajectory_id,
        direction_id=0,
        round_idx=0,
        phase=RoundPhase.ORIGINAL,
        factors=[{"name": trajectory_id, "expression": expression}],
        backtest_metrics={
            "IC": rank_ic / 2,
            "RankIC": rank_ic,
            "annualized_return": rank_ic * 2,
            "information_ratio": rank_ic * 10,
        },
        extra_info={"evaluation": {"status": "active"}, "source": "trajectory_pool"},
    )


def test_adaptive_mutation_waits_for_minimum_rounds() -> None:
    controller = EvolutionController(
        EvolutionConfig(
            mutation_mode_schedule="adaptive",
            adaptive_min_rounds=3,
            mutation_mode_weights={"exploit": 0.75, "explore": 0.25},
        )
    )
    controller._current_round = 2

    assert controller._effective_mutation_mode_weights() == {"exploit": 0.75, "explore": 0.25}


def test_adaptive_mutation_boosts_explore_after_stagnation() -> None:
    controller = EvolutionController(
        EvolutionConfig(
            mutation_mode_schedule="adaptive",
            adaptive_min_rounds=3,
            adaptive_stagnation_rounds=3,
            adaptive_explore_boost=0.15,
            mutation_mode_weights={"exploit": 0.75, "explore": 0.25},
        )
    )
    for round_idx in range(3):
        controller.pool.add(
            StrategyTrajectory(
                trajectory_id=f"rejected_{round_idx}",
                direction_id=round_idx,
                round_idx=round_idx,
                phase=RoundPhase.ORIGINAL,
                factors=[{"expression": f"RANK($close)+{round_idx}"}],
                extra_info={"evaluation": {"status": "rejected"}},
            )
        )
    controller._current_round = 3

    weights = controller._effective_mutation_mode_weights()

    assert weights["explore"] > 0.25


def test_same_round_diversity_penalizes_weaker_candidate() -> None:
    controller = EvolutionController(
        EvolutionConfig(
            diversity_enforcement_enabled=True,
            diversity_similarity_threshold=0.90,
            diversity_penalty=0.10,
        )
    )
    strong = _runtime_trajectory("strong", "TS_MEAN($close, 10)", 0.05)
    weak = _runtime_trajectory("weak", "TS_MEAN($close, 20)", 0.01)
    strong.extra_info["quality_score"] = 0.80
    weak.extra_info["quality_score"] = 0.40

    controller.apply_same_round_diversity_penalty([strong, weak])

    assert "diversity_diagnostics" not in strong.extra_info
    assert weak.extra_info["quality_score"] == pytest.approx(0.30)
    assert weak.extra_info["diversity_diagnostics"][0]["matched_trajectory_id"] == "strong"


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


def test_historical_parent_injection_uses_trajectory_pool_when_library_has_no_active(tmp_path):
    store_path = tmp_path / "factorlib"
    _write_factor(store_path, factor_id="candidate_high", expression="RANK(volume)", status="candidate", rank_ic=0.08)

    controller = EvolutionController(
        EvolutionConfig(
            num_directions=1,
            mutation_enabled=False,
            crossover_enabled=True,
            parquet_library_dir=str(store_path),
            historical_parent_sources={
                "trajectory_pool": {"enabled": True, "min_rank_ic": 0.03, "count": 3},
                "factor_library": {"enabled": True, "statuses": ["active"], "min_rank_ic": 0.03, "count": 3},
            },
        )
    )
    controller.pool.add(_runtime_trajectory("pool_high_a", "RANK(close)", 0.052))
    controller.pool.add(_runtime_trajectory("pool_high_b", "RANK(open)", 0.041))
    controller.pool.add(_runtime_trajectory("pool_high_c", "RANK(high)", 0.035))

    historical = controller._load_historical_parent_candidates([])

    assert [parent.trajectory_id for parent in historical] == ["pool_high_a", "pool_high_b", "pool_high_c"]
    assert all(parent.extra_info.get("source") == "trajectory_pool" for parent in historical)


def test_historical_parent_injection_dedupes_sources_by_best_rank_ic(tmp_path):
    store_path = tmp_path / "factorlib"
    _write_factor(store_path, factor_id="library_weaker", expression="RANK(close)", rank_ic=0.04)

    controller = EvolutionController(
        EvolutionConfig(
            num_directions=1,
            mutation_enabled=False,
            crossover_enabled=True,
            parquet_library_dir=str(store_path),
            historical_parent_sources={
                "trajectory_pool": {"enabled": True, "min_rank_ic": 0.03, "count": 3},
                "factor_library": {"enabled": True, "statuses": ["active"], "min_rank_ic": 0.03, "count": 3},
            },
        )
    )
    controller.pool.add(_runtime_trajectory("pool_stronger", "RANK(close)", 0.06))

    historical = controller._load_historical_parent_candidates([])

    assert [parent.trajectory_id for parent in historical] == ["pool_stronger"]
    assert historical[0].get_primary_metric() == 0.06


def test_historical_parent_prompt_text_includes_core_metrics(tmp_path):
    store_path = tmp_path / "factorlib"
    _write_factor(
        store_path,
        factor_id="library_metrics",
        expression="RANK(close)",
        rank_ic=0.0456,
        ic=0.0123,
        annualized_return=0.0789,
        information_ratio=1.25,
    )
    controller = EvolutionController(
        EvolutionConfig(
            parquet_library_dir=str(store_path),
            historical_parent_sources={
                "factor_library": {"enabled": True, "statuses": ["active"], "min_rank_ic": 0.03, "count": 1},
            },
        )
    )

    parent = controller._load_historical_parent_candidates([])[0]
    text = parent.to_summary_text()

    assert "IC=0.0123" in text
    assert "RankIC=0.0456" in text
    assert "annualized_return=0.0789" in text
    assert "information_ratio=1.2500" in text
