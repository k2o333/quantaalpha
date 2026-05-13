from __future__ import annotations

import pandas as pd
import pytest


def test_backtest_result_parity_rejects_metric_difference() -> None:
    from quantaalpha.factors.runner import assert_backtest_result_parity

    h5_result = pd.DataFrame({"value": {"annualized_return": 0.1, "max_drawdown": -0.2}})
    parquet_result = pd.DataFrame({"value": {"annualized_return": 0.2, "max_drawdown": -0.2}})

    with pytest.raises(AssertionError, match="annualized_return"):
        assert_backtest_result_parity(h5_result, parquet_result)


def test_backtest_result_parity_accepts_same_metrics() -> None:
    from quantaalpha.factors.runner import assert_backtest_result_parity

    h5_result = pd.DataFrame({"value": {"annualized_return": 0.1, "max_drawdown": -0.2}})
    parquet_result = pd.DataFrame({"value": {"annualized_return": 0.1, "max_drawdown": -0.2}})

    summary = assert_backtest_result_parity(h5_result, parquet_result)

    assert summary["metric_count"] == 2
    assert summary["max_abs_diff"] == pytest.approx(0.0)


def test_prepare_parquet_runtime_combined_factors_preserves_existing_columns() -> None:
    from quantaalpha.factors.runner import _prepare_parquet_runtime_combined_factors

    index = pd.MultiIndex.from_product(
        [[pd.Timestamp("2026-01-01"), pd.Timestamp("2026-01-02")], ["000001.SZ"]],
        names=["datetime", "instrument"],
    )
    h5_combined = pd.DataFrame(
        {
            "sota_factor": [1.0, 2.0],
            "new_factor": [3.0, 4.0],
        },
        index=index,
    )
    parquet_new = pd.DataFrame({"new_factor": [3.0, 4.0]}, index=index)

    parquet_combined, compared_columns = _prepare_parquet_runtime_combined_factors(h5_combined, parquet_new)

    assert list(parquet_combined.columns) == ["sota_factor", "new_factor"]
    assert compared_columns == ["new_factor"]
    pd.testing.assert_frame_equal(parquet_combined, h5_combined)
