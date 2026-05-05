"""Gate Log 的 Parquet 写入与读取。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

from quantaalpha.factor_ops.storage import file_lock, parse_iso_datetime, read_table, write_single_row_parquet


@dataclass(frozen=True)
class GateLogRecord:
    """Gate 检查过程日志记录。"""

    factor_id: str
    gate_name: str
    gate_result: str
    check_details: list[dict[str, Any]]
    reason: str
    created_at: str
    operator: str = "auto_gate"
    gate_run_id: str | None = None


class GateLogWriter:
    """写入 Gate 检查过程日志。"""

    def __init__(self, storage_root: str | Path):
        """初始化 writer。"""
        self.storage_root = Path(storage_root)
        self.lock_path = self.storage_root / "locks" / "gate_log.lock"

    def write(self, record: GateLogRecord) -> str:
        """写入一条 Gate 日志并返回 `gate_run_id`。"""
        with file_lock(self.lock_path):
            gate_run_id = record.gate_run_id or self._next_gate_run_id(record.created_at)
            df = pl.DataFrame(
                {
                    "factor_id": [record.factor_id],
                    "gate_run_id": [gate_run_id],
                    "gate_name": [record.gate_name],
                    "gate_result": [record.gate_result],
                    "check_details": [json.dumps(record.check_details, ensure_ascii=False, sort_keys=True)],
                    "reason": [record.reason],
                    "created_at": [record.created_at],
                    "operator": [record.operator],
                },
                schema=self.schema(),
            )
            write_single_row_parquet(self.storage_root, "gate_log", record.created_at, df)
        return gate_run_id

    def _next_gate_run_id(self, created_at: str) -> str:
        date_key = parse_iso_datetime(created_at).strftime("%Y%m%d")
        table = read_table(self.storage_root, "gate_log")
        if table.is_empty():
            sequence = 1
        else:
            prefix = f"gate_{date_key}_"
            sequence = (
                table.filter(pl.col("gate_run_id").str.starts_with(prefix)).select(pl.len()).item()
                + 1
            )
        return f"gate_{date_key}_{sequence:03d}"

    @staticmethod
    def schema() -> dict[str, pl.DataType]:
        """返回 Gate Log schema。"""
        return {
            "factor_id": pl.String,
            "gate_run_id": pl.String,
            "gate_name": pl.String,
            "gate_result": pl.String,
            "check_details": pl.String,
            "reason": pl.String,
            "created_at": pl.String,
            "operator": pl.String,
        }


class GateLogReader:
    """读取 Gate 检查过程日志。"""

    def __init__(self, storage_root: str | Path):
        """初始化 reader。"""
        self.storage_root = Path(storage_root)

    def query(
        self,
        factor_id: str | None = None,
        gate_name: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> pl.DataFrame:
        """查询 Gate 日志。"""
        table = read_table(self.storage_root, "gate_log")
        if table.is_empty():
            return pl.DataFrame(schema=GateLogWriter.schema())
        if factor_id is not None:
            table = table.filter(pl.col("factor_id") == factor_id)
        if gate_name is not None:
            table = table.filter(pl.col("gate_name") == gate_name)
        table = _filter_created_at(table, start=start, end=end)
        return table.sort("created_at")


def _filter_created_at(table: pl.DataFrame, start: str | None, end: str | None) -> pl.DataFrame:
    if start is not None:
        table = table.filter(pl.col("created_at") >= start)
    if end is not None:
        table = table.filter(pl.col("created_at") <= f"{end}T23:59:59" if "T" not in end else pl.lit(end))
    return table
