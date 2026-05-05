"""Factor monitor 输出到 factor_ops 的稳定适配层。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import polars as pl

from quantaalpha.factor_ops.lifecycle.log_writer import LifecycleLogRecord, LifecycleLogWriter


class FactorMonitorInputAdapter:
    """标准化 monitor daily IC 输出，供 HealthScorer 与降解检测复用。"""

    def export_daily_ic(
        self,
        data: pl.DataFrame,
        *,
        factor_column: str = "factor_id",
        date_column: str = "date",
        ic_column: str = "ic",
        rank_ic_column: str = "rank_ic",
    ) -> pl.DataFrame:
        """将 monitor 原始输出标准化为 daily IC 契约。"""
        missing = [
            column
            for column in (factor_column, date_column, ic_column, rank_ic_column)
            if column not in data.columns
        ]
        if missing:
            raise ValueError(f"daily IC input missing columns: {missing}")

        expressions = [
            pl.col(date_column).cast(pl.String).alias("date"),
            pl.col(factor_column).cast(pl.String).alias("factor_id"),
            pl.col(ic_column).cast(pl.Float64).alias("ic"),
            pl.col(rank_ic_column).cast(pl.Float64).alias("rank_ic"),
        ]
        optional_columns = [
            column
            for column in ("coverage", "sample_count", "universe")
            if column in data.columns and column not in (date_column, factor_column, ic_column, rank_ic_column)
        ]
        expressions.extend(pl.col(column) for column in optional_columns)
        return data.select(expressions).sort(["date", "factor_id"])

    def read_daily_ic(
        self,
        path: str | Path,
        *,
        factor_id: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> pl.DataFrame:
        """从 Parquet 读取标准 daily IC，并支持 factor/date 过滤。"""
        table = self.export_daily_ic(pl.read_parquet(path))
        if factor_id is not None:
            table = table.filter(pl.col("factor_id") == factor_id)
        if start is not None:
            table = table.filter(pl.col("date") >= start)
        if end is not None:
            table = table.filter(pl.col("date") <= end)
        return table.sort(["date", "factor_id"])


class DegradationLifecycleBridge:
    """将降解建议写入 Lifecycle Log，形成可审计边界。"""

    def __init__(self, storage_root: str | Path, writer: LifecycleLogWriter | None = None) -> None:
        """初始化桥接器。"""
        self.writer = writer or LifecycleLogWriter(storage_root)

    def write_suggestions(
        self,
        suggestions: Iterable[Any],
        *,
        timestamp: str | None = None,
        created_at: str | None = None,
    ) -> list[str]:
        """写入建议状态变更，返回 lifecycle log ids。"""
        event_time = timestamp or datetime.utcnow().replace(microsecond=0).isoformat()
        create_time = created_at or event_time
        log_ids: list[str] = []
        for suggestion in suggestions:
            new_status = getattr(suggestion, "recommended_status", "")
            if new_status not in {"watch", "degraded"}:
                continue

            log_ids.append(
                self.writer.write(
                    LifecycleLogRecord(
                        factor_id=getattr(suggestion, "factor_id"),
                        old_status=getattr(suggestion, "current_status", ""),
                        new_status=new_status,
                        reason=getattr(suggestion, "reason", ""),
                        timestamp=event_time,
                        created_at=create_time,
                        metrics_snapshot=self._metrics_snapshot(suggestion),
                        operator="degradation_detector",
                    )
                )
            )
        return log_ids

    @staticmethod
    def _metrics_snapshot(suggestion: Any) -> dict[str, Any]:
        return {
            "consecutive_low_count": getattr(suggestion, "consecutive_low_count", 0),
            "factor_name": getattr(suggestion, "factor_name", ""),
            "rolling_ic_mean": getattr(suggestion, "rolling_ic_mean", None),
            "trend_slope": getattr(suggestion, "trend_slope", None),
        }
