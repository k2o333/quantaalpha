from __future__ import annotations

import json
from pathlib import Path

import polars as pl
from quantaalpha.continuous.app5_data_adapter import App5DataAutomationAdapter
from quantaalpha.factor_ops.workflows.app5_inputs import App5ManifestReader, App5SchemaFreshnessAuditor
from quantaalpha.factor_ops.workflows.daily import DailyWorkflowRunner
from quantaalpha.factor_ops.workflows.data_inputs import FactorOpsRunInputResolver
from quantaalpha.factor_ops.workflows.evaluate import EvaluateWorkflowRunner
from quantaalpha.factor_ops.workflows.gate import GateWorkflowRunner
from quantaalpha.factor_ops.workflows.io import (
    load_factor_values,
    load_registry_frame,
    load_returns,
    write_json_report,
    write_markdown_report,
)
from quantaalpha.factor_ops.workflows.lifecycle import ApplyStatusWorkflowRunner
from quantaalpha.factor_ops.workflows.mining import PostMiningWorkflowRunner
from quantaalpha.factor_ops.workflows.report import MonthlyReportWorkflowRunner
from quantaalpha.factor_ops.workflows.status import StatusWorkflowRunner


def _library(path: Path, factors: dict) -> Path:
    path.write_text(
        json.dumps({"metadata": {"version": "test"}, "factors": factors}, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def _factor_values(path: Path, factor_id: str = "factor_001") -> Path:
    pl.DataFrame(
        {
            "date": ["2026-05-01", "2026-05-01", "2026-05-02", "2026-05-02"],
            "stock_id": ["A", "B", "A", "B"],
            factor_id: [1.0, 2.0, 1.1, 2.2],
        }
    ).write_parquet(path)
    return path


def _returns(path: Path) -> Path:
    pl.DataFrame(
        {
            "date": ["2026-05-01", "2026-05-01", "2026-05-02", "2026-05-02"],
            "stock_id": ["A", "B", "A", "B"],
            "return_t_plus_1": [0.01, 0.02, 0.011, 0.021],
        }
    ).write_parquet(path)
    return path


def test_factor_ops_workflow_io_uses_polars_and_honors_no_write(tmp_path) -> None:
    library_path = _library(
        tmp_path / "library.json",
        {"factor_001": {"factor_id": "factor_001", "metadata": {"ops": {"status": "core", "tier": "A"}}}},
    )
    factor_values = _factor_values(tmp_path / "factor_values.parquet")
    returns = _returns(tmp_path / "returns.parquet")

    registry = load_registry_frame(library_path)
    values = load_factor_values(factor_values)
    loaded_returns = load_returns(returns)
    json_result = write_json_report({"success": True}, tmp_path / "report.json", no_write=True)
    md_result = write_markdown_report({"success": True}, tmp_path / "report.md", dry_run=True)

    assert isinstance(registry, pl.DataFrame)
    assert values.columns == ["date", "stock_id", "factor_001"]
    assert loaded_returns.columns == ["date", "stock_id", "return_t_plus_1"]
    assert json_result["written"] is False
    assert md_result["written"] is False
    assert not (tmp_path / "report.json").exists()
    assert not (tmp_path / "report.md").exists()


def test_status_gate_evaluate_apply_and_post_mining_workflows(tmp_path) -> None:
    library_path = _library(
        tmp_path / "library.json",
        {
            "factor_001": {
                "factor_id": "factor_001",
                "factor_name": "factor_001",
                "factor_expression": "close / open",
                "metadata": {"ops": {"status": "testing", "tier": "", "version": 0}},
            },
            "factor_002": {
                "factor_id": "factor_002",
                "factor_name": "factor_002",
                "factor_expression": "volume",
                "metadata": {"ops": {"status": "core", "tier": "A", "version": 0}},
            },
        },
    )
    factor_values = _factor_values(tmp_path / "factor_001.parquet")
    returns = _returns(tmp_path / "returns.parquet")
    storage_root = tmp_path / "ops"

    status = StatusWorkflowRunner().run(library_path=library_path)
    gate = GateWorkflowRunner(storage_root=storage_root).run("factor_001", factor_values=factor_values)
    evaluation = EvaluateWorkflowRunner().run(
        "factor_001",
        factor_values=factor_values,
        returns=returns,
        registry_path=library_path,
        no_write=True,
    )
    dry_apply = ApplyStatusWorkflowRunner(storage_root=storage_root).run(
        "factor_001",
        library_path=library_path,
        to_status="candidate",
        tier="C",
        health_score=50.0,
        expected_version=0,
        reason="dry",
        dry_run=True,
    )
    applied = ApplyStatusWorkflowRunner(storage_root=storage_root).run(
        "factor_001",
        library_path=library_path,
        to_status="candidate",
        tier="C",
        health_score=50.0,
        expected_version=0,
        reason="apply",
    )
    post = PostMiningWorkflowRunner(storage_root=storage_root).run(
        library_path=library_path,
        factor_values=factor_values,
        returns=returns,
        factor_ids=["factor_001"],
        dry_run=True,
    )

    assert status["status_counts"]["testing"] == 1
    assert gate["gate_result"] == "pass"
    assert gate["written"] is True
    assert evaluation["tier"] in {"A", "B", "C", "D"}
    assert evaluation["suggested_status"]
    assert dry_apply["written"] is False
    assert applied["written"] is True
    assert post["accepted_count"] == 1
    assert post["applied_count"] == 0


def test_factor_ops_data_input_resolver(tmp_path) -> None:
    data_root = tmp_path / "app5"
    active = data_root / "daily" / "clean" / "active.parquet"
    active.parent.mkdir(parents=True)
    pl.DataFrame(
        {"ts_code": ["000001.SZ"], "trade_date": ["20260505"], "close": [10.0], "open": [9.9]}
    ).write_parquet(active)
    manifest_dir = data_root / "daily" / "manifest"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "current.json").write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "interface_name": "daily",
                "run_id": "run_1",
                "created_at": "2026-05-05T16:00:00",
                "schema_hash": "hash_daily",
                "active_files": ["clean/active.parquet"],
                "coverage_summary": {"latest_date": "2026-05-05"},
            }
        ),
        encoding="utf-8",
    )
    factor_values = _factor_values(tmp_path / "factor_001.parquet")
    returns = _returns(tmp_path / "returns.parquet")
    library_path = _library(
        tmp_path / "library.json",
        {"factor_001": {"factor_id": "factor_001", "metadata": {"ops": {"status": "testing"}}}},
    )

    reader = App5ManifestReader(data_root)
    manifest = reader.read("daily")
    audit = App5SchemaFreshnessAuditor(data_root).audit_interface("daily", required_columns=["ts_code", "trade_date"])
    adapter = App5DataAutomationAdapter({"enabled": True, "data_root": str(data_root), "groups": ["daily"]})
    summary = adapter.inspect(skip_update=True)
    resolved = FactorOpsRunInputResolver(data_root=data_root).resolve(
        library_path=library_path,
        factor_values=factor_values,
        returns=returns,
        run_date="2026-05-05",
        skip_update=True,
    )

    assert manifest["schema_hash"] == "hash_daily"
    assert audit["schema_pass"] is True
    assert summary["source"] == "app5"
    assert summary["skipped"] is True
    assert resolved["success"] is True
    assert resolved["data_update"]["source"] == "app5"
    assert resolved["factor_inputs"]["candidate_count"] == 1
    assert resolved["factor_inputs"]["missing_returns"] is False


def test_daily_and_monthly_report_workflows(tmp_path) -> None:
    library_path = _library(
        tmp_path / "library.json",
        {
            "factor_001": {
                "factor_id": "factor_001",
                "metadata": {"ops": {"status": "candidate", "tier": "C", "health_score": 55}},
            }
        },
    )
    values = _factor_values(tmp_path / "factor_001.parquet")
    returns = _returns(tmp_path / "returns.parquet")
    storage_root = tmp_path / "ops"

    daily = DailyWorkflowRunner(storage_root=storage_root).run(
        library_path=library_path,
        factor_values=values,
        returns=returns,
        data_update={"updated": True, "updated_interfaces": ["daily"]},
        run_date="2026-05-05",
        dry_run=True,
    )
    report = MonthlyReportWorkflowRunner(storage_root=storage_root).run(
        library_path=library_path,
        month="2026-05",
        output=tmp_path / "report.md",
        format="markdown",
    )

    assert daily["success"] is True
    assert daily["trigger"]["triggered"] is True
    assert daily["post_mining"]["success"] is True
    assert report["success"] is True
    assert report["written"] is True
    assert "mining_prompt_feedback" in report
    assert (tmp_path / "report.md").exists()
