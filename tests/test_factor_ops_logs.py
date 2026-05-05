from __future__ import annotations

import json
import re

import polars as pl
from quantaalpha.factor_ops.gate.log_writer import GateLogReader, GateLogRecord, GateLogWriter
from quantaalpha.factor_ops.lifecycle.log_writer import (
    LifecycleLogReader,
    LifecycleLogRecord,
    LifecycleLogWriter,
)


def test_gate_log_writer_persists_partitioned_parquet_and_returns_run_id(tmp_path) -> None:
    """Gate 日志写入 year/month 分区并返回稳定格式 run_id。"""
    writer = GateLogWriter(tmp_path)

    gate_run_id = writer.write(
        GateLogRecord(
            factor_id="factor_001",
            gate_name="data_quality",
            gate_result="watchlist",
            check_details=[
                {
                    "check_name": "missing_rate",
                    "value": 0.42,
                    "threshold": 0.40,
                    "passed": False,
                    "details": {"nan_count": 42},
                }
            ],
            reason="missing rate too high",
            created_at="2026-05-05T10:00:00",
            operator="auto_gate",
        )
    )

    assert re.fullmatch(r"gate_20260505_\d{3}", gate_run_id)
    parquet_files = list((tmp_path / "gate_log" / "year=2026" / "month=05").glob("*.parquet"))
    assert len(parquet_files) == 1

    df = pl.read_parquet(parquet_files[0])
    assert df["factor_id"].item() == "factor_001"
    assert df["gate_run_id"].item() == gate_run_id
    assert json.loads(df["check_details"].item())[0]["check_name"] == "missing_rate"


def test_gate_log_reader_queries_by_factor_gate_and_date_range(tmp_path) -> None:
    """Gate 日志读取接口支持 factor、gate_name 和日期过滤。"""
    writer = GateLogWriter(tmp_path)
    writer.write(
        GateLogRecord(
            factor_id="factor_001",
            gate_name="data_quality",
            gate_result="pass",
            check_details=[],
            reason="ok",
            created_at="2026-05-05T10:00:00",
        )
    )
    writer.write(
        GateLogRecord(
            factor_id="factor_002",
            gate_name="redundancy",
            gate_result="reject",
            check_details=[],
            reason="too similar",
            created_at="2026-05-06T10:00:00",
        )
    )

    result = GateLogReader(tmp_path).query(
        factor_id="factor_001",
        gate_name="data_quality",
        start="2026-05-01",
        end="2026-05-31",
    )

    assert result.height == 1
    assert result["gate_result"].item() == "pass"


def test_lifecycle_log_writer_persists_status_transition_with_gate_link(tmp_path) -> None:
    """Lifecycle 日志写入状态变更结果，并保留 gate_run_id 关联。"""
    writer = LifecycleLogWriter(tmp_path)

    log_id = writer.write(
        LifecycleLogRecord(
            factor_id="factor_001",
            old_status="testing",
            new_status="candidate",
            old_tier="",
            new_tier="C",
            reason="gate passed",
            metrics_snapshot={"health_score": 62.0, "gate_result": "pass"},
            gate_run_id="gate_20260505_001",
            operator="auto_gate",
            timestamp="2026-05-05T10:05:00",
            created_at="2026-05-05T10:05:01",
        )
    )

    assert re.fullmatch(r"lifecycle_20260505_[0-9a-f]{8}", log_id)
    parquet_files = list((tmp_path / "lifecycle_log" / "year=2026" / "month=05").glob("*.parquet"))
    assert len(parquet_files) == 1

    df = pl.read_parquet(parquet_files[0])
    assert df["old_status"].item() == "testing"
    assert df["new_status"].item() == "candidate"
    assert df["gate_run_id"].item() == "gate_20260505_001"
    assert json.loads(df["metrics_snapshot"].item())["health_score"] == 62.0


def test_lifecycle_log_reader_queries_factor_history(tmp_path) -> None:
    """Lifecycle 日志读取接口返回按 timestamp 排序的因子历史。"""
    writer = LifecycleLogWriter(tmp_path)
    writer.write(
        LifecycleLogRecord(
            factor_id="factor_001",
            old_status="draft",
            new_status="testing",
            reason="calculated",
            timestamp="2026-05-05T09:00:00",
            created_at="2026-05-05T09:00:01",
        )
    )
    writer.write(
        LifecycleLogRecord(
            factor_id="factor_001",
            old_status="testing",
            new_status="candidate",
            reason="gate passed",
            timestamp="2026-05-05T10:00:00",
            created_at="2026-05-05T10:00:01",
        )
    )

    result = LifecycleLogReader(tmp_path).query(
        factor_id="factor_001",
        start="2026-05-01",
        end="2026-05-31",
    )

    assert result["old_status"].to_list() == ["draft", "testing"]
    assert result["new_status"].to_list() == ["testing", "candidate"]
