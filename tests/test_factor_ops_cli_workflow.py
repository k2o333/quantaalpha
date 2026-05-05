from __future__ import annotations

import json

import polars as pl
from quantaalpha.cli import app
from quantaalpha.factor_ops.gate.log_writer import GateLogReader
from quantaalpha.factor_ops.lifecycle.log_writer import LifecycleLogReader


def _library(path, factors: dict) -> str:
    path.write_text(
        json.dumps({"metadata": {"version": "test"}, "factors": factors}, ensure_ascii=False),
        encoding="utf-8",
    )
    return str(path)


def _factor_values(path, factor_id: str = "factor_001") -> str:
    pl.DataFrame(
        {
            "date": ["2026-05-01", "2026-05-01", "2026-05-02", "2026-05-02"],
            "stock_id": ["A", "B", "A", "B"],
            factor_id: [1.0, 2.0, 1.1, 2.2],
        }
    ).write_parquet(path)
    return str(path)


def _returns(path) -> str:
    pl.DataFrame(
        {
            "date": ["2026-05-01", "2026-05-01", "2026-05-02", "2026-05-02"],
            "stock_id": ["A", "B", "A", "B"],
            "return_t_plus_1": [0.01, 0.02, 0.011, 0.021],
        }
    ).write_parquet(path)
    return str(path)


def test_factor_ops_command_group_is_registered(tmp_path) -> None:
    library_path = _library(
        tmp_path / "library.json",
        {
            "factor_001": {
                "factor_id": "factor_001",
                "metadata": {"ops": {"status": "candidate", "tier": "C"}},
            }
        },
    )

    result = app(["factor-ops", "status", "--library-path", library_path])

    assert result["success"] is True
    assert result["total_factors"] == 1
    assert result["status_counts"] == {"candidate": 1}


def test_factor_ops_cli_minimal_automation_loop(tmp_path) -> None:
    library_path = _library(
        tmp_path / "library.json",
        {
            "factor_001": {
                "factor_id": "factor_001",
                "factor_name": "factor_001",
                "factor_expression": "close / open",
                "metadata": {"ops": {"status": "testing", "tier": "", "version": 0}},
            }
        },
    )
    factor_values = _factor_values(tmp_path / "factor_001.parquet")
    returns = _returns(tmp_path / "returns.parquet")
    storage_root = str(tmp_path / "ops")

    post = app(
        [
            "factor-ops",
            "post-mining",
            "--library-path",
            library_path,
            "--factor-values",
            factor_values,
            "--returns",
            returns,
            "--storage-root",
            storage_root,
            "--dry-run",
        ]
    )
    gate = app(
        [
            "factor-ops",
            "gate",
            "factor_001",
            "--factor-values",
            factor_values,
            "--storage-root",
            storage_root,
        ]
    )
    evaluation = app(
        [
            "factor-ops",
            "evaluate",
            "factor_001",
            "--factor-values",
            factor_values,
            "--returns",
            returns,
            "--library-path",
            library_path,
            "--no-write",
        ]
    )
    applied = app(
        [
            "factor-ops",
            "apply-status",
            "factor_001",
            "--library-path",
            library_path,
            "--storage-root",
            storage_root,
            "--to",
            "candidate",
            "--tier",
            "C",
            "--health-score",
            "55",
            "--expected-version",
            "0",
            "--reason",
            "cli smoke",
        ]
    )

    assert post["success"] is True
    assert post["accepted_count"] == 1
    assert gate["gate_result"] == "pass"
    assert evaluation["success"] is True
    assert evaluation["suggested_status"]
    assert applied["success"] is True
    assert LifecycleLogReader(storage_root).query("factor_001").height == 1
    assert GateLogReader(storage_root).query("factor_001").height >= 1


def test_factor_ops_acceptance_command_returns_closed_loop(tmp_path) -> None:
    result = app(["factor-ops", "acceptance", "--storage-root", str(tmp_path)])

    assert result["success"] is True
    assert result["gate_result"] == "pass"
    assert result["registry_update_success"] is True
    assert result["consumer_payload"]["factor_ids"] == ["factor_001"]
