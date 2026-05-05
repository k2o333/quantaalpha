"""Lifecycle Log 的 Parquet 写入与读取。"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import polars as pl

from quantaalpha.factor_ops.storage import file_lock, parse_iso_datetime, read_table, write_single_row_parquet


@dataclass(frozen=True)
class LifecycleLogRecord:
    """状态变更结果日志记录。"""

    factor_id: str
    old_status: str
    new_status: str
    reason: str
    timestamp: str
    created_at: str
    old_tier: str = ""
    new_tier: str = ""
    metrics_snapshot: dict[str, Any] = field(default_factory=dict)
    gate_run_id: str = ""
    operator: str = "auto_gate"


class LifecycleLogWriter:
    """写入状态变更结果日志。"""

    def __init__(self, storage_root: str | Path):
        """初始化 writer。"""
        self.storage_root = Path(storage_root)
        self.lock_path = self.storage_root / "locks" / "lifecycle_log.lock"

    def write(self, record: LifecycleLogRecord) -> str:
        """写入一条状态变更日志并返回 log id。"""
        log_id = self._log_id(record.timestamp)
        with file_lock(self.lock_path):
            df = pl.DataFrame(
                {
                    "log_id": [log_id],
                    "timestamp": [record.timestamp],
                    "factor_id": [record.factor_id],
                    "old_status": [record.old_status],
                    "new_status": [record.new_status],
                    "old_tier": [record.old_tier],
                    "new_tier": [record.new_tier],
                    "reason": [record.reason],
                    "metrics_snapshot": [json.dumps(record.metrics_snapshot, ensure_ascii=False, sort_keys=True)],
                    "gate_run_id": [record.gate_run_id],
                    "operator": [record.operator],
                    "created_at": [record.created_at],
                },
                schema=self.schema(),
            )
            write_single_row_parquet(self.storage_root, "lifecycle_log", record.timestamp, df)
        return log_id

    @staticmethod
    def _log_id(timestamp: str) -> str:
        return f"lifecycle_{parse_iso_datetime(timestamp).strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}"

    @staticmethod
    def schema() -> dict[str, pl.DataType]:
        """返回 Lifecycle Log schema。"""
        return {
            "log_id": pl.String,
            "timestamp": pl.String,
            "factor_id": pl.String,
            "old_status": pl.String,
            "new_status": pl.String,
            "old_tier": pl.String,
            "new_tier": pl.String,
            "reason": pl.String,
            "metrics_snapshot": pl.String,
            "gate_run_id": pl.String,
            "operator": pl.String,
            "created_at": pl.String,
        }


class LifecycleLogReader:
    """读取状态变更结果日志。"""

    def __init__(self, storage_root: str | Path):
        """初始化 reader。"""
        self.storage_root = Path(storage_root)

    def query(
        self,
        factor_id: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> pl.DataFrame:
        """查询 Lifecycle 日志。"""
        table = read_table(self.storage_root, "lifecycle_log")
        if table.is_empty():
            return pl.DataFrame(schema=LifecycleLogWriter.schema())
        if factor_id is not None:
            table = table.filter(pl.col("factor_id") == factor_id)
        table = _filter_timestamp(table, start=start, end=end)
        return table.sort("timestamp")


def _filter_timestamp(table: pl.DataFrame, start: str | None, end: str | None) -> pl.DataFrame:
    if start is not None:
        table = table.filter(pl.col("timestamp") >= start)
    if end is not None:
        table = table.filter(pl.col("timestamp") <= f"{end}T23:59:59" if "T" not in end else pl.lit(end))
    return table
