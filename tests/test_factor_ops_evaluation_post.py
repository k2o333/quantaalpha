from __future__ import annotations

from quantaalpha.factor_ops.post.evaluation import EvaluationPostProcessor, EvaluationPostResult


def test_evaluation_post_processor_builds_health_inputs_and_snapshot() -> None:
    """训练后评价指标转换为 HealthScorer 输入和 eval_snapshot。"""
    result = EvaluationPostProcessor().process(
        factor_id="factor_001",
        evaluation_metrics={
            "IC": 0.05,
            "Rank IC": 0.04,
            "ICIR": 1.2,
            "OOS IC": 0.03,
            "OOS ICIR": 0.6,
            "turnover_rate": 0.20,
            "sharpe_after_cost": 1.4,
        },
        stage_output_path="eval_snapshot/year=2026/month=05/factor_001.parquet",
    )

    assert isinstance(result, EvaluationPostResult)
    assert result.health_inputs["prediction_power"] == {"ic": 0.05, "rank_ic": 0.04}
    assert result.health_inputs["stability"] == {"icir": 1.2}
    assert result.health_inputs["oos_ability"] == {"oos_ic": 0.03, "oos_icir": 0.6}
    assert result.health_inputs["tradability"] == {"turnover": 0.2, "sharpe_after_cost": 1.4}
    assert 0 <= result.health_score <= 100
    assert result.eval_snapshot["factor_id"] == "factor_001"
    assert result.eval_snapshot["health_confidence"] > 0
    assert result.manifest_stage_output == {
        "evaluation_result_path": "eval_snapshot/year=2026/month=05/factor_001.parquet",
        "health_score": result.health_score,
    }


def test_evaluation_post_processor_handles_alternate_metric_names() -> None:
    """兼容 backtest/runner 和 trajectory 常见大小写字段。"""
    result = EvaluationPostProcessor().process(
        factor_id="factor_002",
        evaluation_metrics={
            "ic": 0.04,
            "rank_ic": 0.03,
            "icir": 0.8,
            "turnover": 0.15,
        },
    )

    assert result.health_inputs["prediction_power"] == {"ic": 0.04, "rank_ic": 0.03}
    assert result.health_inputs["stability"] == {"icir": 0.8}
    assert result.health_inputs["tradability"] == {"turnover": 0.15}
