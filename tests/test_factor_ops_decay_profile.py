from __future__ import annotations

import polars as pl
import pytest
from quantaalpha.factor_ops.eval.decay_profile import DecayProfileComputer, DecayProfileResult
from quantaalpha.factor_ops.eval.health_scorer import HealthScorer


def test_decay_profile_computes_horizon_ic_and_half_life_contract() -> None:
    """Decay Profile 输出半衰期、最优周期、衰减分类和 horizon IC。"""
    factor_values = pl.DataFrame(
        {
            "date": ["2026-05-01"] * 4 + ["2026-05-02"] * 4,
            "stock_id": ["A", "B", "C", "D"] * 2,
            "factor_value": [1.0, 2.0, 3.0, 4.0, 1.0, 2.0, 3.0, 4.0],
        }
    )
    returns = pl.DataFrame(
        {
            "date": ["2026-05-01"] * 4 + ["2026-05-02"] * 4,
            "stock_id": ["A", "B", "C", "D"] * 2,
            "return_t_plus_1": [0.01, 0.02, 0.03, 0.04, 0.01, 0.02, 0.03, 0.04],
            "return_t_plus_2": [0.01, 0.02, 0.04, 0.03, 0.01, 0.02, 0.04, 0.03],
            "return_t_plus_5": [0.01, 0.03, 0.02, 0.04, 0.01, 0.03, 0.02, 0.04],
            "return_t_plus_10": [0.04, 0.03, 0.02, 0.01, 0.04, 0.03, 0.02, 0.01],
        }
    )

    result = DecayProfileComputer().compute(
        factor_values,
        returns,
        horizons=[1, 2, 5, 10],
    )

    assert isinstance(result, DecayProfileResult)
    assert result.horizon_ic == {1: 1.0, 2: 0.8, 5: 0.8, 10: -1.0}
    assert result.optimal_horizon == 1
    assert result.half_life_days == pytest.approx(30.0)
    assert result.decay_speed == "slow"
    assert result.ts_gru_allowed


def test_decay_profile_fast_decay_flags_ts_gru_filter() -> None:
    """半衰期 < 1 天时不允许进入 TS-GRU。"""
    result = DecayProfileComputer().summarize_horizon_ic({1: 0.02, 2: 0.10, 5: 0.01})

    assert result.half_life_days == pytest.approx(0.5)
    assert result.decay_speed == "fast"
    assert not result.ts_gru_allowed


def test_decay_profile_result_feeds_health_scorer_signal_persistence() -> None:
    """Decay Profile 的 half_life 可直接作为 HealthScorer 信号持续性输入。"""
    profile = DecayProfileComputer().summarize_horizon_ic({1: 0.08, 2: 0.06, 5: 0.03, 10: 0.02})
    health = HealthScorer().compute(
        "factor_001",
        signal_persistence=profile.to_health_input(),
    )

    assert health.health_confidence == 0.05
    assert health.health_breakdown["signal_persistence"] > 0
