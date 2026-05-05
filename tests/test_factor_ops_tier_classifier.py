from __future__ import annotations

from quantaalpha.factor_ops.eval.tier_classifier import TierClassifier, TierResult


def test_tier_classifier_assigns_core_when_all_a_rules_pass() -> None:
    """A/core 需要高健康分、OOS 通过、低相关且近期无明显衰减。"""
    result = TierClassifier().classify(
        "factor_a",
        health_score=86.0,
        health_confidence=0.95,
        oos_ic=0.03,
        oos_icir=0.5,
        max_abs_corr=0.60,
        ic_history=[0.04] * 60 + [0.035] * 60,
    )

    assert isinstance(result, TierResult)
    assert result.tier == "A"
    assert result.ops_status == "core"
    assert result.weight_cap == 1.0
    assert result.ts_gru_group_softmax_cap == 1.0
    assert result.reasons == ["core rules passed"]


def test_tier_classifier_assigns_satellite_with_weight_limits() -> None:
    """B/satellite 使用 50% 权重上限。"""
    result = TierClassifier().classify(
        "factor_b",
        health_score=72.0,
        health_confidence=0.80,
        marginal_contribution=True,
        max_abs_corr=0.70,
    )

    assert result.tier == "B"
    assert result.ops_status == "satellite"
    assert result.weight_cap == 0.5
    assert result.ts_gru_group_softmax_cap == 0.5


def test_tier_classifier_confidence_shortfall_forces_watchlist() -> None:
    """置信度不足时即使健康分较高也进入 C/watchlist。"""
    result = TierClassifier(min_confidence=0.60).classify(
        "factor_c",
        health_score=75.0,
        health_confidence=0.40,
        marginal_contribution=True,
    )

    assert result.tier == "C"
    assert result.ops_status == "watchlist"
    assert "confidence below threshold" in result.reasons


def test_tier_classifier_assigns_retired_for_invalid_or_low_score() -> None:
    """健康分低、PIT 失败或严重数据问题进入 D/retired。"""
    result = TierClassifier().classify(
        "factor_d",
        health_score=55.0,
        health_confidence=0.80,
        pit_failed=True,
    )

    assert result.tier == "D"
    assert result.ops_status == "retired"
    assert result.weight_cap == 0.0
    assert "pit failed" in result.reasons


def test_tier_classifier_detects_recent_decay_for_core_rule() -> None:
    """最近 60 日 IC 均值较前 60 日下降 20% 以上，不能进入 core。"""
    result = TierClassifier().classify(
        "factor_decay",
        health_score=88.0,
        health_confidence=0.95,
        oos_ic=0.03,
        oos_icir=0.5,
        max_abs_corr=0.60,
        ic_history=[0.05] * 60 + [0.03] * 60,
    )

    assert result.tier == "B"
    assert result.ops_status == "satellite"
    assert "recent decay detected" in result.reasons
