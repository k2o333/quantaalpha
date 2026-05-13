"""Tradability masks from App5 auxiliary interfaces."""

from __future__ import annotations

import polars as pl


def build_tradability_mask(
    universe: pl.DataFrame,
    *,
    trade_cal: pl.DataFrame,
    suspend_d: pl.DataFrame | None = None,
    stock_st: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """Combine calendar, suspension, and ST constraints into one mask."""

    base = universe.with_columns(
        pl.col("datetime").cast(pl.Date).alias("datetime"),
        pl.col("instrument").cast(pl.Utf8).alias("instrument"),
    )
    cal = trade_cal.select(
        pl.col("cal_date").cast(pl.Date).alias("datetime"),
        (pl.col("is_open").cast(pl.Int64, strict=False) == 1).alias("__calendar_open"),
    )
    result = base.join(cal, on="datetime", how="left").with_columns(pl.col("__calendar_open").fill_null(False))
    if suspend_d is not None and not suspend_d.is_empty():
        suspended = suspend_d.select(
            pl.col("trade_date").cast(pl.Date).alias("datetime"),
            pl.col("ts_code").cast(pl.Utf8).alias("instrument"),
        ).unique()
        result = result.join(suspended.with_columns(pl.lit(True).alias("__suspended")), on=["datetime", "instrument"], how="left")
    else:
        result = result.with_columns(pl.lit(False).alias("__suspended"))
    if stock_st is not None and not stock_st.is_empty():
        st = stock_st.select(
            pl.col("trade_date").cast(pl.Date).alias("datetime"),
            pl.col("ts_code").cast(pl.Utf8).alias("instrument"),
            (pl.col("is_st").cast(pl.Int64, strict=False) == 1).alias("__st"),
        )
        result = result.join(st, on=["datetime", "instrument"], how="left")
    else:
        result = result.with_columns(pl.lit(False).alias("__st"))
    return result.with_columns(
        (pl.col("__calendar_open") & ~pl.col("__suspended").fill_null(False) & ~pl.col("__st").fill_null(False)).alias("is_tradable")
    ).drop(["__calendar_open", "__suspended", "__st"]).sort(["instrument", "datetime"])
