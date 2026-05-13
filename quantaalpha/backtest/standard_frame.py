"""App5-backed backtest standard-frame builder."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import polars as pl

from quantaalpha.backtest.contracts import (
    OptionalStandardFrameField,
    classify_app5_interface,
    inventory_clean_active_interfaces,
    validate_optional_standard_frame_field,
    validate_standard_frame_columns,
)


@dataclass(frozen=True)
class StandardFrameRequest:
    """Request identity for an App5 backtest standard frame."""

    start_date: str | None = None
    end_date: str | None = None
    instruments: tuple[str, ...] = ()
    daily_interface: str = "daily"
    adjustment: str = "raw"
    optional_fields: tuple[OptionalStandardFrameField, ...] = ()
    storage_root: str = "data"
    materialized_cache_root: str | None = None

    def identity(self) -> dict[str, Any]:
        return {
            "daily_interface": self.daily_interface,
            "adjustment": self.adjustment,
            "end_date": self.end_date,
            "instruments": list(self.instruments),
            "optional_fields": [asdict(field_item) for field_item in self.optional_fields],
            "start_date": self.start_date,
            "storage_root": self.storage_root,
        }

    def identity_hash(self) -> str:
        payload = json.dumps(self.identity(), ensure_ascii=True, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class StandardFrameBuildResult:
    """Built standard-frame artifact and manifest."""

    frame: pl.DataFrame
    manifest: dict[str, Any]
    parquet_path: str | None = None
    manifest_path: str | None = None


class App5StandardFrameBuilder:
    """Build the governed standard frame from App5 clean/active data."""

    def __init__(self, *, adapter: Any | None = None, storage_root: str | Path = "data") -> None:
        if adapter is None:
            from training.adapter.app5_parquet_adapter import App5ParquetAdapter

            adapter = App5ParquetAdapter(storage_root=storage_root)
        self.adapter = adapter
        self.storage_root = Path(storage_root)

    def build(self, request: StandardFrameRequest) -> StandardFrameBuildResult:
        """Build the minimal frame plus explicitly admitted optional fields."""
        classify_app5_interface(request.daily_interface)
        for field_item in request.optional_fields:
            validate_optional_standard_frame_field(field_item)

        frame = self._read_daily_frame(request)
        for field_item in request.optional_fields:
            frame = self._join_optional_field(frame, request, field_item)
        validate_standard_frame_columns(frame.columns)
        manifest = self._manifest(request, frame)
        parquet_path: str | None = None
        manifest_path: str | None = None
        if request.materialized_cache_root:
            cache_dir = Path(request.materialized_cache_root) / request.identity_hash()
            cache_dir.mkdir(parents=True, exist_ok=True)
            parquet_path = str(cache_dir / "standard_frame.parquet")
            manifest_path = str(cache_dir / "manifest.json")
            frame.write_parquet(parquet_path)
            Path(manifest_path).write_text(
                json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        return StandardFrameBuildResult(
            frame=frame,
            manifest=manifest,
            parquet_path=parquet_path,
            manifest_path=manifest_path,
        )

    def _read_daily_frame(self, request: StandardFrameRequest) -> pl.DataFrame:
        adjustment = str(request.adjustment or "raw").lower()
        if adjustment not in {"raw", "qfq", "hfq"}:
            raise ValueError(f"unsupported standard frame adjustment: {request.adjustment}")
        price_columns = ["open", "high", "low", "close"]
        source_price_columns = price_columns if adjustment == "raw" else [f"{field}_{adjustment}" for field in price_columns]
        columns = ["trade_date", "ts_code", *source_price_columns, "vol", "amount", "pct_chg"]
        raw = self.adapter.read(
            request.daily_interface,
            start_date=request.start_date,
            end_date=request.end_date,
            columns=columns,
            unique=True,
        )
        if raw.is_empty():
            raise ValueError(f"standard frame source is empty: {request.daily_interface}")
        missing_prices = sorted(set(source_price_columns) - set(raw.columns))
        if missing_prices:
            raise ValueError(
                f"standard frame adjustment={adjustment} requires columns missing from "
                f"{request.daily_interface}: {missing_prices}"
            )
        if request.instruments:
            raw = raw.filter(pl.col("ts_code").cast(pl.Utf8).is_in(list(request.instruments)))
        frame = raw.with_columns(
            _date_expr("trade_date").alias("datetime"),
            pl.col("ts_code").cast(pl.Utf8).alias("instrument"),
            pl.col(source_price_columns[0]).cast(pl.Float64, strict=False).alias("$open"),
            pl.col(source_price_columns[1]).cast(pl.Float64, strict=False).alias("$high"),
            pl.col(source_price_columns[2]).cast(pl.Float64, strict=False).alias("$low"),
            pl.col(source_price_columns[3]).cast(pl.Float64, strict=False).alias("$close"),
            pl.col("vol").cast(pl.Float64, strict=False).fill_null(0.0).alias("$volume"),
        )
        raw_vwap_expr = (
            pl.when(pl.col("$volume") > 0)
            .then(pl.col("amount").cast(pl.Float64, strict=False) * 10.0 / pl.col("$volume"))
            .otherwise(pl.col("$close"))
        )
        if adjustment == "raw":
            vwap_expr = raw_vwap_expr
        else:
            # App5 does not expose adjusted VWAP; qlib bin data also lacks a persisted vwap field.
            # Use adjusted close as the explicit parity-safe vwap proxy.
            vwap_expr = pl.col("$close")
        pct = pl.col("pct_chg").cast(pl.Float64, strict=False).fill_null(0.0)
        return (
            frame.with_columns(
                vwap_expr.fill_null(pl.col("$close")).alias("$vwap"),
                pl.when(pct.abs() > 1.0).then(pct / 100.0).otherwise(pct).alias("$return"),
            )
            .select(["datetime", "instrument", "$open", "$high", "$low", "$close", "$volume", "$vwap", "$return"])
            .unique(subset=["datetime", "instrument"], keep="first", maintain_order=True)
            .sort(["datetime", "instrument"])
        )

    def _join_optional_field(
        self,
        frame: pl.DataFrame,
        request: StandardFrameRequest,
        field_item: OptionalStandardFrameField,
    ) -> pl.DataFrame:
        if field_item.join_key != ("datetime", "instrument"):
            raise ValueError(
                f"unsupported optional field join_key for {field_item.feature_name}: {field_item.join_key}"
            )
        if field_item.time_policy not in {"same_trade_date_no_lookahead"}:
            raise ValueError(
                f"unsupported optional field time_policy for {field_item.feature_name}: {field_item.time_policy}"
            )
        source = self.adapter.read(
            field_item.source_interface,
            start_date=request.start_date,
            end_date=request.end_date,
            columns=["trade_date", "ts_code", field_item.source_field],
            unique=True,
        )
        if source.is_empty():
            if field_item.missing_policy == "required":
                raise ValueError(f"optional standard-frame field source is empty: {field_item.feature_name}")
            return frame.with_columns(pl.lit(None).cast(_dtype(field_item.dtype)).alias(field_item.feature_name))
        source = source.select(
            _date_expr("trade_date").alias("datetime"),
            pl.col("ts_code").cast(pl.Utf8).alias("instrument"),
            pl.col(field_item.source_field).cast(_dtype(field_item.dtype), strict=False).alias(field_item.feature_name),
        ).unique(subset=["datetime", "instrument"], keep="first", maintain_order=True)
        joined = frame.join(source, on=["datetime", "instrument"], how="left")
        if field_item.missing_policy == "required" and joined.get_column(field_item.feature_name).null_count() > 0:
            raise ValueError(f"required optional standard-frame field has missing values: {field_item.feature_name}")
        return joined

    def _manifest(self, request: StandardFrameRequest, frame: pl.DataFrame) -> dict[str, Any]:
        admissions = inventory_clean_active_interfaces(self.storage_root)
        return {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "cache_identity": request.identity_hash(),
            "request": request.identity(),
            "standard_frame": {
                "columns": frame.columns,
                "adjustment": request.adjustment,
                "row_count": frame.height,
                "required_columns": ["datetime", "instrument", "$open", "$high", "$low", "$close", "$volume", "$vwap", "$return"],
            },
            "source_interfaces": [request.daily_interface, *[field.source_interface for field in request.optional_fields]],
            "app5_interface_admissions": [asdict(item) for item in admissions],
        }


def request_from_mapping(payload: Mapping[str, Any]) -> StandardFrameRequest:
    """Parse a config mapping into a StandardFrameRequest."""
    optional_fields_payload = payload.get("optional_fields", ()) or ()
    if not isinstance(optional_fields_payload, Sequence) or isinstance(optional_fields_payload, (str, bytes)):
        raise ValueError("standard_frame.optional_fields must be a sequence")
    return StandardFrameRequest(
        start_date=payload.get("start_date"),
        end_date=payload.get("end_date"),
        instruments=tuple(str(item) for item in payload.get("instruments", ()) or ()),
        daily_interface=str(payload.get("daily_interface", "daily")),
        adjustment=str(payload.get("adjustment", "raw")),
        optional_fields=tuple(_optional_field_from_mapping(item) for item in optional_fields_payload),
        storage_root=str(payload.get("storage_root", "data")),
        materialized_cache_root=payload.get("materialized_cache_root"),
    )


def _optional_field_from_mapping(payload: Mapping[str, Any]) -> OptionalStandardFrameField:
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


def _date_expr(column: str) -> pl.Expr:
    return pl.col(column).cast(pl.Utf8).str.replace_all(r"\D", "").str.slice(0, 8).str.strptime(pl.Date, "%Y%m%d")


def _dtype(dtype: str) -> pl.DataType:
    normalized = dtype.lower()
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
    raise ValueError(f"unsupported standard-frame dtype: {dtype}")
