"""No-qlib 风险指标。"""

from __future__ import annotations

import numpy as np
import pandas as pd


def risk_metrics(excess_return: pd.Series) -> dict[str, float]:
    """计算 qlib risk_analysis 对齐目标指标的 no-qlib 版本。"""
    values = excess_return.replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy(dtype=float)
    if len(values) == 0:
        return {"annualized_return": 0.0, "information_ratio": 0.0, "max_drawdown": 0.0, "calmar_ratio": 0.0}
    annualized = _annualized_return(values)
    info = _ratio(values.mean() * 252.0, values.std(ddof=1) * np.sqrt(252.0) if len(values) > 1 else 0.0)
    max_dd = _max_drawdown(values)
    return {
        "annualized_return": annualized,
        "information_ratio": info,
        "max_drawdown": max_dd,
        "calmar_ratio": _ratio(annualized, abs(max_dd)),
    }


def _annualized_return(returns: np.ndarray) -> float:
    compounded = float(np.prod(1.0 + returns))
    return compounded ** (252.0 / len(returns)) - 1.0


def _ratio(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator > 1e-12 else 0.0


def _max_drawdown(returns: np.ndarray) -> float:
    equity = np.cumprod(1.0 + returns)
    peak = np.maximum.accumulate(equity)
    return float((equity / peak - 1.0).min())

