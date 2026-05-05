from __future__ import annotations

import math

import polars as pl
import pytest
from quantaalpha.factor_ops.utils import (
    CorrelationEngine,
    DecayFitter,
    ICTrendCalculator,
    OutlierDetector,
    RankICCalculator,
    RegimeLabelGenerator,
)


def test_correlation_engine_computes_cross_section_spearman_pairs() -> None:
    df = pl.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-01", "2026-01-02", "2026-01-02"],
            "stock_id": ["A", "B", "A", "B"],
            "factor_1": [1.0, 2.0, 1.0, 2.0],
            "factor_2": [1.0, 2.0, 2.0, 1.0],
        }
    )

    result = CorrelationEngine().compute_spearman_matrix(df, window_days=2)

    assert result.columns == ["date", "factor_i", "factor_j", "correlation"]
    assert result.filter(pl.col("date") == "2026-01-01")["correlation"].item() == pytest.approx(1.0)
    assert result.filter(pl.col("date") == "2026-01-02")["correlation"].item() == pytest.approx(-1.0)


def test_correlation_engine_pairwise_aligns_candidate_and_pool() -> None:
    candidate = pl.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-01"],
            "stock_id": ["A", "B"],
            "candidate": [1.0, 2.0],
        }
    )
    pool = pl.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-01"],
            "stock_id": ["A", "B"],
            "pool_a": [1.0, 2.0],
            "pool_b": [2.0, 1.0],
        }
    )

    result = CorrelationEngine().compute_pairwise_corr(candidate, pool, window_days=1)

    assert set(result["pool_factor"].to_list()) == {"pool_a", "pool_b"}
    assert result.filter(pl.col("pool_factor") == "pool_a")["correlation"].item() == pytest.approx(1.0)
    assert result.filter(pl.col("pool_factor") == "pool_b")["correlation"].item() == pytest.approx(-1.0)


def test_rank_ic_calculator_computes_rank_ic_and_icir() -> None:
    factor_values = pl.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-01", "2026-01-02", "2026-01-02"],
            "stock_id": ["A", "B", "A", "B"],
            "factor_value": [1.0, 2.0, 2.0, 1.0],
        }
    )
    returns = pl.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-01", "2026-01-02", "2026-01-02"],
            "stock_id": ["A", "B", "A", "B"],
            "return_t_plus_1": [0.01, 0.02, 0.03, 0.01],
        }
    )

    calculator = RankICCalculator()
    ic = calculator.compute_rank_ic(factor_values, returns, horizon=1)

    assert ic.columns == ["date", "ic", "ic_abs"]
    assert ic["ic"].to_list() == pytest.approx([1.0, 1.0])
    assert math.isnan(calculator.compute_icir(pl.Series([0.05, 0.05])))


def test_ic_trend_calculator_returns_weighted_slope_and_decline_flag() -> None:
    series = pl.Series("ic", [0.10, 0.09, 0.08, 0.07, 0.06, 0.05])

    result = ICTrendCalculator().compute_trend_slope(series, windows=[3, 6], weights=[0.6, 0.4])

    assert result["weighted_slope"] < 0
    assert result["trend_direction"] == "down"
    assert ICTrendCalculator().detect_significant_decline(series, decline_threshold=0.2, min_window=3)


def test_decay_fitter_uses_linear_half_life_rules() -> None:
    result = DecayFitter().fit_half_life({1: 0.08, 2: 0.06, 5: 0.03, 10: 0.02})

    assert result["optimal_horizon"] == 1
    assert result["half_life_days"] == pytest.approx(4.0)
    assert result["decay_speed"] == "medium"


def test_regime_label_generator_combines_trend_and_volatility_labels() -> None:
    dates = [f"2026-01-{day:02d}" for day in range(1, 31)]
    returns = [0.003] * 25 + [0.02, -0.02, 0.02, -0.02, 0.02]

    result = RegimeLabelGenerator().generate_labels(
        pl.DataFrame({"date": dates, "market_return": returns}),
        trend_window=5,
        vol_window=5,
        trend_threshold=0.01,
    )

    assert result.columns == ["date", "trend_regime", "vol_regime", "combined_regime"]
    assert result.height == 30
    assert set(result["trend_regime"].drop_nulls().unique().to_list()) <= {"bull", "bear", "sideways"}
    assert set(result["vol_regime"].drop_nulls().unique().to_list()) <= {"high_vol", "low_vol", "normal_vol"}


def test_outlier_detector_winsorizes_and_flags_jumps() -> None:
    detector = OutlierDetector()
    series = pl.Series("value", [1.0, 1.0, 1.0, 1.0, 100.0])

    winsorized = detector.mad_winsorize(series, n_mad=5.0)

    assert winsorized[-1] == pytest.approx(1.0)
    assert detector.detect_single_day_jump(pl.Series("value", [1.0, 1.1, 1.2, 10.0]), zscore_threshold=2.0)
