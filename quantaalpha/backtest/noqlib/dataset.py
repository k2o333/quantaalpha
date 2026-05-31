"""No-qlib dataset 构建和 qlib processor 等价子集。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import polars as pl


@dataclass
class NoQlibDataset:
    """训练、验证、测试切分后的矩阵。"""

    combined: pl.DataFrame
    feature_columns: list[str]
    label_column: str
    segments: dict[str, tuple[str, str]]
    learn_combined: pl.DataFrame | None = None
    raw_labels: pl.DataFrame | None = None

    def segment(self, name: str) -> pl.DataFrame:
        source = self.learn_combined if name in {"train", "valid"} and self.learn_combined is not None else self.combined
        start, end = self.segments[name]
        return source.filter(pl.col("datetime").is_between(pl.lit(start).str.strptime(pl.Datetime("ns")), pl.lit(end).str.strptime(pl.Datetime("ns"))))


class NoQlibDatasetBuilder:
    """构建 feature/label combined frame。"""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def build(self, features: pl.DataFrame, labels: pl.DataFrame) -> NoQlibDataset:
        """对齐键列并应用 Fillna/ProcessInf/DropnaLabel/CSRankNorm。"""
        features = _normalize_frame(features)
        labels = _normalize_frame(labels)
        feature_columns = [column for column in features.columns if column not in {"datetime", "instrument"}]
        label_column = "LABEL0"
        if label_column not in labels.columns:
            value_columns = [column for column in labels.columns if column not in {"datetime", "instrument"}]
            if len(value_columns) != 1:
                raise ValueError("noqlib label frame must contain LABEL0 or exactly one value column")
            labels = labels.rename({value_columns[0]: label_column})
        raw_labels = labels.select(["datetime", "instrument", label_column]).sort(["datetime", "instrument"])
        combined = features.join(raw_labels, on=["datetime", "instrument"], how="inner")
        if combined.is_empty():
            raise ValueError("noqlib feature/label key intersection is empty")
        segments = _segments(self.config)
        _validate_segment_coverage(
            combined,
            segments,
            feature_bounds=_frame_bounds(features),
            label_bounds=_frame_bounds(raw_labels),
        )
        combined = combined.with_columns(*[pl.when(pl.col(column).is_infinite() | pl.col(column).is_nan()).then(None).otherwise(pl.col(column)).fill_null(0.0).alias(column) for column in feature_columns])
        combined = _cross_section_rank_norm(combined, feature_columns)
        combined = _cross_section_rank_norm(combined, [label_column])
        return NoQlibDataset(
            combined=combined.sort(["datetime", "instrument"]),
            feature_columns=feature_columns,
            label_column=label_column,
            segments=segments,
            learn_combined=None,
            raw_labels=raw_labels,
        )


def _normalize_frame(frame: pl.DataFrame) -> pl.DataFrame:
    missing = {"datetime", "instrument"} - set(frame.columns)
    if missing:
        raise ValueError(f"noqlib frame missing key columns: {sorted(missing)}")
    datetime_expr = pl.col("datetime").str.strptime(pl.Datetime("ns"), strict=False) if frame.schema["datetime"] == pl.Utf8 else pl.col("datetime").cast(pl.Datetime("ns"), strict=False)
    return frame.with_columns(
        datetime_expr.alias("datetime"),
        pl.col("instrument").cast(pl.Utf8),
    )


def _cross_section_rank_norm(frame: pl.DataFrame, columns: list[str]) -> pl.DataFrame:
    return frame.with_columns(*[((pl.col(column).rank(method="average").over("datetime") / pl.len().over("datetime")) - 0.5).mul(3.46).alias(column) for column in columns])


def _segments(config: dict[str, Any]) -> dict[str, tuple[str, str]]:
    raw_segments = config.get("dataset", {}).get("segments", {})
    return {name: (str(value[0]), str(value[1])) for name, value in raw_segments.items()}


def _frame_bounds(frame: pl.DataFrame) -> tuple[str, str]:
    """Return ISO date bounds for one normalized noqlib frame."""
    start, end = frame.select(
        pl.col("datetime").min().alias("min_datetime"),
        pl.col("datetime").max().alias("max_datetime"),
    ).row(0)
    return start.date().isoformat(), end.date().isoformat()


def _validate_segment_coverage(
    combined: pl.DataFrame,
    segments: dict[str, tuple[str, str]],
    *,
    feature_bounds: tuple[str, str] | None = None,
    label_bounds: tuple[str, str] | None = None,
) -> None:
    """Reject ambiguous or uncovered model-evaluation windows before training."""
    required = {"train", "test"}
    missing = sorted(required - set(segments))
    if missing:
        raise ValueError(f"noqlib dataset segments missing required entries: {missing}")

    parsed: list[tuple[str, datetime, datetime]] = []
    for name in ("train", "valid", "test"):
        if name not in segments:
            continue
        start_text, end_text = segments[name]
        start = datetime.fromisoformat(start_text)
        end = datetime.fromisoformat(end_text)
        if start > end:
            raise ValueError(f"noqlib dataset segment has reversed bounds: {name}={segments[name]}")
        parsed.append((name, start, end))

    for (_, _, previous_end), (name, start, _) in zip(parsed, parsed[1:]):
        if previous_end >= start:
            raise ValueError(f"noqlib dataset segments must be ordered and mutually exclusive: overlap before {name}")

    actual_start, actual_end = combined.select(
        pl.col("datetime").min().alias("min_datetime"),
        pl.col("datetime").max().alias("max_datetime"),
    ).row(0)
    for name, start, end in parsed:
        requested = segments[name]
        if start < actual_start or end > actual_end:
            raise ValueError(
                "noqlib segment coverage validation failed: "
                f"requested {name}={requested}, "
                f"feature bounds={feature_bounds}, "
                f"label bounds={label_bounds}, "
                f"actual combined bounds=('{actual_start.date().isoformat()}', '{actual_end.date().isoformat()}')"
            )
        segment_rows = combined.filter(pl.col("datetime").is_between(start, end)).height
        if segment_rows == 0:
            raise ValueError(f"noqlib segment coverage validation failed: requested {name}={requested} has 0 rows")
