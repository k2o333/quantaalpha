"""No-qlib 信号 IC 指标。"""

from __future__ import annotations

import numpy as np
import pandas as pd


def signal_metrics(prediction: pd.Series, label: pd.Series) -> dict[str, float]:
    """计算 IC、ICIR、Rank IC、Rank ICIR。"""
    aligned = pd.concat([prediction.rename("pred"), label.rename("label")], axis=1).dropna()
    if aligned.empty:
        return {"IC": 0.0, "ICIR": 0.0, "Rank IC": 0.0, "Rank ICIR": 0.0}
    ic_values = []
    rank_ic_values = []
    for _, group in aligned.groupby(level="datetime"):
        if len(group) < 2:
            continue
        ic = group["pred"].corr(group["label"])
        ric = group["pred"].rank().corr(group["label"].rank())
        if not np.isnan(ic):
            ic_values.append(float(ic))
        if not np.isnan(ric):
            rank_ic_values.append(float(ric))
    return {
        "IC": _mean(ic_values),
        "ICIR": _ir(ic_values),
        "Rank IC": _mean(rank_ic_values),
        "Rank ICIR": _ir(rank_ic_values),
    }


def _mean(values: list[float]) -> float:
    return float(np.mean(values)) if values else 0.0


def _ir(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    std = float(np.std(values, ddof=1))
    return float(np.mean(values) / std) if std > 1e-12 else 0.0

