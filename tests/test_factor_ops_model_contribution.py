from __future__ import annotations

import polars as pl
from quantaalpha.factor_ops.contrib import (
    DowngradeRuleEngine,
    ModelContributionEvaluator,
    ModelContributionWorkflowRunner,
)


def test_model_contribution_evaluator_builds_baseline_candidate_and_drop_one_report() -> None:
    registry = pl.DataFrame(
        {
            "factor_id": ["f_core_1", "f_core_2", "f_sat", "f_candidate"],
            "ops_status": ["core", "core", "satellite", "candidate"],
            "health_score": [90.0, 85.0, 70.0, 55.0],
        }
    )
    metrics = {
        "baseline": {"rank_ic": 0.050, "icir": 1.2},
        "candidate_added": {"f_candidate": {"rank_ic": 0.056, "icir": 1.3}},
        "drop_one": {"f_candidate": {"rank_ic": 0.047, "icir": 1.1}},
        "shap_rank_pct": {"f_candidate": 0.35},
    }

    report = ModelContributionEvaluator(registry).generate_report(metrics)

    assert report.baseline["features"] == ["f_core_1", "f_core_2"]
    assert report.candidate_added[0]["factor_id"] == "f_candidate"
    assert report.candidate_added[0]["ic_improvement"] == 0.006
    assert report.drop_one["f_candidate"]["ic_change"] == 0.003
    assert report.to_dict()["candidate_pool"] == ["f_sat", "f_candidate"]


def test_model_contribution_evaluator_rejects_empty_core_pool() -> None:
    registry = pl.DataFrame({"factor_id": ["f1"], "ops_status": ["candidate"]})

    try:
        ModelContributionEvaluator(registry).generate_report({"baseline": {"rank_ic": 0.05}})
    except ValueError as exc:
        assert str(exc) == "core pool is empty"
    else:
        raise AssertionError("expected ValueError")


def test_downgrade_rule_engine_flags_low_contribution_and_ts_gru_failures() -> None:
    registry = pl.DataFrame(
        {
            "factor_id": ["f_core", "bad", "ts_gru_bad", "ts_gru_good"],
            "ops_status": ["core", "candidate", "candidate", "candidate"],
            "data_source_type": ["manual", "manual", "DL-Feature", "DL-Feature"],
        }
    )
    report = ModelContributionEvaluator(registry).generate_report(
        {
            "baseline": {"rank_ic": 0.05},
            "candidate_added": {
                "bad": {"rank_ic": 0.049},
                "ts_gru_bad": {"rank_ic": 0.049},
                "ts_gru_good": {"rank_ic": 0.052},
            },
            "drop_one": {
                "bad": {"rank_ic": 0.049},
                "ts_gru_bad": {"rank_ic": 0.049},
                "ts_gru_good": {"rank_ic": 0.046},
            },
            "shap_rank_pct": {"bad": 0.90, "ts_gru_bad": 0.70, "ts_gru_good": 0.70},
        }
    )

    suggestions = DowngradeRuleEngine().evaluate(report)
    by_factor = {suggestion.factor_id: suggestion for suggestion in suggestions}

    assert by_factor["bad"].new_status == "watchlist"
    assert "low shap rank" in by_factor["bad"].reason
    assert by_factor["ts_gru_bad"].new_status == "watchlist"
    assert "ts-gru contribution failed" in by_factor["ts_gru_bad"].reason
    assert "ts_gru_good" not in by_factor


def test_model_contribution_workflow_runner_executes_ablation_plan() -> None:
    registry = pl.DataFrame(
        {
            "factor_id": ["core_a", "candidate_bad"],
            "ops_status": ["core", "candidate"],
            "data_source_type": ["manual", "manual"],
        }
    )

    def metric_runner(features: tuple[str, ...]) -> dict[str, float]:
        if features == ("core_a",):
            return {"rank_ic": 0.050}
        if features == ("core_a", "candidate_bad"):
            return {"rank_ic": 0.051}
        return {"rank_ic": 0.049}

    result = ModelContributionWorkflowRunner(registry, metric_runner=metric_runner).run(
        shap_rank_pct={"candidate_bad": 0.9}
    )

    assert result.report.baseline["features"] == ["core_a"]
    assert result.report.candidate_added[0]["factor_id"] == "candidate_bad"
    assert result.report.drop_one["candidate_bad"]["ic_change"] == 0.001
    assert result.suggestions[0].factor_id == "candidate_bad"
