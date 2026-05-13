"""No-qlib 风险指标。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import polars as pl


def risk_metrics(excess_return: pd.Series) -> dict[str, float]:
    """计算 qlib risk_analysis 对齐目标指标的 no-qlib 版本。"""
    values = (
        pl.Series("excess_return", excess_return.to_numpy(dtype=float))
        .replace([np.inf, -np.inf], None)
        .fill_null(0.0)
        .to_numpy()
    )
    if len(values) == 0:
        return {"annualized_return": 0.0, "information_ratio": 0.0, "max_drawdown": 0.0, "calmar_ratio": 0.0}
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


def _ratio(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator > 1e-12 else 0.0


def _max_drawdown(returns: np.ndarray) -> float:
    cumulative = np.cumsum(returns)
    peak = np.maximum.accumulate(cumulative)
    return float((cumulative - peak).min())
