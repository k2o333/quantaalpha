"""单因子表现历史 Parquet 存储。"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import polars as pl


SUMMARY_REQUIRED_COLUMNS = {
    "schema_version",
    "validation_id",
    "factor_id",
    "expression_hash",
    "factor_name",
    "factor_expression",
    "translated_expression",
    "source",
    "validated_at",
    "success",
    "passed",
    "created_at",
}

SUMMARY_SCHEMA = {
    "schema_version": pl.Int64,
    "validation_id": pl.String,
    "factor_id": pl.String,
    "expression_hash": pl.String,
    "factor_name": pl.String,
    "factor_expression": pl.String,
    "translated_expression": pl.String,
    "source": pl.String,
    "run_id": pl.String,
    "validated_at": pl.String,
    "train_start": pl.String,
    "train_end": pl.String,
    "valid_start": pl.String,
    "valid_end": pl.String,
    "test_start": pl.String,
    "test_end": pl.String,
    "success": pl.Boolean,
    "status": pl.String,
    "passed": pl.Boolean,
    "ic_mean": pl.Float64,
    "ic_std": pl.Float64,
    "icir": pl.Float64,
    "rank_ic_mean": pl.Float64,
    "rank_icir": pl.Float64,
    "positive_ratio": pl.Float64,
    "daily_ic_count": pl.Int64,
    "min_ic": pl.Float64,
    "min_rank_ic": pl.Float64,
    "annualized_return": pl.Float64,
    "information_ratio": pl.Float64,
    "max_drawdown": pl.Float64,
    "computation_time_seconds": pl.Float64,
    "error_message": pl.String,
    "extra_json": pl.String,
    "created_at": pl.String,
}


@dataclass(frozen=True)
class PerformanceHistoryConfig:
    """表现历史存储配置。"""

    enabled: bool = True
    root: str = "third_party/quantaalpha/data/factorlib/performance_history"
    compression: str = "zstd"
    write_summary: bool = True
    write_series: bool = True
    update_latest_snapshot: bool = True

    @classmethod
    def from_dict(cls, data: dict | None) -> "PerformanceHistoryConfig":
        if not data:
            return cls()
        return cls(
            enabled=data.get("enabled", True),
            root=data.get("root", cls.root),
            compression=data.get("compression", "zstd"),
            write_summary=data.get("write_summary", True),
            write_series=data.get("write_series", True),
            update_latest_snapshot=data.get("update_latest_snapshot", True),
        )


def _as_iso(value: datetime | date | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _period_value(execution_periods: dict[str, tuple[str, str]], segment: str, index: int) -> str | None:
    period = execution_periods.get(segment)
    if not period:
        return None
    return period[index]


def build_summary_row(
    *,
    factor_id: str,
    factor_name: str,
    factor_expression: str,
    translated_expression: str,
    source: str,
    validated_at: datetime | None,
    execution_periods: dict[str, tuple[str, str]] | None,
    status: str,
    passed: bool,
    ic_mean: float | None = None,
    ic_std: float | None = None,
    icir: float | None = None,
    rank_ic_mean: float | None = None,
    rank_icir: float | None = None,
    positive_ratio: float | None = None,
    daily_ic_count: int | None = None,
    min_ic: float | None = None,
    min_rank_ic: float | None = None,
    annualized_return: float | None = None,
    information_ratio: float | None = None,
    max_drawdown: float | None = None,
    computation_time_seconds: float | None = None,
    error_message: str | None = None,
    run_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构造 summary 表的一行记录。"""

    validated_at = validated_at or datetime.now()
    execution_periods = execution_periods or {}
    expression_hash = hashlib.md5(factor_expression.encode("utf-8")).hexdigest()
    window_hash = hashlib.md5(json.dumps(execution_periods, sort_keys=True).encode("utf-8")).hexdigest()[:8]
    validation_id = f"{source}:{factor_id}:{validated_at.strftime('%Y%m%d%H%M%S')}:{window_hash}"

    return {
        "schema_version": 1,
        "validation_id": validation_id,
        "factor_id": factor_id,
        "expression_hash": expression_hash,
        "factor_name": factor_name,
        "factor_expression": factor_expression,
        "translated_expression": translated_expression,
        "source": source,
        "run_id": run_id,
        "validated_at": validated_at.isoformat(),
        "train_start": _period_value(execution_periods, "train", 0),
        "train_end": _period_value(execution_periods, "train", 1),
        "valid_start": _period_value(execution_periods, "valid", 0),
        "valid_end": _period_value(execution_periods, "valid", 1),
        "test_start": _period_value(execution_periods, "test", 0),
        "test_end": _period_value(execution_periods, "test", 1),
        "success": status == "success",
        "status": status,
        "passed": passed,
        "ic_mean": ic_mean,
        "ic_std": ic_std,
        "icir": icir,
        "rank_ic_mean": rank_ic_mean,
        "rank_icir": rank_icir,
        "positive_ratio": positive_ratio,
        "daily_ic_count": daily_ic_count,
        "min_ic": min_ic,
        "min_rank_ic": min_rank_ic,
        "annualized_return": annualized_return,
        "information_ratio": information_ratio,
        "max_drawdown": max_drawdown,
        "computation_time_seconds": computation_time_seconds,
        "error_message": error_message,
        "extra_json": json.dumps(extra or {}, ensure_ascii=False, sort_keys=True),
        "created_at": datetime.now().isoformat(),
    }


