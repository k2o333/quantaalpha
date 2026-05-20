"""No-qlib 风险指标。"""

from __future__ import annotations

import numpy as np
import pandas as pd


def risk_metrics(excess_return: pd.Series) -> dict[str, float]:
    """计算 qlib risk_analysis 对齐目标指标的 no-qlib 版本。"""
    values = excess_return.to_numpy(dtype=float)
    if len(values) == 0:
        return {"annualized_return": 0.0, "information_ratio": 0.0, "max_drawdown": 0.0, "calmar_ratio": 0.0}
    finite_mask = np.isfinite(values)
    if not finite_mask.all():
        bad_count = int((~finite_mask).sum())
        raise ValueError(f"non-finite excess_return values are not valid risk input: count={bad_count}")
    scaler = 238.0
    annualized = float(values.mean() * scaler)
    info = _ratio(values.mean(), values.std(ddof=1) if len(values) > 1 else 0.0) * np.sqrt(scaler)
    max_dd = _max_drawdown(values)
    return {
        "annualized_return": annualized,
        "information_ratio": info,
        "max_drawdown": max_dd,
        "calmar_ratio": _ratio(annualized, abs(max_dd)),
    }


def risk_metrics_by_year(excess_return: pd.Series) -> dict[str, dict[str, float]]:
    """按自然年切分日超额收益并计算 no-qlib 风险指标。"""
    if excess_return.empty:
        return {}
    if not isinstance(excess_return.index, pd.DatetimeIndex):
        series = excess_return.copy()
        series.index = pd.to_datetime(series.index)
    else:
        series = excess_return
    return {str(year): risk_metrics(group) for year, group in series.groupby(series.index.year)}


def _ratio(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator > 1e-12 else 0.0


def _max_drawdown(returns: np.ndarray) -> float:
    cumulative = np.cumsum(returns)
    peak = np.maximum.accumulate(cumulative)
    return float((cumulative - peak).min())
