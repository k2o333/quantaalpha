"""Qlib return provenance extraction helpers."""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from quantaalpha.backtest.contracts import QlibReturnProvenance


def qlib_excess_return_provenance(
    *,
    recorder_object: str,
    report_path: str = 'portfolio_metric_dict["1day"][0]',
    source_series_proven_identical: bool = False,
) -> QlibReturnProvenance:
    """Return the frozen provenance for the current qlib runner return metric."""
    return QlibReturnProvenance(
        recorder_object=recorder_object,
        dataframe_path=report_path,
        column_name="excess_return",
        transformation='report["return"] - report["bench"] - report["cost"]',
        risk_analyzer_input="qlib.contrib.evaluate.risk_analysis(excess_return_with_cost)",
        daily_series_name="excess_vs_benchmark.daily_excess_return",
        source_series_proven_identical=source_series_proven_identical,
    )


def extract_excess_return_series(report: pd.DataFrame) -> pd.Series:
    """Extract the exact daily series consumed by qlib risk_analysis."""
    required = {"return", "bench", "cost"}
    missing = sorted(required - set(report.columns))
    if missing:
        raise ValueError(f"qlib portfolio report missing columns for excess return: {missing}")
    series = report["return"].replace([float("inf"), float("-inf")], pd.NA).fillna(0)
    bench = report["bench"].replace([float("inf"), float("-inf")], pd.NA).fillna(0)
    cost = report["cost"].replace([float("inf"), float("-inf")], pd.NA).fillna(0)
    result = (series - bench - cost).dropna()
    result.name = "excess_return"
    return result


def require_qlib_return_provenance(metrics: Mapping[str, Any]) -> dict[str, Any]:
    """Fail if qlib annualized return lacks the frozen provenance payload."""
    namespaces = metrics.get("metric_namespaces")
    if not isinstance(namespaces, Mapping):
        raise ValueError("metrics missing metric_namespaces")
    excess = namespaces.get("excess_vs_benchmark")
    if not isinstance(excess, Mapping):
        raise ValueError("metrics missing excess_vs_benchmark namespace")
    provenance = excess.get("qlib_return_provenance")
    if not isinstance(provenance, Mapping):
        raise ValueError("qlib annualized return provenance is missing")
    required = {
        "recorder_object",
        "dataframe_path",
        "column_name",
        "transformation",
        "risk_analyzer_input",
        "daily_series_name",
        "source_series_proven_identical",
    }
    missing = sorted(required - set(provenance))
    if missing:
        raise ValueError(f"qlib annualized return provenance missing fields: {missing}")
    return dict(provenance)
