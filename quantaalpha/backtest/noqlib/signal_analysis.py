"""No-qlib 信号 IC 指标。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import polars as pl


def signal_metrics(prediction: pd.Series, label: pd.Series) -> dict[str, float]:
    """计算 IC、ICIR、Rank IC、Rank ICIR。"""
    raw_prediction_rows = int(len(prediction))
    pred_frame = prediction.rename("pred").reset_index()
    label_frame = label.rename("label").reset_index()
    pred_polars = pl.from_pandas(pred_frame).with_columns(
        pl.col("datetime").cast(pl.Datetime("ns")),
        pl.col("instrument").cast(pl.Utf8),
    )
    label_polars = pl.from_pandas(label_frame).with_columns(
        pl.col("datetime").cast(pl.Datetime("ns")),
        pl.col("instrument").cast(pl.Utf8),
    )
    aligned = (
        pred_polars.join(label_polars, on=["datetime", "instrument"], how="inner")
        .drop_nulls(["pred", "label"])
    )
    capacity_metrics = {
        "signal_aligned_rows": float(aligned.height),
        "signal_active_days": 0.0,
        "signal_mean_cross_section_size": 0.0,
        "signal_valid_ratio": float(aligned.height / raw_prediction_rows) if raw_prediction_rows > 0 else 0.0,
    }
    if aligned.is_empty():
        return {"IC": 0.0, "ICIR": 0.0, "Rank IC": 0.0, "Rank ICIR": 0.0, **capacity_metrics}
    daily = (
        aligned.with_columns(
            pl.col("pred").rank(method="average").over("datetime").alias("pred_rank"),
            pl.col("label").rank(method="average").over("datetime").alias("label_rank"),
        )
        .group_by("datetime", maintain_order=True)
        .agg(
            pl.len().alias("rows"),
            pl.corr("pred", "label").alias("ic"),
            pl.corr("pred_rank", "label_rank").alias("rank_ic"),
        )
        .filter(pl.col("rows") >= 2)
    )
    capacity_metrics["signal_active_days"] = float(daily.height)
    if not daily.is_empty():
        capacity_metrics["signal_mean_cross_section_size"] = float(daily.get_column("rows").mean() or 0.0)
    ic_values = [float(value) for value in daily.get_column("ic").drop_nulls().to_list() if np.isfinite(value)]
    rank_ic_values = [float(value) for value in daily.get_column("rank_ic").drop_nulls().to_list() if np.isfinite(value)]
    return {
        "IC": _mean(ic_values),
        "ICIR": _ir(ic_values),
        "Rank IC": _mean(rank_ic_values),
        "Rank ICIR": _ir(rank_ic_values),
        **capacity_metrics,
    }


def _mean(values: list[float]) -> float:
    return float(np.mean(values)) if values else 0.0


def _ir(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    std = float(np.std(values, ddof=1))
    return float(np.mean(values) / std) if std > 1e-12 else 0.0
