"""Standard-frame 构建器使用的纯函数。"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Mapping, Sequence

import polars as pl

from quantaalpha.backtest.mining_admission import MiningAdmissionField
from quantaalpha.backtest.contracts import OptionalStandardFrameField


def parse_date_or_none(value: str | None) -> date | None:
    if not value:
        return None
    text = str(value)
    if len(text) == 8 and text.isdigit():
        return datetime.strptime(text, "%Y%m%d").date()
    return datetime.fromisoformat(text[:10]).date()


def admitted_field_from_mapping(payload: Mapping) -> MiningAdmissionField:
    base_payload = payload.get("base")
    if not isinstance(base_payload, Mapping):
        raise ValueError("standard_frame.admitted_fields item requires base mapping")
    return MiningAdmissionField(
        base=optional_field_from_mapping(base_payload),
        source_kind=str(payload["source_kind"]),
        payload=dict(payload.get("payload", {}) or {}),
        rationale=payload.get("rationale"),
        admitted_by=payload.get("admitted_by"),
    )


def optional_field_from_mapping(payload: Mapping) -> OptionalStandardFrameField:
    return OptionalStandardFrameField(
        source_interface=str(payload["source_interface"]),
        source_field=str(payload["source_field"]),
        feature_name=str(payload["feature_name"]),
        dtype=str(payload.get("dtype", "float64")),
        join_key=tuple(str(item) for item in payload.get("join_key", ("datetime", "instrument"))),
        time_policy=str(payload["time_policy"]),
        missing_policy=str(payload.get("missing_policy", "nan")),
        allowed_usage=tuple(str(item) for item in payload.get("allowed_usage", ())),
    )


def frame_date_bound(frame: pl.DataFrame, bound: str) -> str | None:
    if frame.is_empty() or "datetime" not in frame.columns:
        return None
    expr = pl.col("datetime").min() if bound == "min" else pl.col("datetime").max()
    value = frame.select(expr.alias("value")).item()
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value)
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text[:10]


def date_expr(column: str) -> pl.Expr:
    digits = pl.col(column).cast(pl.Utf8).str.replace_all(r"\D", "")
    normalized = pl.when(digits.str.len_chars() == 6).then(digits + pl.lit("01")).otherwise(digits.str.slice(0, 8))
    return normalized.str.strptime(pl.Date, "%Y%m%d", strict=False)


def missing_float_expr(column: str) -> pl.Expr:
    value = pl.col(column).cast(pl.Float64, strict=False)
    return value.is_null() | value.is_nan()


def missing_marker_expr(column: str) -> pl.Expr:
    return pl.col(column).fill_null(True).cast(pl.Boolean, strict=False).fill_null(True)


def filter_frame_by_markets(
    frame: pl.DataFrame,
    include_markets: Sequence[str],
    exclude_markets: Sequence[str],
) -> pl.DataFrame:
    include = [str(value).upper() for value in include_markets if str(value).strip()]
    exclude = [str(value).upper() for value in exclude_markets if str(value).strip()]
    if not include and not exclude:
        return frame
    if "ts_code" not in frame.columns:
        return frame
    market = pl.col("ts_code").cast(pl.Utf8).str.to_uppercase().str.extract(r"\.([A-Z]+)$", 1)
    predicate = pl.lit(True)
    if include:
        predicate = predicate & market.is_in(include)
    if exclude:
        predicate = predicate & (~market.is_in(exclude))
    return frame.filter(predicate)


def compact_date(value: date | datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().strftime("%Y%m%d")
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    digits = re.sub(r"\D", "", str(value))
    return digits[:8] if digits else None


def frame_date_bounds(frame: pl.DataFrame) -> tuple[date | None, date | None]:
    if frame.is_empty() or "datetime" not in frame.columns:
        return None, None
    dates = frame.get_column("datetime")
    return dates.min(), dates.max()


def asof_lte_filters(frame: pl.DataFrame, date_column: str) -> list[tuple[str, str, object]]:
    _min_date, max_date = frame_date_bounds(frame)
    compact_max = compact_date(max_date)
    if compact_max is None:
        return []
    return [(date_column, "<=", compact_max)]


def event_window_filters(
    frame: pl.DataFrame,
    event_date_column: str,
    visibility_column: str,
    window_days: int,
) -> list[tuple[str, str, object]]:
    min_date, max_date = frame_date_bounds(frame)
    compact_max = compact_date(max_date)
    if compact_max is None:
        return []
    filters: list[tuple[str, str, object]] = [(visibility_column, "<=", compact_max)]
    if min_date is not None:
        compact_start = compact_date(min_date - timedelta(days=window_days))
        if compact_start is not None:
            filters.append((event_date_column, "between", (compact_start, compact_max)))
    return filters


def event_source_column(feature_name: str, window_days: int, *, amount_column: str | None) -> str:
    name = feature_name.lstrip("$")
    if name.endswith(f"_count_{window_days}d") or name.endswith("_recency_days"):
        return name
    if amount_column:
        return f"{_event_prefix(feature_name, window_days)}_amount_{window_days}d"
    return name


def _event_prefix(feature_name: str, window_days: int) -> str:
    name = feature_name.lstrip("$")
    suffixes = (
        f"_count_{window_days}d",
        f"_amount_{window_days}d",
        f"_vol_{window_days}d",
        f"_ratio_{window_days}d",
        "_recency_days",
    )
    for suffix in suffixes:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    match = re.match(r"(.+?)_(count|amount|vol|ratio|recency)(?:_\d+d|_days)?$", name)
    return match.group(1) if match else name


def aggregate_expr(field_item: MiningAdmissionField, aggregation: str) -> pl.Expr:
    value = pl.col(field_item.source_field).cast(dtype(field_item.dtype), strict=False)
    if aggregation == "sum":
        return value.sum()
    if aggregation == "mean":
        return value.mean()
    if aggregation == "count":
        return pl.len().cast(dtype(field_item.dtype))
    raise ValueError(f"unsupported aggregate context aggregation for {field_item.feature_name}: {aggregation}")


def dtype(dtype_name: str) -> pl.DataType:
    normalized = dtype_name.lower()
    if normalized in {"float", "float64"}:
        return pl.Float64
    if normalized == "float32":
        return pl.Float32
    if normalized in {"int", "int64"}:
        return pl.Int64
    if normalized == "int32":
        return pl.Int32
    if normalized in {"str", "string", "utf8"}:
        return pl.Utf8
    raise ValueError(f"unsupported standard-frame dtype: {dtype_name}")
