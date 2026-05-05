from __future__ import annotations

import math

import polars as pl
import pytest
from quantaalpha.factor_ops.eval.regime_ic import RegimeICComputer, RegimeICResult


def test_regime_ic_computes_conditional_ic_by_combined_regime() -> None:
    """Regime IC 按市场状态聚合 ic_mean / icir / n_days。"""
    factor_values = pl.DataFrame(
        {
            "date": ["2026-05-01"] * 4 + ["2026-05-02"] * 4 + ["2026-05-03"] * 4,
            "stock_id": ["A", "B", "C", "D"] * 3,
            "factor_value": [1.0, 2.0, 3.0, 4.0] * 3,
        }
    )
    returns = pl.DataFrame(
        {
            "date": ["2026-05-01"] * 4 + ["2026-05-02"] * 4 + ["2026-05-03"] * 4,
            "stock_id": ["A", "B", "C", "D"] * 3,
            "return_t_plus_1": [
                0.01,
                0.02,
                0.03,
                0.04,
                0.01,
                0.02,
                0.03,
                0.04,
                0.04,
                0.03,
                0.02,
                0.01,
            ],
        }
    )
    labels = pl.DataFrame(
        {
            "date": ["2026-05-01", "2026-05-02", "2026-05-03"],
            "combined_regime": ["bull_low_vol", "bull_low_vol", "bear_high_vol"],
        }
    )

    result = RegimeICComputer().compute(factor_values, returns, labels)

    assert isinstance(result, RegimeICResult)
    assert result.horizon == 1
    assert result.regime_ic["bull_low_vol"]["ic_mean"] == pytest.approx(1.0)
    assert result.regime_ic["bull_low_vol"]["n_days"] == 2
    assert result.regime_ic["bear_high_vol"]["ic_mean"] == pytest.approx(-1.0)
    assert result.best_regime == "bull_low_vol"
    assert result.worst_regime == "bear_high_vol"


def test_regime_ic_accepts_precomputed_daily_ic() -> None:
    """可从已计算 daily IC 直接汇总，便于月度重算复用。"""
    daily_ic = pl.DataFrame(
        {
            "date": ["2026-05-01", "2026-05-02", "2026-05-03"],
            "ic": [0.04, 0.02, -0.03],
        }
    )
    labels = pl.DataFrame(
        {
            "date": ["2026-05-01", "2026-05-02", "2026-05-03"],
            "trend_regime": ["bull", "bull", "bear"],
        }
    )

    result = RegimeICComputer().summarize_daily_ic(
        daily_ic,
        labels,
        regime_column="trend_regime",
    )

    assert result.regime_ic["bull"]["ic_mean"] == pytest.approx(0.03)
    assert result.regime_ic["bear"]["ic_mean"] == pytest.approx(-0.03)
    assert math.isnan(result.regime_ic["bear"]["icir"])


def test_regime_ic_to_ts_gru_features_flattens_regime_stats() -> None:
    """Regime IC 输出可转换为 TS-GRU 先验特征字典。"""
    result = RegimeICComputer().summarize_daily_ic(
        pl.DataFrame({"date": ["2026-05-01"], "ic": [0.04]}),
        pl.DataFrame({"date": ["2026-05-01"], "combined_regime": ["bull_low_vol"]}),
    )

    assert result.to_ts_gru_features() == {
        "regime_ic_bull_low_vol_ic_mean": 0.04,
        "regime_ic_bull_low_vol_icir": math.nan,
        "regime_ic_bull_low_vol_n_days": 1,
    }
