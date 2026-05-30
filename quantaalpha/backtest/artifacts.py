"""回测表格产物写入。"""

from __future__ import annotations

from pathlib import Path

import polars as pl


def write_daily_report_parquet(daily_report: pl.DataFrame, output_dir: Path, prefix: str) -> Path:
    """写入 long-only 日度明细 Parquet。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{prefix}_long_only_daily_report.parquet"
    daily_out = _ensure_date_column(daily_report)
    daily_out.write_parquet(path)
    return path


def write_cumulative_excess_parquet(frame: pl.DataFrame, output_dir: Path, prefix: str) -> Path:
    """写入累计超额收益 Parquet。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{prefix}_cumulative_excess.parquet"
    save_df = _ensure_date_column(frame)
    if "daily_excess_return" not in save_df.columns:
        if {"return", "bench", "cost"} <= set(save_df.columns):
            save_df = save_df.with_columns((pl.col("return") - pl.col("bench") - pl.col("cost")).alias("daily_excess_return"))
        elif "excess_return" in save_df.columns:
            save_df = save_df.rename({"excess_return": "daily_excess_return"})
        else:
            raise ValueError("cumulative excess artifact requires daily_excess_return or return/bench/cost columns")
    if "cumulative_excess_return" not in save_df.columns:
        save_df = save_df.with_columns(pl.col("daily_excess_return").cum_sum().alias("cumulative_excess_return"))
    save_df.select(["date", "daily_excess_return", "cumulative_excess_return"]).write_parquet(path)
    return path


def write_positions_parquet(positions: pl.DataFrame, output_dir: Path, prefix: str) -> Path:
    """写入 long-only 持仓 Parquet。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{prefix}_long_only_positions.parquet"
    positions.write_parquet(path)
    return path


def _ensure_date_column(frame: pl.DataFrame) -> pl.DataFrame:
    if "date" in frame.columns:
        return frame
    if "datetime" in frame.columns:
        return frame.rename({"datetime": "date"})
    raise ValueError("backtest artifact frame requires date or datetime column")
