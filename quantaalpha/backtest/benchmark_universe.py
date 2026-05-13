"""Benchmark universe selection from App5 index_weight."""

from __future__ import annotations

from datetime import date

import polars as pl


def select_benchmark_universe_asof(
    index_weight: pl.DataFrame,
    *,
    index_code: str,
    as_of_date: date | str,
) -> pl.DataFrame:
    """Return benchmark constituents for the latest weight date visible as of a date."""

    if index_weight.is_empty():
        return pl.DataFrame(schema={"instrument": pl.String, "benchmark_weight": pl.Float64})
    query_date = _parse_date(as_of_date)
    frame = index_weight.with_columns(pl.col("trade_date").cast(pl.Date).alias("trade_date"))
    visible = frame.filter((pl.col("index_code") == index_code) & (pl.col("trade_date") <= query_date))
    if visible.is_empty():
        return pl.DataFrame(schema={"instrument": pl.String, "benchmark_weight": pl.Float64})
    latest_date = visible.select(pl.col("trade_date").max()).item()
    return (
        visible.filter(pl.col("trade_date") == latest_date)
        .select(
            pl.col("con_code").cast(pl.Utf8).alias("instrument"),
            pl.col("weight").cast(pl.Float64, strict=False).alias("benchmark_weight"),
        )
        .sort("instrument")
    )


def _parse_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    raw = str(value)
    if len(raw) == 8 and raw.isdigit():
        return date.fromisoformat(f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}")
    return date.fromisoformat(raw)
