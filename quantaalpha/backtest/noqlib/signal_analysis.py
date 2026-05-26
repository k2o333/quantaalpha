"""No-qlib 信号 IC 指标。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import polars as pl


def signal_metrics(prediction: pd.Series | pd.DataFrame | pl.DataFrame, label: pd.Series | pd.DataFrame | pl.DataFrame) -> dict[str, float]:
    """计算 IC、ICIR、Rank IC、Rank ICIR。"""
    pred_polars = _to_signal_frame(prediction, "pred")
    label_polars = _to_signal_frame(label, "label")
    raw_prediction_rows = int(pred_polars.height)
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


def _to_signal_frame(frame: pd.Series | pd.DataFrame | pl.DataFrame, value_column: str) -> pl.DataFrame:
    """归一化 signal 输入为显式键列 polars frame。"""
    if isinstance(frame, pl.DataFrame):
        return _normalize_polars_signal_frame(frame, value_column)
    if isinstance(frame, pd.Series):
        return _normalize_polars_signal_frame(pl.from_pandas(frame.rename(value_column).reset_index()), value_column)
    if isinstance(frame, pd.DataFrame):
        if value_column in frame.columns:
            value_series = frame[value_column]
        elif len(frame.columns) == 1:
            value_series = frame.iloc[:, 0].rename(value_column)
        else:
            raise ValueError(f"signal {value_column} frame must contain a '{value_column}' column or exactly one value column")
        return _normalize_polars_signal_frame(pl.from_pandas(value_series.reset_index()), value_column)
    raise TypeError(f"unsupported signal {value_column} input type: {type(frame).__name__}")


def _normalize_polars_signal_frame(frame: pl.DataFrame, value_column: str) -> pl.DataFrame:
    """校验并标准化 signal polars frame 的键列和值列。"""
    required_keys = {"datetime", "instrument"}
    missing_keys = sorted(required_keys - set(frame.columns))
    if missing_keys:
        raise ValueError(f"signal {value_column} frame missing columns: {missing_keys}")
    if value_column not in frame.columns:
        value_candidates = [column for column in frame.columns if column not in required_keys]
        if len(value_candidates) != 1:
            raise ValueError(f"signal {value_column} frame must contain '{value_column}' or exactly one non-key value column")
        frame = frame.rename({value_candidates[0]: value_column})
    return frame.select(["datetime", "instrument", value_column]).with_columns(
        _datetime_expr(frame),
        pl.col("instrument").cast(pl.Utf8),
        pl.col(value_column).cast(pl.Float64, strict=False),
    )


def _datetime_expr(frame: pl.DataFrame) -> pl.Expr:
    """按输入类型把 datetime 列归一为 ns 精度时间戳。"""
    dtype = frame.schema["datetime"]
    if dtype == pl.Utf8:
        return pl.col("datetime").str.strptime(pl.Datetime("ns"), strict=False)
    return pl.col("datetime").cast(pl.Datetime("ns"), strict=False)


def _mean(values: list[float]) -> float:
    return float(np.mean(values)) if values else 0.0


def _ir(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    std = float(np.std(values, ddof=1))
    return float(np.mean(values) / std) if std > 1e-12 else 0.0