def _summary_frame(rows: list[dict[str, Any]]) -> pl.DataFrame:
    """Build a summary frame with stable dtypes even when values are all null."""

    return pl.DataFrame(rows, schema=SUMMARY_SCHEMA, strict=False)


class PerformanceHistoryStore:
    """Append-only Parquet store for single-factor performance history."""

    def __init__(self, root: str | Path, compression: str = "zstd"):
        self.root = Path(root)
        self.compression = compression

    def append_summary(self, row: dict[str, Any]) -> Path:
        """Append one summary row and return the written part file."""

        missing = SUMMARY_REQUIRED_COLUMNS - set(row)
        if missing:
            raise ValueError(f"summary row missing required columns: {sorted(missing)}")

        part_path = self._partition_path("summary", row["validated_at"])
        part_path.parent.mkdir(parents=True, exist_ok=True)
        _summary_frame([row]).write_parquet(part_path, compression=self.compression)
        return part_path

    def append_series(
        self,
        *,
        factor_id: str,
        validation_id: str,
        metric_name: str,
        values: list[float],
        created_at: datetime | None = None,
        metric_dates: list[date | datetime | str | None] | None = None,
    ) -> Path | None:
        """Append a long-form metric series such as daily IC."""

        if not values:
            return None

        created_at = created_at or datetime.now()
        rows = []
        for idx, value in enumerate(values):
            metric_date = metric_dates[idx] if metric_dates and idx < len(metric_dates) else None
            rows.append(
                {
                    "schema_version": 1,
                    "validation_id": validation_id,
                    "factor_id": factor_id,
                    "metric_name": metric_name,
                    "metric_index": idx,
                    "metric_date": _as_iso(metric_date),
                    "metric_value": float(value),
                    "created_at": created_at.isoformat(),
                }
            )

        part_path = self._partition_path("series", created_at)
        part_path.parent.mkdir(parents=True, exist_ok=True)
        pl.DataFrame(rows).write_parquet(part_path, compression=self.compression)
        return part_path

    def load_factor_history(self, factor_id: str) -> pl.DataFrame:
        """Load all summary rows for one factor sorted by validation time."""

        frames = []
        for path in (self.root / "summary").glob("year=*/month=*/*.parquet"):
            frame = pl.read_parquet(path)
            if "factor_id" in frame.columns:
                selected = frame.filter(pl.col("factor_id") == factor_id)
                if selected.height:
                    frames.append(selected)
        if not frames:
            return pl.DataFrame()
        return pl.concat(frames, how="diagonal_relaxed").sort("validated_at")

    def refresh_latest_by_factor(self) -> Path:
        """Rebuild latest-by-factor snapshot from summary parts."""

        frames = [pl.read_parquet(path) for path in (self.root / "summary").glob("year=*/month=*/*.parquet")]
        output = self.root / "latest_by_factor.parquet"
        output.parent.mkdir(parents=True, exist_ok=True)
        if not frames:
            pl.DataFrame().write_parquet(output, compression=self.compression)
            return output
        latest = (
            pl.concat(frames, how="diagonal_relaxed")
            .sort(["factor_id", "validated_at"])
            .group_by("factor_id")
            .tail(1)
            .sort("factor_id")
        )
        latest.write_parquet(output, compression=self.compression)
        return output

    def _partition_path(self, table: str, value: datetime | str) -> Path:
        if isinstance(value, str):
            dt = datetime.fromisoformat(value)
        else:
            dt = value
        filename = f"part-{dt.strftime('%Y%m%d%H%M%S%f')}-{os.getpid()}.parquet"
        return self.root / table / f"year={dt.year:04d}" / f"month={dt.month:02d}" / filename
