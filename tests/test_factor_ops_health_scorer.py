from __future__ import annotations

import math

import polars as pl
from quantaalpha.factor_ops.eval.health_scorer import HealthScorer, HealthScoreResult


def test_health_scorer_computes_seven_dimension_contract() -> None:
    """HealthScorer 输出 health_score / confidence / breakdown 契约。"""
    result = HealthScorer().compute(
        "factor_001",
        prediction_power={"ic": 0.05, "rank_ic": 0.04},
        stability={"icir": 1.0},
        oos_ability={"oos_ic": 0.03},
        independence={"max_abs_corr": 0.70},
        tradability={"sharpe_after_cost": 1.5},
        recent_performance={"trend_slope": 0.10},
        signal_persistence={"half_life": 20.0},
    )

    assert isinstance(result, HealthScoreResult)
    assert result.factor_id == "factor_001"
    assert 0 <= result.health_score <= 100
    assert result.health_confidence == 1.0
    assert list(result.health_breakdown) == [
        "prediction_power",
        "stability",
        "oos_ability",
        "independence",
        "tradability",
        "recent_performance",
        "signal_persistence",
    ]
    assert 70 <= result.health_breakdown["prediction_power"] <= 74
    assert 94 <= result.health_breakdown["independence"] <= 96


def test_health_scorer_uses_weighted_confidence_and_no_weight_renormalization() -> None:
    """缺失维度按 0 分计入，confidence 使用原始权重可用比例。"""
    result = HealthScorer().compute(
        "factor_002",
        prediction_power={"ic": 0.05},
        stability=None,
        oos_ability={"oos_ic": 0.03},
        independence=None,
        tradability={"sharpe_after_cost": 1.2},
        recent_performance=None,
        signal_persistence={"half_life": 20.0},
    )

    expected_confidence = (25 + 15 + 10 + 5) / 100
    expected_score = sum(
        result.health_breakdown[dimension] * HealthScorer.DEFAULT_WEIGHTS[dimension] / 100
        for dimension in HealthScorer.DEFAULT_WEIGHTS
    )

    assert result.health_confidence == expected_confidence
    assert math.isclose(result.health_score, expected_score, abs_tol=1e-9)
    assert result.health_breakdown["stability"] == 0
    assert result.health_breakdown["independence"] == 0
    assert result.health_breakdown["recent_performance"] == 0


def test_health_scorer_sigmoid_parameters_match_plan() -> None:
    """评分映射使用 gap 文档 M1 的 sigmoid 参数。"""
    scorer = HealthScorer()

    assert 72 <= scorer.map_sigmoid(0.05, k=50, x0=0.03) <= 74
    assert 99 <= scorer.map_sigmoid(1.0, k=10, x0=0.5) <= 100
    assert 61 <= scorer.map_sigmoid(0.03, k=50, x0=0.02) <= 63
    assert 91 <= scorer.map_sigmoid(1.5, k=5, x0=1.0) <= 93
    assert 98 <= scorer.map_sigmoid(20.0, k=0.5, x0=10.0) <= 100


def test_health_scorer_recent_performance_accepts_daily_ic_dataframe() -> None:
    """近期状态可直接消费 monitor adapter 的 daily IC DataFrame。"""
    dates = [f"2026-05-{day:02d}" for day in range(1, 31)]
    daily_ic = pl.DataFrame(
        {
            "date": dates,
            "factor_id": ["factor_003"] * 30,
            "ic": [0.01 + day * 0.001 for day in range(30)],
            "rank_ic": [0.01] * 30,
        }
    )

    result = HealthScorer().compute(
        "factor_003",
        recent_performance={"daily_ic": daily_ic},
    )

    assert result.health_confidence == 0.10
    assert result.health_breakdown["recent_performance"] > 50


def test_health_scorer_tradability_can_compute_after_cost_sharpe() -> None:
    """可交易性支持按单边费率扣除 turnover 后计算年化 Sharpe。"""
    result = HealthScorer().compute(
        "factor_004",
        tradability={
            "returns": [0.01, 0.012, 0.008, 0.011],
            "turnover": [0.10, 0.20, 0.10, 0.20],
        },
    )

    assert result.health_confidence == 0.10
    assert result.health_breakdown["tradability"] > 90


def test_health_scorer_all_missing_inputs_returns_zero_score() -> None:
    """全维度缺失时分数和置信度均为 0。"""
    result = HealthScorer().compute("factor_empty")

    assert result.health_score == 0
    assert result.health_confidence == 0
    assert all(score == 0 for score in result.health_breakdown.values())
