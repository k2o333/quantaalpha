"""Durable factor-value publication helpers."""

from __future__ import annotations

import ast
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import polars as pl


@dataclass(frozen=True)
class FactorValuePublicationResult:
    output_path: str
    manifest_path: str
    factor_id: str
    factor_name: str
    row_count: int


def publish_factor_values_from_workspace(
    *,
    workspace_path: str | Path,
    factor_name: str,
    factor_id: str,
    output_dir: str | Path,
    metadata: dict[str, Any] | None = None,
) -> FactorValuePublicationResult:
    """Publish one factor's workspace values as long-format durable parquet."""

    source_path = Path(workspace_path) / "combined_factors_df.parquet"
    if not source_path.exists():
        raise FileNotFoundError(f"combined factor values not found: {source_path}")

    frame = pl.read_parquet(source_path)
    normalized = _normalize_workspace_factor_frame(frame, factor_name=factor_name, factor_id=factor_id)

    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    output_path = target_dir / f"{factor_id}.parquet"
    manifest_path = target_dir / f"{factor_id}.manifest.json"
    normalized.write_parquet(output_path)

    result = FactorValuePublicationResult(
        output_path=str(output_path),
        manifest_path=str(manifest_path),
        factor_id=factor_id,
        factor_name=factor_name,
        row_count=normalized.height,
    )
    manifest = {
        **asdict(result),
        "source_path": str(source_path),
        "metadata": metadata or {},
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def _normalize_workspace_factor_frame(frame: pl.DataFrame, *, factor_name: str, factor_id: str) -> pl.DataFrame:
    frame = _normalize_key_columns(frame)
    value_column = _find_factor_value_column(frame.columns, factor_name)
    if value_column is None:
        raise ValueError(f"factor value column not found for factor '{factor_name}'")
    if "trade_date" not in frame.columns or "instrument" not in frame.columns:
        raise ValueError("workspace factor frame must include trade_date/datetime/date and instrument/ts_code")

    return (
        frame.select(["trade_date", "instrument", value_column])
        .rename({value_column: "factor_value"})
        .with_columns(
            pl.col("trade_date").map_elements(_normalize_date_value, return_dtype=pl.Utf8),
            pl.col("instrument").cast(pl.Utf8),
            pl.lit(str(factor_id)).alias("factor_id"),
            pl.col("factor_value").cast(pl.Float64, strict=False),
        )
        .select(["trade_date", "instrument", "factor_id", "factor_value"])
        .drop_nulls(["factor_value"])
        .unique(subset=["trade_date", "instrument", "factor_id"], keep="last")
        .sort(["trade_date", "instrument", "factor_id"])
    )


def _normalize_key_columns(frame: pl.DataFrame) -> pl.DataFrame:
    rename_map: dict[str, str] = {}
    if "instrument" not in frame.columns and "ts_code" in frame.columns:
        rename_map["ts_code"] = "instrument"
    if "trade_date" not in frame.columns:
        if "datetime" in frame.columns:
            rename_map["datetime"] = "trade_date"
        elif "date" in frame.columns:
            rename_map["date"] = "trade_date"
    return frame.rename(rename_map) if rename_map else frame


def _find_factor_value_column(columns: list[str], factor_name: str) -> str | None:
    for column in columns:
        if _feature_name_from_column(column) == factor_name:
            return column
    return None


def _feature_name_from_column(column: str) -> str | None:
    if column in {"trade_date", "date", "datetime", "instrument", "ts_code"}:
        return None
    if column.startswith("('feature',"):
        try:
            parsed = ast.literal_eval(column)
        except (SyntaxError, ValueError):
            return None
        if isinstance(parsed, tuple) and len(parsed) == 2 and parsed[0] == "feature":
            return str(parsed[1])
    return column


def _normalize_date_value(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "strftime"):
        return value.strftime("%Y%m%d")
    text = str(value).strip()
    if not text:
        return None
    return text.replace("-", "")[:8]
