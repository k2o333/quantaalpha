from __future__ import annotations

import pandas as pd
import pytest


def test_risk_metrics_rejects_nan_excess_returns() -> None:
    from quantaalpha.backtest.noqlib.risk import risk_metrics

    with pytest.raises(ValueError, match="non-finite excess_return"):
        risk_metrics(pd.Series([0.01, float("nan")]))


def test_risk_metrics_rejects_infinite_excess_returns() -> None:
    from quantaalpha.backtest.noqlib.risk import risk_metrics

    with pytest.raises(ValueError, match="non-finite excess_return"):
        risk_metrics(pd.Series([0.01, float("inf")]))
