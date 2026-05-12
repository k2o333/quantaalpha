from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _market() -> pd.DataFrame:
    rows = []
    for dt in pd.date_range("2020-01-01", periods=4, freq="D"):
        for offset, instrument in enumerate(["A", "B"]):
            close = float(dt.day + offset)
            rows.append(
                {
                    "datetime": dt,
                    "instrument": instrument,
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "volume": 100.0,
                    "vwap": close,
                    "return": 0.0,
                }
            )
    return pd.DataFrame(rows).set_index(["datetime", "instrument"])


def test_vnpy_expression_engine_golden_cases() -> None:
    from quantaalpha.backtest.vnpy.expression_engine import VnpyExpressionEngine

    engine = VnpyExpressionEngine(_market())
    factors = [
        {"factor_id": "mean2", "factor_name": "mean2", "factor_expression": "TS_MEAN($close, 2)"},
        {"factor_id": "rank2", "factor_name": "rank2", "factor_expression": "TS_RANK($close, 2)"},
        {"factor_id": "ret1", "factor_name": "ret1", "factor_expression": "$close / DELAY($close, 1) - 1"},
    ]
    result = engine.compute(factors)
    idx = (pd.Timestamp("2020-01-02"), "A")
    assert result.loc[idx, "mean2"] == pytest.approx(1.5)
    assert result.loc[idx, "rank2"] == pytest.approx(1.0)
    assert result.loc[idx, "ret1"] == pytest.approx(1.0)
    assert engine.audit[0].vnpy_expression == "ts_mean(close, 2)"


def test_vnpy_expression_engine_accepts_qlib_style_aliases() -> None:
    from quantaalpha.backtest.vnpy.expression_engine import VnpyExpressionEngine

    result = VnpyExpressionEngine(_market()).compute(
        [{"factor_id": "mean2", "factor_name": "mean2", "factor_expression": "Mean($close, 2)"}]
    )
    assert result.loc[(pd.Timestamp("2020-01-02"), "A"), "mean2"] == pytest.approx(1.5)


def test_vnpy_expression_engine_rejects_unsupported_calls() -> None:
    from quantaalpha.backtest.vnpy.expression_engine import VnpyExpressionEngine, VnpyExpressionError

    with pytest.raises(VnpyExpressionError, match="unsupported"):
        VnpyExpressionEngine(_market()).compute(
            [{"factor_id": "bad", "factor_name": "bad", "factor_expression": "UNSUPPORTED($close, 2)"}]
        )
