"""回测表格产物写入。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def write_daily_report_parquet(daily_report: pd.DataFrame, output_dir: Path, prefix: str) -> Path:
    """写入 long-only 日度明细 Parquet。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{prefix}_long_only_daily_report.parquet"
    daily_out = daily_report.reset_index(names="date")
    daily_out.to_parquet(path, index=False)
    return path


def write_cumulative_excess_parquet(frame: pd.DataFrame, output_dir: Path, prefix: str) -> Path:
    """写入累计超额收益 Parquet。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{prefix}_cumulative_excess.parquet"
    save_df = frame.copy()
    if "daily_excess_return" not in save_df.columns:
        if {"return", "bench", "cost"} <= set(save_df.columns):
            save_df["daily_excess_return"] = save_df["return"] - save_df["bench"] - save_df["cost"]
        elif "excess_return" in save_df.columns:
            save_df = save_df.rename(columns={"excess_return": "daily_excess_return"})
        else:
            raise ValueError("cumulative excess artifact requires daily_excess_return or return/bench/cost columns")
    if "cumulative_excess_return" not in save_df.columns:
        save_df["cumulative_excess_return"] = save_df["daily_excess_return"].cumsum()
    save_df = save_df[["daily_excess_return", "cumulative_excess_return"]]
    save_df.index.name = "date"
    save_df.reset_index().to_parquet(path, index=False)
    return path


def write_positions_parquet(positions: pd.DataFrame, output_dir: Path, prefix: str) -> Path:
    """写入 long-only 持仓 Parquet。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{prefix}_long_only_positions.parquet"
    positions.to_parquet(path, index=False)
    return path
