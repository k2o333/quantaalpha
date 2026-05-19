"""App5-backed backtest standard-frame builder."""

from __future__ import annotations

import hashlib
import json
import re
import warnings
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
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
from quantaalpha.backtest.mining_admission import MiningAdmissionField


@dataclass(frozen=True)
class StandardFrameRequest:
    """Request identity for an App5 backtest standard frame."""

    start_date: str | None = None
    end_date: str | None = None
    instruments: tuple[str, ...] = ()
    daily_interface: str = "daily"
    adjustment: str = "raw"
    optional_fields: tuple[OptionalStandardFrameField, ...] = ()
    admitted_fields: tuple[MiningAdmissionField, ...] = ()
    storage_root: str = "data"
    materialized_cache_root: str | None = None

    def identity(self) -> dict[str, Any]:
        return {
            "daily_interface": self.daily_interface,
            "adjustment": self.adjustment,
            "end_date": self.end_date,
            "instruments": list(self.instruments),
            "admitted_fields": [field_item.identity() for field_item in self.admitted_fields],
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
        for field_item in request.admitted_fields:
            validate_optional_standard_frame_field(field_item.base)

        frame = self._read_daily_frame(request)
        admitted_fields = self._resolved_admitted_fields(request)
        daily_panel_fields = [field for field in admitted_fields if field.source_kind == "daily_panel"]
        frame = self._join_daily_panel_batches(frame, request, daily_panel_fields)
        feature_view_fields = [field for field in admitted_fields if field.source_kind != "daily_panel"]
        frame = self._join_feature_view_batches(frame, request, feature_view_fields)
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

    def _resolved_admitted_fields(self, request: StandardFrameRequest) -> tuple[MiningAdmissionField, ...]:
        if request.admitted_fields:
            return request.admitted_fields
        return tuple(
            MiningAdmissionField(
                base=field_item,
                source_kind="daily_panel",
                payload={
                    "source_interface": field_item.source_interface,
                    "source_field": field_item.source_field,
                },
            )
            for field_item in request.optional_fields
        )

    def _join_daily_panel_batches(
        self,
        frame: pl.DataFrame,
        request: StandardFrameRequest,
        fields: Sequence[MiningAdmissionField],
    ) -> pl.DataFrame:
        grouped: dict[tuple[str, str], list[MiningAdmissionField]] = {}
        for field_item in fields:
            if field_item.join_key != ("datetime", "instrument"):
                raise ValueError(
                    f"unsupported optional field join_key for {field_item.feature_name}: {field_item.join_key}"
                )
            if field_item.time_policy not in {"same_trade_date_no_lookahead"}:
                raise ValueError(
                    f"unsupported optional field time_policy for {field_item.feature_name}: {field_item.time_policy}"
                )
            grouped.setdefault((field_item.source_interface, field_item.time_policy), []).append(field_item)

        joined = frame
        for (source_interface, _time_policy), group in grouped.items():
            joined = self._join_daily_panel_batch(joined, request, source_interface, group)
        return joined

    def _join_daily_panel_batch(
        self,
        frame: pl.DataFrame,
        request: StandardFrameRequest,
        source_interface: str,
        fields: Sequence[MiningAdmissionField],
    ) -> pl.DataFrame:
        source_fields = list(dict.fromkeys(field.source_field for field in fields))
        source = self.adapter.read(
            source_interface,
            start_date=request.start_date,
            end_date=request.end_date,
            columns=["trade_date", "ts_code", *source_fields],
            unique=True,
        )
        if source.is_empty():
            expressions = []
            for field_item in fields:
                if field_item.missing_policy == "required":
                    raise ValueError(f"optional standard-frame field source is empty: {field_item.feature_name}")
                expressions.append(pl.lit(None).cast(_dtype(field_item.dtype)).alias(field_item.feature_name))
            return frame.with_columns(expressions)

        select_exprs = [
            _date_expr("trade_date").alias("datetime"),
            pl.col("ts_code").cast(pl.Utf8).alias("instrument"),
        ]
        select_exprs.extend(
            pl.col(field_item.source_field).cast(_dtype(field_item.dtype), strict=False).alias(field_item.feature_name)
            for field_item in fields
        )
        source = source.select(select_exprs).unique(subset=["datetime", "instrument"], keep="first", maintain_order=True)
        joined = frame.join(source, on=["datetime", "instrument"], how="left")
        for field_item in fields:
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
            "source_interfaces": [
                request.daily_interface,
                *[field.source_interface for field in request.optional_fields],
                *[field.source_interface for field in request.admitted_fields],
            ],
            "app5_interface_admissions": [asdict(item) for item in admissions],
        }

    def _join_feature_view_batches(
        self,
        frame: pl.DataFrame,
        request: StandardFrameRequest,
        fields: Sequence[MiningAdmissionField],
    ) -> pl.DataFrame:
        grouped: dict[tuple[object, ...], list[MiningAdmissionField]] = {}
        for field_item in fields:
            grouped.setdefault(field_item.batch_key(), []).append(field_item)

        joined = frame
        for batch_key, group in grouped.items():
            try:
                if group[0].source_kind == "dimension_asof":
                    joined = self._join_dimension_asof_batch(joined, request, group)
                elif group[0].source_kind == "event_window":
                    joined = self._join_event_window_batch(joined, request, group)
                elif group[0].source_kind == "canonical_financial_asof":
                    joined = self._join_canonical_financial_asof_batch(joined, request, group)
                else:
                    raise ValueError(f"unsupported feature-view source_kind: {group[0].source_kind}")
            except Exception as exc:
                feature_names = [field.feature_name for field in group]
                raise ValueError(
                    f"failed to materialize feature-view batch source_kind={group[0].source_kind} "
                    f"batch_key={batch_key} feature_names={feature_names}: {exc}"
                ) from exc
        return joined

    def _join_dimension_asof_batch(
        self,
        frame: pl.DataFrame,
        request: StandardFrameRequest,
        fields: Sequence[MiningAdmissionField],
    ) -> pl.DataFrame:
        from app5.feature_layer.dimension import join_effective_dimension_asof

        source_interface = fields[0].source_interface
        effective_date_column = str(fields[0].payload["effective_date_column"])
        source_fields = list(dict.fromkeys(field.source_field for field in fields))
        source = self.adapter.read(
            source_interface,
            start_date=request.start_date,
            end_date=request.end_date,
            columns=["ts_code", effective_date_column, *source_fields],
            unique=True,
        )
        max_date = frame.get_column("datetime").max()
        if source.is_empty():
            joined = join_effective_dimension_asof(frame, source, effective_date_column=effective_date_column, fields=source_fields)
        else:
            source = source.with_columns(_date_expr(effective_date_column).alias(effective_date_column))
            if max_date is not None:
                source = source.filter(pl.col(effective_date_column) <= max_date)
            joined = join_effective_dimension_asof(frame, source, effective_date_column=effective_date_column, fields=source_fields)
        return self._project_joined_feature_columns(joined, fields)

    def _join_event_window_batch(
        self,
        frame: pl.DataFrame,
        request: StandardFrameRequest,
        fields: Sequence[MiningAdmissionField],
    ) -> pl.DataFrame:
        from app5.feature_layer.event_state import build_event_window_features

        first = fields[0]
        event_date_column = str(first.payload["event_date_column"])
        visibility_column = str(first.payload["visibility_column"])
        amount_column = first.payload.get("amount_column")
        amount_column = str(amount_column) if amount_column else None
        window_days = int(first.payload["window_days"])
        source_columns = ["ts_code", event_date_column, visibility_column]
        if amount_column:
            source_columns.append(amount_column)
        events = self.adapter.read(
            first.source_interface,
            start_date=request.start_date,
            end_date=request.end_date,
            columns=list(dict.fromkeys(source_columns)),
            unique=True,
        )
        max_date = frame.get_column("datetime").max()
        if not events.is_empty():
            events = events.with_columns(
                _date_expr(event_date_column).alias(event_date_column),
                _date_expr(visibility_column).alias(visibility_column),
            )
            if max_date is not None:
                events = events.filter(pl.col(visibility_column) <= max_date)
        calendar = frame.select(pl.col("datetime").cast(pl.Date).alias("trade_date")).unique().sort("trade_date")
        instruments = sorted(frame.get_column("instrument").unique().to_list())
        joined = frame
        for field_item in fields:
            prefix = _event_prefix(field_item.feature_name, window_days)
            features = build_event_window_features(
                events,
                calendar,
                instruments=instruments,
                event_date_column=event_date_column,
                visibility_column=visibility_column,
                amount_column=amount_column,
                window_days=window_days,
                prefix=prefix,
            )
            source_column = field_item.feature_name.lstrip("$")
            feature_frame = features.select(
                pl.col("trade_date").cast(pl.Date).alias("datetime"),
                pl.col("instrument").cast(pl.Utf8),
                pl.col(source_column).cast(_dtype(field_item.dtype), strict=False).alias(field_item.feature_name),
            )
            joined = joined.join(feature_frame, on=["datetime", "instrument"], how="left")
            if field_item.missing_policy == "zero":
                joined = joined.with_columns(pl.col(field_item.feature_name).fill_null(0))
        return joined

    def _join_canonical_financial_asof_batch(
        self,
        frame: pl.DataFrame,
        request: StandardFrameRequest,
        fields: Sequence[MiningAdmissionField],
    ) -> pl.DataFrame:
        table = str(fields[0].payload["canonical_table"])
        table_root = Path(str(fields[0].payload.get("canonical_root") or Path(request.storage_root) / "canonical_app5")) / table
        parquet_files = sorted(path for path in table_root.rglob("*.parquet") if path.is_file())
        source_fields = list(dict.fromkeys(field.source_field for field in fields))
        if not parquet_files:
            return frame.with_columns(
                [
                    pl.lit(None).cast(_dtype(field.dtype)).alias(field.feature_name)
                    for field in fields
                ]
            )
        max_date = frame.get_column("datetime").max()
        lazy_frame = pl.scan_parquet([str(path) for path in parquet_files]).with_columns(
            _date_expr("ann_date").alias("ann_date")
        )
        if max_date is not None:
            lazy_frame = lazy_frame.filter(pl.col("ann_date") <= max_date)
        for optional_filter in ("report_type", "comp_type"):
            if optional_filter in fields[0].payload:
                lazy_frame = lazy_frame.filter(pl.col(optional_filter) == str(fields[0].payload[optional_filter]))
        financial = (
            lazy_frame.select(
                pl.col("ts_code").cast(pl.Utf8).alias("instrument"),
                pl.col("ann_date"),
                *[pl.col(source_field) for source_field in source_fields],
            )
            .collect()
            .sort(["instrument", "ann_date"])
        )
        if financial.is_empty():
            return frame.with_columns(
                [
                    pl.lit(None).cast(_dtype(field.dtype)).alias(field.feature_name)
                    for field in fields
                ]
            )
        left = frame.sort(["instrument", "datetime"])
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="Sortedness of columns cannot be checked when 'by' groups provided",
                category=UserWarning,
            )
            joined = left.join_asof(
                financial,
                left_on="datetime",
                right_on="ann_date",
                by="instrument",
                strategy="backward",
            )
        return self._project_joined_feature_columns(joined.drop("ann_date"), fields).sort(["datetime", "instrument"])

    def _project_joined_feature_columns(
        self,
        frame: pl.DataFrame,
        fields: Sequence[MiningAdmissionField],
    ) -> pl.DataFrame:
        expressions = []
        drop_columns = []
        for field_item in fields:
            if field_item.source_field == field_item.feature_name:
                continue
            if field_item.source_field in frame.columns:
                expressions.append(
                    pl.col(field_item.source_field)
                    .cast(_dtype(field_item.dtype), strict=False)
                    .alias(field_item.feature_name)
                )
                drop_columns.append(field_item.source_field)
        projected = frame.with_columns(expressions) if expressions else frame
        removable = [column for column in drop_columns if column in projected.columns and column not in {field.feature_name for field in fields}]
        return projected.drop(removable) if removable else projected


