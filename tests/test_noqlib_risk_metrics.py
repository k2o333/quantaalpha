from __future__ import annotations

import polars as pl
import pytest


def test_risk_metrics_rejects_nan_excess_returns() -> None:
    from quantaalpha.backtest.noqlib.risk import risk_metrics

    with pytest.raises(ValueError, match="non-finite excess_return"):
        risk_metrics(pl.Series("excess_return", [0.01, float("nan")]))


def test_risk_metrics_rejects_infinite_excess_returns() -> None:
    from quantaalpha.backtest.noqlib.risk import risk_metrics

    with pytest.raises(ValueError, match="non-finite excess_return"):
        risk_metrics(pl.Series("excess_return", [0.01, float("inf")]))


def test_risk_metrics_by_year_splits_calendar_years() -> None:
    from quantaalpha.backtest.noqlib.risk import risk_metrics_by_year

    returns = pl.DataFrame(
        {
            "date": ["2021-12-30", "2021-12-31", "2022-01-04"],
            "excess_return": [0.01, 0.02, -0.01],
        }
    )

    metrics = risk_metrics_by_year(returns)

    assert set(metrics) == {"2021", "2022"}
    assert metrics["2021"]["annualized_return"] == pytest.approx(0.015 * 238.0)
    assert metrics["2022"]["annualized_return"] == pytest.approx(-0.01 * 238.0)
