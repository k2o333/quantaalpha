"""No-qlib 风险指标。"""

from __future__ import annotations

from datetime import date, datetime
import math
import statistics
from typing import Iterable

import polars as pl


def risk_metrics(excess_return: Iterable[float] | pl.Series) -> dict[str, float]:
    """计算 qlib risk_analysis 对齐目标指标的 no-qlib 版本。"""
    if isinstance(excess_return, pl.Series):
        values = [float(value) for value in excess_return.to_list()]
    else:
        values = [float(value) for value in excess_return]
    if len(values) == 0:
        return {"annualized_return": 0.0, "information_ratio": 0.0, "max_drawdown": 0.0, "calmar_ratio": 0.0}
    bad_count = sum(1 for value in values if not math.isfinite(value))
    if bad_count:
        raise ValueError(f"non-finite excess_return values are not valid risk input: count={bad_count}")
    scaler = 238.0
    mean_value = statistics.fmean(values)
    annualized = float(mean_value * scaler)
    info = _ratio(mean_value, statistics.stdev(values) if len(values) > 1 else 0.0) * math.sqrt(scaler)
    max_dd = _max_drawdown(values)
    return {
        "annualized_return": annualized,
        "information_ratio": info,
        "max_drawdown": max_dd,
        "calmar_ratio": _ratio(annualized, abs(max_dd)),
    }


def risk_metrics_by_year(excess_return: pl.DataFrame) -> dict[str, dict[str, float]]:
    """按自然年切分日超额收益并计算 no-qlib 风险指标。"""
    if excess_return.is_empty():
        return {}
    required = {"date", "excess_return"}
    missing = sorted(required - set(excess_return.columns))
    if missing:
        raise ValueError(f"risk_metrics_by_year frame missing columns: {missing}")
    rows = excess_return.select(["date", "excess_return"]).drop_nulls("excess_return").to_dicts()
    by_year: dict[str, list[float]] = {}
    for row in rows:
        year = _year(row["date"])
        by_year.setdefault(str(year), []).append(float(row["excess_return"]))
    return {year: risk_metrics(values) for year, values in sorted(by_year.items())}


def _ratio(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator > 1e-12 else 0.0


def _max_drawdown(returns: list[float]) -> float:
    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for value in returns:
        cumulative += value
        peak = max(peak, cumulative)
        max_drawdown = min(max_drawdown, cumulative - peak)
    return float(max_drawdown)


def _year(value: object) -> int:
    if isinstance(value, datetime):
        return value.year
    if isinstance(value, date):
        return value.year
    text = str(value)
    return int(text[:4])
