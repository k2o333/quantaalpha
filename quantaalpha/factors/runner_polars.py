from __future__ import annotations

import numpy as np
import polars as pl

from quantaalpha.core.exception import FactorEmptyError


KEY_COLUMNS = ("datetime", "instrument")


def prepare_parquet_runtime_combined_factors(
    h5_combined_factors: pl.DataFrame,
    parquet_runtime_new_factors: pl.DataFrame,
) -> tuple[pl.DataFrame, list[str]]:
    """Build a Polars combined frame with parquet-runtime values replacing new factor columns."""

    common_columns = [col for col in factor_value_columns(h5_combined_factors) if col in factor_value_columns(parquet_runtime_new_factors)]
    if not common_columns:
        raise AssertionError("parquet runtime combined parity has no common factor columns")
    replacement = parquet_runtime_new_factors.select([*KEY_COLUMNS, *common_columns])
    base_columns = [col for col in h5_combined_factors.columns if col not in common_columns]
    parquet_combined = h5_combined_factors.select(base_columns).join(replacement, on=list(KEY_COLUMNS), how="inner")
    if parquet_combined.is_empty():
        raise AssertionError("parquet runtime combined parity has no common rows")
    return parquet_combined.sort(list(KEY_COLUMNS)), common_columns


def factor_value_columns(df: pl.DataFrame) -> list[str]:
    """Return non-key factor value columns from a standard factor frame."""

    return [column for column in df.columns if column not in KEY_COLUMNS]


def ensure_polars_factor_frame(df: pl.DataFrame, *, factor_name: str | None = None) -> pl.DataFrame:
    """Normalize a factor result to explicit-key Polars frame."""

    if not isinstance(df, pl.DataFrame):
        raise TypeError(f"factor result must be a polars DataFrame, got {type(df).__name__}")
    missing = set(KEY_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"factor result missing key columns: {sorted(missing)}")
    rename_map: dict[str, str] = {}
    value_columns = factor_value_columns(df)
    if factor_name and len(value_columns) == 1 and value_columns[0] in {"value", "score", "pred"}:
        rename_map[value_columns[0]] = factor_name
    for column in value_columns:
        normalized = _normalize_feature_column_name(str(rename_map.get(column, column)))
        if normalized != column:
            rename_map[column] = normalized
    if rename_map:
        df = df.rename(rename_map)
    value_columns = factor_value_columns(df)
    if not value_columns:
        raise ValueError("factor result has no value columns")
    datetime_expr = pl.col("datetime").str.strptime(pl.Datetime("ns"), strict=False) if df.schema["datetime"] == pl.Utf8 else pl.col("datetime").cast(pl.Datetime("ns"), strict=False)
    normalized = (
        df.select([*KEY_COLUMNS, *value_columns])
        .with_columns(
            datetime_expr.alias("datetime"),
            pl.col("instrument").cast(pl.Utf8),
            *[pl.col(column).cast(pl.Float64, strict=False).alias(column) for column in value_columns],
        )
        .sort(list(KEY_COLUMNS))
    )
    duplicate_count = normalized.group_by(list(KEY_COLUMNS)).len().filter(pl.col("len") > 1).height
    if duplicate_count:
        raise ValueError(f"factor result duplicate datetime/instrument keys: {duplicate_count}")
    return normalized


def clean_factor_values(df: pl.DataFrame) -> pl.DataFrame:
    value_columns = factor_value_columns(df)
    return df.with_columns(*[pl.when(pl.col(column).is_infinite() | pl.col(column).is_nan()).then(None).otherwise(pl.col(column)).alias(column) for column in value_columns])


def join_factor_frames(frames: list[pl.DataFrame], *, how: str = "inner") -> pl.DataFrame:
    if not frames:
        raise FactorEmptyError("No valid factor data found to merge.")
    result = frames[0]
    for frame in frames[1:]:
        overlap = set(factor_value_columns(result)) & set(factor_value_columns(frame))
        if overlap:
            raise ValueError(f"duplicate factor columns: {sorted(overlap)}")
        result = result.join(frame, on=list(KEY_COLUMNS), how=how)
    return result.sort(list(KEY_COLUMNS))


def to_feature_storage_frame(df: pl.DataFrame) -> pl.DataFrame:
    return df.select(
        [
            pl.col("datetime"),
            pl.col("instrument"),
            *[pl.col(column).alias(f"feature_{column}") for column in factor_value_columns(df)],
        ]
    )


def metrics_to_polars(metrics: dict[str, object]) -> pl.DataFrame:
    rows = []
    for metric, value in metrics.items():
        try:
            metric_value = float(value)
        except (TypeError, ValueError):
            continue
        if not np.isfinite(metric_value):
            metric_value = None
        rows.append({"metric": str(metric), "value": metric_value})
    return pl.DataFrame(rows, schema={"metric": pl.Utf8, "value": pl.Float64})


def _normalize_feature_column_name(column: str) -> str:
    if column.startswith("feature_"):
        return column.removeprefix("feature_")
    return column
