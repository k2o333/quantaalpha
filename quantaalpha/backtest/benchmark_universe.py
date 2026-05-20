"""Benchmark universe selection from App5 index_weight."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Sequence

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
    frame = index_weight.with_columns(_trade_date_expr().alias("trade_date"))
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


def write_benchmark_instruments_file(
    index_weight: pl.DataFrame,
    *,
    index_code: str,
    as_of_date: date | str,
    output_path: str | Path,
    exclude_markets: Sequence[str] = (),
) -> Path:
    """将指数 as-of 成分股写成 noqlib instruments 文件。"""

    instruments = select_benchmark_universe_asof(
        index_weight,
        index_code=index_code,
        as_of_date=as_of_date,
    ).get_column("instrument")
    values = sorted(
        {
            str(instrument)
            for instrument in instruments.to_list()
            if not _is_excluded_market(str(instrument), exclude_markets)
        }
    )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(values) + ("\n" if values else ""), encoding="utf-8")
    return path


def write_combined_benchmark_instruments_file(
    index_weight: pl.DataFrame,
    *,
    index_codes: Sequence[str],
    as_of_date: date | str,
    output_path: str | Path,
    exclude_markets: Sequence[str] = (),
) -> Path:
    """将多个指数 as-of 成分股合并写成 noqlib instruments 文件。"""

    values: set[str] = set()
    for index_code in index_codes:
        frame = select_benchmark_universe_asof(index_weight, index_code=index_code, as_of_date=as_of_date)
        values.update(
            str(instrument)
            for instrument in frame.get_column("instrument").to_list()
            if not _is_excluded_market(str(instrument), exclude_markets)
        )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(values)
    path.write_text("\n".join(ordered) + ("\n" if ordered else ""), encoding="utf-8")
    return path


def _parse_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    raw = str(value)
    if len(raw) == 8 and raw.isdigit():
        return date.fromisoformat(f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}")
    return date.fromisoformat(raw)


def _is_excluded_market(instrument: str, exclude_markets: Sequence[str]) -> bool:
    suffix = instrument.rsplit(".", maxsplit=1)[-1].upper() if "." in instrument else ""
    return suffix in {str(market).upper() for market in exclude_markets}


def _trade_date_expr() -> pl.Expr:
    raw = pl.col("trade_date")
    text = raw.cast(pl.Utf8)
    return (
        pl.when(text.str.contains(r"^\d{8}$"))
        .then(text.str.strptime(pl.Date, format="%Y%m%d", strict=False))
        .otherwise(raw.cast(pl.Date, strict=False))
    )
