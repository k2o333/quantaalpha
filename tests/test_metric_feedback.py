from __future__ import annotations

import pandas as pd

from quantaalpha.pipeline.evolution.metric_feedback import (
    extract_backtest_metrics,
    format_metric_feedback,
)


def test_extract_backtest_metrics_from_backtest_dataframe() -> None:
    result = pd.DataFrame(
        {"0": [0.012345, 0.045678, 1.2345, 0.0789]},
        index=[
            "IC",
            "Rank IC",
            "1day.excess_return_without_cost.information_ratio",
            "1day.excess_return_without_cost.annualized_return",
        ],
    )

    metrics = extract_backtest_metrics(result)

    assert metrics == {
        "IC": 0.012345,
        "Rank IC": 0.045678,
        "Information Ratio": 1.2345,
        "Annualized Return": 0.0789,
    }


def test_format_metric_feedback_includes_core_backtest_metrics() -> None:
    text = format_metric_feedback(
        {
            "IC": 0.012345,
            "RankIC": 0.045678,
            "information_ratio": 1.2345,
            "annualized_return": 0.0789,
        }
    )

    assert "Backtest Metrics" in text
    assert "IC=0.0123" in text
    assert "Rank IC=0.0457" in text
    assert "Information Ratio=1.2345" in text
    assert "Annualized Return=0.0789" in text


def test_format_metric_feedback_warns_on_low_ic() -> None:
    text = format_metric_feedback({"IC": 0.001, "RankIC": -0.002})

    assert "low predictive power" in text