def request_from_mapping(payload: Mapping[str, Any]) -> StandardFrameRequest:
    """Parse a config mapping into a StandardFrameRequest."""
    optional_fields_payload = payload.get("optional_fields", ()) or ()
    if not isinstance(optional_fields_payload, Sequence) or isinstance(optional_fields_payload, (str, bytes)):
        raise ValueError("standard_frame.optional_fields must be a sequence")
    admitted_fields_payload = payload.get("admitted_fields", ()) or ()
    if not isinstance(admitted_fields_payload, Sequence) or isinstance(admitted_fields_payload, (str, bytes)):
        raise ValueError("standard_frame.admitted_fields must be a sequence")
    return StandardFrameRequest(
        start_date=payload.get("start_date"),
        end_date=payload.get("end_date"),
        instruments=tuple(str(item) for item in payload.get("instruments", ()) or ()),
        daily_interface=str(payload.get("daily_interface", "daily")),
        adjustment=str(payload.get("adjustment", "raw")),
        optional_fields=tuple(_optional_field_from_mapping(item) for item in optional_fields_payload),
        admitted_fields=tuple(_admitted_field_from_mapping(item) for item in admitted_fields_payload),
        storage_root=str(payload.get("storage_root", "data")),
        materialized_cache_root=payload.get("materialized_cache_root"),
    )


def _admitted_field_from_mapping(payload: Mapping[str, Any]) -> MiningAdmissionField:
    base_payload = payload.get("base")
    if not isinstance(base_payload, Mapping):
        raise ValueError("standard_frame.admitted_fields item requires base mapping")
    return MiningAdmissionField(
        base=_optional_field_from_mapping(base_payload),
        source_kind=str(payload["source_kind"]),
        payload=dict(payload.get("payload", {}) or {}),
        rationale=payload.get("rationale"),
        admitted_by=payload.get("admitted_by"),
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


def _event_prefix(feature_name: str, window_days: int) -> str:
    name = feature_name.lstrip("$")
    suffixes = (f"_count_{window_days}d", f"_amount_{window_days}d", "_recency_days")
    for suffix in suffixes:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    match = re.match(r"(.+?)_(count|amount|recency)(?:_\d+d|_days)?$", name)
    if match:
        return match.group(1)
    return name


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
