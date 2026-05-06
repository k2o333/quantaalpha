from __future__ import annotations

import json

import polars as pl
from quantaalpha.factor_ops.acceptance import FactorOpsAcceptanceRunner
from quantaalpha.factor_ops.cli import build_status_summary


def test_factor_ops_status_summary_counts_ops_status_and_tier() -> None:
    registry = pl.DataFrame(
        {
            "factor_id": ["f1", "f2", "f3"],
            "metadata_json": [
                json.dumps({"ops": {"status": "core", "tier": "A"}}),
                json.dumps({"ops": {"status": "satellite", "tier": "B"}}),
                json.dumps({"ops": {"status": "watchlist", "tier": "C"}}),
            ],
        }
    )

    summary = build_status_summary(registry)

    assert summary == {
        "total_factors": 3,
        "status_counts": {"core": 1, "satellite": 1, "watchlist": 1},
        "tier_counts": {"A": 1, "B": 1, "C": 1},
        "model_eligible_count": 2,
    }


def test_factor_ops_status_summary_infers_ops_status_from_legacy_evaluation_status() -> None:
    registry = pl.DataFrame(
        {
            "factor_id": ["f1", "f2", "f3"],
            "evaluation_status": ["pending_validation", "active", "deprecated"],
            "metadata_json": ["{}", "{}", "{}"],
        }
    )

    summary = build_status_summary(registry)

    assert summary["status_counts"] == {"testing": 1, "candidate": 1, "retired": 1}
    assert summary["model_eligible_count"] == 1


def test_factor_ops_acceptance_runner_executes_minimal_closed_loop(tmp_path) -> None:
    result = FactorOpsAcceptanceRunner(tmp_path).run_minimal_loop(
        factor_id="factor_001",
        factor_values=pl.DataFrame(
            {
                "date": ["2026-05-01", "2026-05-01"],
                "stock_id": ["A", "B"],
                "factor_001": [1.0, 2.0],
            }
        ),
        returns=pl.DataFrame(
            {
                "date": ["2026-05-01", "2026-05-01"],
                "stock_id": ["A", "B"],
                "return_t_plus_1": [0.01, 0.02],
            }
        ),
    )

    assert result["gate_result"] == "pass"
    assert result["health_score"] >= 0
    assert result["tier"] in {"A", "B", "C", "D"}
    assert result["registry_update_success"]
    assert result["consumer_payload"]["factor_ids"] == ["factor_001"]
