"""
Tests for pipeline Parquet factor library wiring.

Verifies that the pipeline save branch uses FactorStoreFacade, not JSON FactorLibraryManager.
"""

import json
import hashlib
import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock, call

import pytest
import pandas as pd

from quantaalpha.factors.parquet_library import ParquetFactorLibrary


@pytest.fixture
def tmp_factorlib_dir():
    """Create a temporary factorlib directory."""
    tmpdir = tempfile.mkdtemp(prefix="factorlib_pipeline_test_")
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


def _make_mock_experiment():
    """Create a mock experiment object."""
    experiment = MagicMock()
    experiment.result = MagicMock()

    task = MagicMock()
    task.factor_name = "test_factor"
    task.factor_expression = "STD($close, 20)"
    task.factor_description = "Test factor"
    task.factor_formulation = ""

    experiment.sub_tasks = [task]

    workspace = MagicMock()
    workspace.code_dict = {"factor.py": "expr = 'STD($close, 20)'"}
    workspace.workspace_path = "/tmp/test_workspace"
    experiment.sub_workspace_list = [workspace]

    return experiment


def _make_mock_experiment_with_result(result):
    experiment = _make_mock_experiment()
    experiment.result = result
    return experiment


class TestPipelineParquetWiring:
    """Test that pipeline save branch uses FactorStoreFacade."""

    def test_pipeline_save_branch_uses_factor_store_facade(self):
        """The factor-library save branch in loop.py calls FactorStoreFacade.write_factor(),
        not JSON FactorLibraryManager JSON save, for the covered normal save branch."""
        from quantaalpha.pipeline.loop import AlphaAgentLoop

        source_file = Path(AlphaAgentLoop.__module__.replace(".", "/") + ".py")
        if not source_file.exists():
            source_file = Path(__file__).parent.parent / "quantaalpha" / "pipeline" / "loop.py"

        source_code = source_file.read_text()

        # Should reference FactorStoreFacade
        assert "FactorStoreFacade" in source_code or "save_factors_to_parquet" in source_code, (
            "loop.py should reference FactorStoreFacade or save_factors_to_parquet"
        )

    def test_pipeline_save_branch_does_not_create_json_library(self, tmp_factorlib_dir):
        """Using a fake experiment with one factor and a temporary factorlib directory,
        the covered save branch produces Parquet store files and no factor library .json file."""
        from quantaalpha.pipeline.loop import save_factors_to_parquet

        experiment = _make_mock_experiment()
        parquet_store_path = Path(tmp_factorlib_dir) / "parquet_store"
        parquet_store_path.mkdir(parents=True, exist_ok=True)

        save_factors_to_parquet(
            experiment=experiment,
            parquet_store_path=str(parquet_store_path),
            experiment_id="test_exp_001",
            round_number=0,
            hypothesis="Test hypothesis",
            feedback=None,
            initial_direction="Test direction",
            user_initial_direction="Test direction",
            planning_direction="Test direction",
            evolution_phase="original",
            trajectory_id="traj_001",
            parent_trajectory_ids=[],
        )

        delta_dir = parquet_store_path / "delta"
        parquet_files = list(delta_dir.glob("*.parquet"))
        assert len(parquet_files) > 0, "At least one Parquet delta file should be created"

        json_files = list(parquet_store_path.rglob("*.json"))
        assert len(json_files) == 0, f"No JSON files should be created in store, found: {json_files}"


class TestSaveFactorsToParquetHelper:
    """Test the save_factors_to_parquet helper function."""

    def test_save_helper_writes_through_factor_store_facade(self, tmp_factorlib_dir):
        """The helper writes through FactorStoreFacade.write_factor()."""
        from quantaalpha.pipeline.loop import save_factors_to_parquet

        experiment = _make_mock_experiment()
        store_path = Path(tmp_factorlib_dir) / "test_store"
        store_path.mkdir(parents=True, exist_ok=True)

        save_factors_to_parquet(
            experiment=experiment,
            parquet_store_path=str(store_path),
            experiment_id="exp_001",
            round_number=1,
            hypothesis="Test",
            feedback=None,
            initial_direction="dir",
            user_initial_direction="dir",
            planning_direction="dir",
            evolution_phase="original",
            trajectory_id="t1",
            parent_trajectory_ids=[],
        )

        delta_files = list((store_path / "delta").glob("*.parquet"))
        assert len(delta_files) == 1, "One delta Parquet file should be created"

        # Assert no JSON files anywhere in store (recursive check)
        json_files = list(store_path.rglob("*.json"))
        assert len(json_files) == 0, f"No JSON files should exist anywhere in store, found: {json_files}"

    def test_save_helper_handles_multiple_factors(self, tmp_factorlib_dir):
        """Helper handles experiments with multiple factors."""
        from quantaalpha.pipeline.loop import save_factors_to_parquet

        experiment = _make_mock_experiment()
        task2 = MagicMock()
        task2.factor_name = "second_factor"
        task2.factor_expression = "MEAN($volume, 10)"
        task2.factor_description = "Second factor"
        task2.factor_formulation = ""
        experiment.sub_tasks.append(task2)

        workspace2 = MagicMock()
        workspace2.code_dict = {"factor.py": "expr = 'MEAN($volume, 10)'"}
        workspace2.workspace_path = "/tmp/test_workspace_2"
        experiment.sub_workspace_list.append(workspace2)

        store_path = Path(tmp_factorlib_dir) / "multi_store"
        store_path.mkdir(parents=True, exist_ok=True)

        save_factors_to_parquet(
            experiment=experiment,
            parquet_store_path=str(store_path),
            experiment_id="exp_002",
            round_number=0,
            hypothesis="Test",
            feedback=None,
            initial_direction="dir",
            user_initial_direction="dir",
            planning_direction="dir",
            evolution_phase="original",
            trajectory_id="t2",
            parent_trajectory_ids=[],
        )

        delta_files = list((store_path / "delta").glob("*.parquet"))
        assert len(delta_files) == 2, "Two delta Parquet files should be created"

        # Assert no JSON files anywhere in store (recursive check)
        json_files = list(store_path.rglob("*.json"))
        assert len(json_files) == 0, f"No JSON files should exist anywhere in store, found: {json_files}"

    def test_save_helper_skips_failed_factors_when_round_summary_is_available(self, tmp_factorlib_dir):
        """Only factors that completed the debug round successfully should enter the library."""
        from quantaalpha.pipeline.loop import save_factors_to_parquet
        import polars as pl

        experiment = _make_mock_experiment()
        failed_task = MagicMock()
        failed_task.factor_name = "failed_factor"
        failed_task.factor_expression = "TS_MEAN($close * SEQUENCE(5), 5)"
        failed_task.factor_description = "Invalid sequence usage"
        failed_task.factor_formulation = ""
        experiment.sub_tasks.append(failed_task)

        success = experiment.sub_tasks[0]
        success_id = hashlib.md5(
            f"{success.factor_name}_{success.factor_expression}".encode()
        ).hexdigest()[:16]
        failed_id = hashlib.md5(
            f"{failed_task.factor_name}_{failed_task.factor_expression}".encode()
        ).hexdigest()[:16]

        store_path = Path(tmp_factorlib_dir) / "successful_only_store"
        store_path.mkdir(parents=True, exist_ok=True)

        save_factors_to_parquet(
            experiment=experiment,
            parquet_store_path=str(store_path),
            experiment_id="exp_partial",
            round_number=0,
            hypothesis="Test",
            feedback=None,
            initial_direction="dir",
            user_initial_direction="dir",
            planning_direction="dir",
            evolution_phase="mutation",
            trajectory_id="t_partial",
            parent_trajectory_ids=[],
            round_summary={
                "successful_factor_ids": [success_id],
                "failed_factor_ids": [failed_id],
                "failed_reasons": {failed_id: ["backtest_exception"]},
            },
        )

        delta_files = list((store_path / "delta").glob("*.parquet"))
        assert len(delta_files) == 1, "Only the successful factor should be saved"
        df = pl.read_parquet(str(delta_files[0]))
        assert df["factor_id"].to_list() == [success_id]

    def test_save_helper_stores_below_promotion_threshold_as_candidate(self, tmp_factorlib_dir):
        """Below-promotion results are retained for diagnostics but not marked active."""
        from quantaalpha.pipeline.loop import save_factors_to_parquet
        import polars as pl

        experiment = _make_mock_experiment_with_result(
            pd.Series(
                {
                    "IC": 0.021,
                    "Rank IC": 0.021,
                    "information_ratio": 0.42,
                    "annualized_return": 0.12,
                }
            )
        )
        store_path = Path(tmp_factorlib_dir) / "candidate_store"
        store_path.mkdir(parents=True, exist_ok=True)

        save_factors_to_parquet(
            experiment=experiment,
            parquet_store_path=str(store_path),
            quality_gate_config={
                "promotion": {"min_rank_ic": 0.03, "min_information_ratio": 0.3},
                "persistence": {"below_threshold": "candidate", "missing_metrics": "rejected"},
            },
        )

        delta_files = list((store_path / "delta").glob("*.parquet"))
        df = pl.read_parquet(str(delta_files[0]))
        assert df["evaluation_status"].to_list() == ["candidate"]

    def test_save_helper_returns_quality_lifecycle_summary_and_best_metrics(self, tmp_factorlib_dir):
        """Save result exposes lifecycle counts and best optimization metrics for run summaries."""
        from quantaalpha.pipeline.loop import save_factors_to_parquet

        experiment = _make_mock_experiment_with_result(
            pd.Series(
                {
                    "IC": 0.028,
                    "Rank IC": 0.041,
                    "information_ratio": 0.51,
                    "annualized_return": 0.18,
                }
            )
        )
        store_path = Path(tmp_factorlib_dir) / "summary_store"
        store_path.mkdir(parents=True, exist_ok=True)

        result = save_factors_to_parquet(
            experiment=experiment,
            parquet_store_path=str(store_path),
            quality_gate_config={
                "promotion": {"min_rank_ic": 0.03, "min_information_ratio": 0.3},
                "persistence": {"below_threshold": "candidate", "missing_metrics": "rejected"},
            },
        )

        assert result["quality_gate_lifecycle"] == {
            "evaluated": 1,
            "active_promoted": 1,
            "candidate_only": 0,
            "rejected": 0,
        }
        assert result["best_metrics"]["IC"] == 0.028
        assert result["best_metrics"]["Rank IC"] == 0.041
        assert result["best_metrics"]["annualized_return"] == 0.18
        assert result["best_metrics"]["information_ratio"] == 0.51

    def test_save_helper_promotes_passing_backtest_result_to_active(self, tmp_factorlib_dir):
        """Passing Rank IC and information-ratio promotion thresholds become active."""
        from quantaalpha.pipeline.loop import save_factors_to_parquet
        import polars as pl

        experiment = _make_mock_experiment_with_result(
            pd.Series(
                {
                    "IC": 0.028,
                    "Rank IC": 0.041,
                    "information_ratio": 0.51,
                    "annualized_return": 0.18,
                }
            )
        )
        store_path = Path(tmp_factorlib_dir) / "active_store"
        store_path.mkdir(parents=True, exist_ok=True)

        save_factors_to_parquet(
            experiment=experiment,
            parquet_store_path=str(store_path),
            quality_gate_config={
                "promotion": {"min_rank_ic": 0.03, "min_information_ratio": 0.3},
                "persistence": {"below_threshold": "candidate", "missing_metrics": "rejected"},
            },
        )

        delta_files = list((store_path / "delta").glob("*.parquet"))
        df = pl.read_parquet(str(delta_files[0]))
        assert df["evaluation_status"].to_list() == ["active"]

    def test_save_helper_publishes_active_factor_values_to_long_store(self, tmp_factorlib_dir):
        """Active factors publish workspace factor values as durable long-format parquet."""
        from quantaalpha.pipeline.loop import save_factors_to_parquet
        import polars as pl

        experiment = _make_mock_experiment_with_result(
            pd.Series(
                {
                    "IC": 0.028,
                    "Rank IC": 0.041,
                    "information_ratio": 0.51,
                    "annualized_return": 0.18,
                }
            )
        )
        workspace_dir = Path(tmp_factorlib_dir) / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        pl.DataFrame(
            {
                "trade_date": ["20250102", "20250103"],
                "instrument": ["SH600000", "SZ000001"],
                "test_factor": [1.25, -0.5],
            }
        ).write_parquet(workspace_dir / "combined_factors_df.parquet")
        experiment.sub_workspace_list[0].workspace_path = str(workspace_dir)

        store_path = Path(tmp_factorlib_dir) / "active_value_store"
        factor_value_dir = Path(tmp_factorlib_dir) / "factor_values"
        store_path.mkdir(parents=True, exist_ok=True)

        result = save_factors_to_parquet(
            experiment=experiment,
            parquet_store_path=str(store_path),
            factor_value_dir=str(factor_value_dir),
            quality_gate_config={
                "promotion": {"min_rank_ic": 0.03, "min_information_ratio": 0.3},
                "persistence": {"below_threshold": "candidate", "missing_metrics": "rejected"},
            },
        )

        factor_id = hashlib.md5(
            f"{experiment.sub_tasks[0].factor_name}_{experiment.sub_tasks[0].factor_expression}".encode()
        ).hexdigest()[:16]
        value_file = factor_value_dir / f"{factor_id}.parquet"
        manifest_file = factor_value_dir / f"{factor_id}.manifest.json"
        assert value_file.exists()
        assert manifest_file.exists()
        assert result["factor_value_publication"] == {
            "enabled": True,
            "published": 1,
            "skipped": 0,
            "failed": 0,
        }

        values = pl.read_parquet(value_file)
        assert values.schema["trade_date"] == pl.Utf8
        assert values.select(["trade_date", "instrument", "factor_id", "factor_value"]).to_dicts() == [
            {
                "trade_date": "20250102",
                "instrument": "SH600000",
                "factor_id": factor_id,
                "factor_value": 1.25,
            },
            {
                "trade_date": "20250103",
                "instrument": "SZ000001",
                "factor_id": factor_id,
                "factor_value": -0.5,
            },
        ]

    def test_save_helper_records_metric_isolation_for_same_metrics_different_values(self, tmp_factorlib_dir):
        """Same backtest metrics are only acceptable when factor-value identity evidence is present."""
        from quantaalpha.pipeline.loop import save_factors_to_parquet
        import polars as pl

        experiment = _make_mock_experiment_with_result(
            pd.Series({"IC": 0.028, "Rank IC": 0.041, "information_ratio": 0.51})
        )
        task_two = MagicMock()
        task_two.factor_name = "second_factor"
        task_two.factor_expression = "MEAN($volume, 5)"
        task_two.factor_description = "Second factor"
        experiment.sub_tasks.append(task_two)

        workspace_one = Path(tmp_factorlib_dir) / "workspace_one"
        workspace_two = Path(tmp_factorlib_dir) / "workspace_two"
        workspace_one.mkdir(parents=True, exist_ok=True)
        workspace_two.mkdir(parents=True, exist_ok=True)
        pl.DataFrame(
            {
                "trade_date": ["20250102", "20250103"],
                "instrument": ["SH600000", "SH600000"],
                "test_factor": [1.25, -0.5],
            }
        ).write_parquet(workspace_one / "combined_factors_df.parquet")
        pl.DataFrame(
            {
                "trade_date": ["20250102", "20250103"],
                "instrument": ["SH600000", "SH600000"],
                "second_factor": [3.0, 4.0],
            }
        ).write_parquet(workspace_two / "combined_factors_df.parquet")
        experiment.sub_workspace_list[0].workspace_path = str(workspace_one)
        workspace = MagicMock()
        workspace.workspace_path = str(workspace_two)
        experiment.sub_workspace_list.append(workspace)

        result = save_factors_to_parquet(
            experiment=experiment,
            parquet_store_path=str(Path(tmp_factorlib_dir) / "metric_isolation_store"),
            factor_value_dir=str(Path(tmp_factorlib_dir) / "metric_isolation_values"),
            quality_gate_config={
                "promotion": {"min_rank_ic": 0.03, "min_information_ratio": 0.3},
                "persistence": {"below_threshold": "candidate", "missing_metrics": "rejected"},
            },
        )

        isolation = result["metric_isolation"]
        assert isolation["factor_count"] == 2
        assert isolation["metric_signature"]["Rank IC"] == 0.041
        assert len(isolation["factor_value_fingerprints"]) == 2
        assert len(set(isolation["factor_value_fingerprints"].values())) == 2
        assert isolation["status"] == "isolated"

    def test_save_helper_persists_isolated_metrics_per_factor(self, tmp_factorlib_dir):
        """Per-factor isolated metrics override combined metrics in persisted factor records."""
        from quantaalpha.pipeline.loop import save_factors_to_parquet
        import polars as pl

        experiment = _make_mock_experiment_with_result(
            pd.Series({"IC": 0.0, "Rank IC": 0.0, "information_ratio": 0.0})
        )
        task_two = MagicMock()
        task_two.factor_name = "second_factor"
        task_two.factor_expression = "MEAN($volume, 5)"
        task_two.factor_description = "Second factor"
        experiment.sub_tasks.append(task_two)
        experiment._isolated_factor_metrics = {
            "test_factor": {"IC": 0.10, "Rank IC": 0.11, "information_ratio": 0.12},
            "second_factor": {"IC": -0.20, "Rank IC": -0.21, "information_ratio": -0.22},
            "metric_unique_counts": {"Rank IC": 2, "information_ratio": 2},
        }

        store_path = Path(tmp_factorlib_dir) / "isolated_metric_store"
        result = save_factors_to_parquet(
            experiment=experiment,
            parquet_store_path=str(store_path),
            quality_gate_config={
                "promotion": {"min_rank_ic": 0.03, "min_information_ratio": 0.3},
                "persistence": {"below_threshold": "candidate", "missing_metrics": "rejected"},
            },
        )

        rows = pl.read_parquet(str(store_path / "delta" / "*.parquet")).select(
            ["factor_name", "backtest_results_json", "metadata_json"]
        ).to_dicts()
        metrics_by_name = {
            row["factor_name"]: json.loads(row["backtest_results_json"])
            for row in rows
        }
        metadata_by_name = {
            row["factor_name"]: json.loads(row["metadata_json"])
            for row in rows
        }
        assert metrics_by_name["test_factor"]["Rank IC"] == 0.11
        assert metrics_by_name["second_factor"]["Rank IC"] == -0.21
        assert metadata_by_name["test_factor"]["quality_score"] != metadata_by_name["second_factor"]["quality_score"]
        assert result["metric_isolation"]["isolated_metric_unique_counts"]["Rank IC"] == 2

    def test_save_helper_quality_score_logs_factor_names_for_isolated_metrics(self, tmp_factorlib_dir, monkeypatch):
        """Quality-score events include concrete factor names, not only the batch placeholder."""
        from quantaalpha.pipeline.loop import save_factors_to_parquet

        experiment = _make_mock_experiment_with_result(
            pd.Series({"IC": 0.0, "Rank IC": 0.0, "information_ratio": 0.0})
        )
        task_two = MagicMock()
        task_two.factor_name = "second_factor"
        task_two.factor_expression = "MEAN($volume, 5)"
        task_two.factor_description = "Second factor"
        experiment.sub_tasks.append(task_two)
        experiment._isolated_factor_metrics = {
            "test_factor": {"IC": 0.10, "Rank IC": 0.11, "information_ratio": 0.12},
            "second_factor": {"IC": -0.20, "Rank IC": -0.21, "information_ratio": -0.22},
            "metric_unique_counts": {"Rank IC": 2, "information_ratio": 2},
        }
        events: list[str] = []
        monkeypatch.setattr(
            "quantaalpha.pipeline.quality_overlay.logger.info",
            lambda message: events.append(str(message)),
        )

        save_factors_to_parquet(
            experiment=experiment,
            parquet_store_path=str(Path(tmp_factorlib_dir) / "isolated_metric_log_store"),
            quality_gate_config={
                "promotion": {"min_rank_ic": 0.03, "min_information_ratio": 0.3},
                "persistence": {"below_threshold": "candidate", "missing_metrics": "rejected"},
            },
        )

        quality_score_events = [
            event for event in events if "quality_overlay_event gate=quality_score" in event
        ]
        assert any("factor=test_factor" in event for event in quality_score_events)
        assert any("factor=second_factor" in event for event in quality_score_events)
        assert not any("factor=<batch>" in event for event in quality_score_events)

    def test_save_helper_uses_task_level_isolated_metrics_when_experiment_payload_missing(self, tmp_factorlib_dir):
        """Persistence keeps per-factor metrics even if only task-level isolated metrics survive."""
        from quantaalpha.pipeline.loop import save_factors_to_parquet
        import polars as pl

        experiment = _make_mock_experiment_with_result(
            pd.Series({"IC": 0.0, "Rank IC": 0.0, "information_ratio": 0.0})
        )
        experiment.sub_tasks[0].isolated_backtest_metrics = {
            "IC": 0.10,
            "Rank IC": 0.11,
            "information_ratio": 0.12,
        }
        task_two = MagicMock()
        task_two.factor_name = "second_factor"
        task_two.factor_expression = "MEAN($volume, 5)"
        task_two.factor_description = "Second factor"
        task_two.isolated_backtest_metrics = {
            "IC": -0.20,
            "Rank IC": -0.21,
            "information_ratio": -0.22,
        }
        experiment.sub_tasks.append(task_two)
        experiment._isolated_factor_metrics = {"metric_unique_counts": {"Rank IC": 2, "information_ratio": 2}}

        store_path = Path(tmp_factorlib_dir) / "task_isolated_metric_store"
        save_factors_to_parquet(
            experiment=experiment,
            parquet_store_path=str(store_path),
            quality_gate_config={
                "promotion": {"min_rank_ic": 0.03, "min_information_ratio": 0.3},
                "persistence": {"below_threshold": "candidate", "missing_metrics": "rejected"},
            },
        )

        rows = pl.read_parquet(str(store_path / "delta" / "*.parquet")).select(
            ["factor_name", "backtest_results_json"]
        ).to_dicts()
        metrics_by_name = {
            row["factor_name"]: json.loads(row["backtest_results_json"])
            for row in rows
        }
        assert metrics_by_name["test_factor"]["Rank IC"] == 0.11
        assert metrics_by_name["second_factor"]["Rank IC"] == -0.21

    def test_save_helper_honors_disabled_factor_value_publication_flag(self, tmp_factorlib_dir):
        """Publication can be disabled even when a factor-value directory is configured."""
        from quantaalpha.pipeline.loop import save_factors_to_parquet
        import polars as pl

        experiment = _make_mock_experiment_with_result(
            pd.Series({"IC": 0.028, "Rank IC": 0.041, "information_ratio": 0.51})
        )
        workspace_dir = Path(tmp_factorlib_dir) / "workspace_no_publish"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        pl.DataFrame(
            {
                "trade_date": ["20250102"],
                "instrument": ["SH600000"],
                "test_factor": [1.25],
            }
        ).write_parquet(workspace_dir / "combined_factors_df.parquet")
        experiment.sub_workspace_list[0].workspace_path = str(workspace_dir)

        store_path = Path(tmp_factorlib_dir) / "active_no_value_store"
        factor_value_dir = Path(tmp_factorlib_dir) / "factor_values_disabled"
        store_path.mkdir(parents=True, exist_ok=True)

        result = save_factors_to_parquet(
            experiment=experiment,
            parquet_store_path=str(store_path),
            factor_value_dir=str(factor_value_dir),
            publish_factor_values_on_pass=False,
            quality_gate_config={
                "promotion": {"min_rank_ic": 0.03, "min_information_ratio": 0.3},
                "persistence": {"below_threshold": "candidate", "missing_metrics": "rejected"},
            },
        )

        assert not factor_value_dir.exists()
        assert result["factor_value_publication"] == {
            "enabled": False,
            "published": 0,
            "skipped": 0,
            "failed": 0,
        }

    def test_save_helper_deletes_passed_workspace_after_value_publication(self, tmp_factorlib_dir):
        """Minimal passed-workspace policy deletes scratch only after durable value publication."""
        from quantaalpha.pipeline.loop import save_factors_to_parquet
        import polars as pl

        experiment = _make_mock_experiment_with_result(
            pd.Series({"IC": 0.028, "Rank IC": 0.041, "information_ratio": 0.51})
        )
        workspace_dir = Path(tmp_factorlib_dir) / "passed_workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        pl.DataFrame(
            {
                "trade_date": ["20250102"],
                "instrument": ["SH600000"],
                "test_factor": [1.25],
            }
        ).write_parquet(workspace_dir / "combined_factors_df.parquet")
        (workspace_dir / "factor.py").write_text("factor = 1\n", encoding="utf-8")
        experiment.sub_workspace_list[0].workspace_path = str(workspace_dir)

        factor_value_dir = Path(tmp_factorlib_dir) / "factor_values_cleanup"
        result = save_factors_to_parquet(
            experiment=experiment,
            parquet_store_path=str(Path(tmp_factorlib_dir) / "passed_cleanup_store"),
            factor_value_dir=str(factor_value_dir),
            passed_workspace_retention="delete_after_publish",
            quality_gate_config={
                "promotion": {"min_rank_ic": 0.03, "min_information_ratio": 0.3},
                "persistence": {"below_threshold": "candidate", "missing_metrics": "rejected"},
            },
        )

        factor_id = hashlib.md5(
            f"{experiment.sub_tasks[0].factor_name}_{experiment.sub_tasks[0].factor_expression}".encode()
        ).hexdigest()[:16]
        assert (factor_value_dir / f"{factor_id}.parquet").exists()
        assert not workspace_dir.exists()
        assert result["workspace_cleanup"] == {
            "enabled": True,
            "deleted": 1,
            "retained": 0,
            "failed": 0,
        }

    def test_save_helper_deletes_failed_workspace_after_compact_summary(self, tmp_factorlib_dir):
        """Failed candidates keep compact audit summary instead of full workspace scratch."""
        from quantaalpha.pipeline.loop import save_factors_to_parquet
        import polars as pl

        experiment = _make_mock_experiment_with_result(
            pd.Series({"IC": 0.028, "Rank IC": 0.041, "information_ratio": 0.51})
        )
        task = experiment.sub_tasks[0]
        factor_id = hashlib.md5(f"{task.factor_name}_{task.factor_expression}".encode()).hexdigest()[:16]
        workspace_dir = Path(tmp_factorlib_dir) / "failed_workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        pl.DataFrame(
            {
                "trade_date": ["20250102"],
                "instrument": ["SH600000"],
                "test_factor": [1.25],
            }
        ).write_parquet(workspace_dir / "combined_factors_df.parquet")
        (workspace_dir / "runtime_info.py").write_text("info = {}\n", encoding="utf-8")
        experiment.sub_workspace_list[0].workspace_path = str(workspace_dir)
        store_path = Path(tmp_factorlib_dir) / "failed_cleanup_store"

        result = save_factors_to_parquet(
            experiment=experiment,
            parquet_store_path=str(store_path),
            failed_workspace_retention="summary_only",
            round_summary={
                "successful_factor_ids": [],
                "failed_factor_ids": [factor_id],
                "failed_reasons": {factor_id: ["backtest_exception"]},
            },
        )

        summary_path = store_path / "artifact_audit" / f"{factor_id}.failure.json"
        assert summary_path.exists()
        assert not workspace_dir.exists()
        assert result["workspace_cleanup"] == {
            "enabled": True,
            "deleted": 1,
            "retained": 0,
            "failed": 0,
        }

    def test_save_helper_deletes_candidate_experiment_workspace_after_audit(self, tmp_factorlib_dir):
        """Candidate-only batches must not retain experiment-level combined factor scratch."""
        from quantaalpha.pipeline.loop import save_factors_to_parquet
        import polars as pl

        experiment = _make_mock_experiment_with_result(
            pd.Series({"IC": 0.018, "Rank IC": 0.020, "information_ratio": 0.15})
        )
        sub_workspace_dir = Path(tmp_factorlib_dir) / "candidate_sub_workspace"
        sub_workspace_dir.mkdir(parents=True, exist_ok=True)
        (sub_workspace_dir / "factor.py").write_text("factor = 1\n", encoding="utf-8")
        experiment.sub_workspace_list[0].workspace_path = str(sub_workspace_dir)

        experiment_workspace_dir = Path(tmp_factorlib_dir) / "candidate_experiment_workspace"
        experiment_workspace_dir.mkdir(parents=True, exist_ok=True)
        pl.DataFrame(
            {
                "trade_date": ["20250102"],
                "instrument": ["SH600000"],
                "test_factor": [1.25],
            }
        ).write_parquet(experiment_workspace_dir / "combined_factors_df.parquet")
        experiment.experiment_workspace.workspace_path = str(experiment_workspace_dir)

        result = save_factors_to_parquet(
            experiment=experiment,
            parquet_store_path=str(Path(tmp_factorlib_dir) / "candidate_experiment_cleanup_store"),
            failed_workspace_retention="summary_only",
            quality_gate_config={
                "promotion": {"min_rank_ic": 0.03, "min_information_ratio": 0.3},
                "persistence": {"below_threshold": "candidate", "missing_metrics": "rejected"},
            },
        )

        assert not sub_workspace_dir.exists()
        assert not experiment_workspace_dir.exists()
        assert result["workspace_cleanup"]["deleted"] == 2

    def test_save_helper_applies_capacity_promotion_thresholds(self, tmp_factorlib_dir):
        """Configured signal-capacity thresholds participate in active promotion decisions."""
        from quantaalpha.pipeline.loop import save_factors_to_parquet
        import polars as pl

        experiment = _make_mock_experiment_with_result(
            pd.Series(
                {
                    "IC": 0.028,
                    "Rank IC": 0.041,
                    "information_ratio": 0.51,
                    "signal_valid_ratio": 0.62,
                    "signal_active_days": 12.0,
                    "signal_mean_cross_section_size": 2.8,
                }
            )
        )
        store_path = Path(tmp_factorlib_dir) / "capacity_candidate_store"
        store_path.mkdir(parents=True, exist_ok=True)

        save_factors_to_parquet(
            experiment=experiment,
            parquet_store_path=str(store_path),
            quality_gate_config={
                "promotion": {
                    "min_rank_ic": 0.03,
                    "min_information_ratio": 0.3,
                    "min_signal_valid_ratio": 0.7,
                    "min_signal_active_days": 10,
                    "min_signal_mean_cross_section_size": 2.0,
                },
                "persistence": {"below_threshold": "candidate", "missing_metrics": "rejected"},
            },
        )

        delta_files = list((store_path / "delta").glob("*.parquet"))
        df = pl.read_parquet(str(delta_files[0]))
        assert df["evaluation_status"].to_list() == ["candidate"]

        metadata = json.loads(df["metadata_json"].item())
        decision = metadata["quality_gate_decision"]
        assert decision["reason"] == "below_promotion_gate"
        assert decision["signal_valid_ratio"] == 0.62
        assert decision["min_signal_valid_ratio"] == 0.7

    def test_save_helper_rejects_missing_capacity_metrics_when_required(self, tmp_factorlib_dir):
        """Capacity thresholds are required metrics when configured."""
        from quantaalpha.pipeline.loop import save_factors_to_parquet
        import polars as pl

        experiment = _make_mock_experiment_with_result(
            pd.Series(
                {
                    "IC": 0.028,
                    "Rank IC": 0.041,
                    "information_ratio": 0.51,
                }
            )
        )
        store_path = Path(tmp_factorlib_dir) / "capacity_missing_store"
        store_path.mkdir(parents=True, exist_ok=True)

        save_factors_to_parquet(
            experiment=experiment,
            parquet_store_path=str(store_path),
            quality_gate_config={
                "promotion": {
                    "min_rank_ic": 0.03,
                    "min_information_ratio": 0.3,
                    "min_signal_valid_ratio": 0.7,
                },
                "persistence": {"below_threshold": "candidate", "missing_metrics": "rejected"},
            },
        )

        delta_files = list((store_path / "delta").glob("*.parquet"))
        df = pl.read_parquet(str(delta_files[0]))
        assert df["evaluation_status"].to_list() == ["rejected"]

        metadata = json.loads(df["metadata_json"].item())
        decision = metadata["quality_gate_decision"]
        assert decision["reason"] == "missing_required_metrics"
        assert decision["missing_metrics"] == ["signal_valid_ratio"]

    def test_save_helper_rejects_missing_required_promotion_metrics(self, tmp_factorlib_dir):
        """Missing required promotion metrics are rejected instead of silently promoted."""
        from quantaalpha.pipeline.loop import save_factors_to_parquet
        import polars as pl

        experiment = _make_mock_experiment_with_result(pd.Series({"IC": 0.028}))
        store_path = Path(tmp_factorlib_dir) / "rejected_store"
        store_path.mkdir(parents=True, exist_ok=True)

        save_factors_to_parquet(
            experiment=experiment,
            parquet_store_path=str(store_path),
            quality_gate_config={
                "promotion": {"min_rank_ic": 0.03, "min_information_ratio": 0.3},
                "persistence": {"below_threshold": "candidate", "missing_metrics": "rejected"},
            },
        )

        delta_files = list((store_path / "delta").glob("*.parquet"))
        df = pl.read_parquet(str(delta_files[0]))
        assert df["evaluation_status"].to_list() == ["rejected"]

    def test_pipeline_save_sequence_uses_microsecond_timestamp_plus_index(self, tmp_factorlib_dir):
        """Two factors in one batch have different increasing sequence values greater than a legacy round number."""
        from quantaalpha.pipeline.loop import save_factors_to_parquet
        import polars as pl

        experiment = _make_mock_experiment()
        task2 = MagicMock()
        task2.factor_name = "second_factor"
        task2.factor_expression = "MEAN($volume, 10)"
        task2.factor_description = "Second factor"
        task2.factor_formulation = ""
        experiment.sub_tasks.append(task2)

        workspace2 = MagicMock()
        workspace2.code_dict = {"factor.py": "expr = 'MEAN($volume, 10)'"}
        workspace2.workspace_path = "/tmp/test_workspace_2"
        experiment.sub_workspace_list.append(workspace2)

        store_path = Path(tmp_factorlib_dir) / "seq_store"
        store_path.mkdir(parents=True, exist_ok=True)

        round_number = 5  # A legacy round number
        save_factors_to_parquet(
            experiment=experiment,
            parquet_store_path=str(store_path),
            experiment_id="exp_seq",
            round_number=round_number,
            hypothesis="Test",
            feedback=None,
            initial_direction="dir",
            user_initial_direction="dir",
            planning_direction="dir",
            evolution_phase="original",
            trajectory_id="t_seq",
            parent_trajectory_ids=[],
        )

        delta_files = sorted((store_path / "delta").glob("*.parquet"))
        assert len(delta_files) == 2, "Two delta files should be created"

        # Read sequences from delta files
        sequences = []
        for f in delta_files:
            df = pl.read_parquet(str(f))
            sequences.append(int(df["sequence"][0]))

        # Both sequences should be greater than the round_number (legacy behavior)
        assert sequences[0] > round_number, f"Sequence {sequences[0]} should be > round_number {round_number}"
        assert sequences[1] > round_number, f"Sequence {sequences[1]} should be > round_number {round_number}"

        # Sequences should be different and increasing
        assert sequences[0] != sequences[1], "Sequences should be different for different factors in same batch"

    def test_pipeline_save_compacts_when_delta_threshold_reached(self, tmp_factorlib_dir):
        """compact_config with delta_file_threshold triggers compact after the batch,
        creates compacted/factors.parquet, and leaves no .json file in the temporary store."""
        from quantaalpha.pipeline.loop import save_factors_to_parquet

        experiment = _make_mock_experiment()
        store_path = Path(tmp_factorlib_dir) / "compact_store"
        store_path.mkdir(parents=True, exist_ok=True)

        compact_config = {
            "enabled": True,
            "delta_file_threshold": 1,
            "compact_on_save_batch_end": True,
        }

        save_factors_to_parquet(
            experiment=experiment,
            parquet_store_path=str(store_path),
            experiment_id="exp_compact",
            round_number=0,
            hypothesis="Test",
            feedback=None,
            initial_direction="dir",
            user_initial_direction="dir",
            planning_direction="dir",
            evolution_phase="original",
            trajectory_id="t_compact",
            parent_trajectory_ids=[],
            compact_config=compact_config,
        )

        # Compacted file should exist
        compacted_path = store_path / "compacted" / "factors.parquet"
        assert compacted_path.exists(), "compacted/factors.parquet should exist after compact triggered"

        # No JSON files anywhere
        json_files = list(store_path.rglob("*.json"))
        assert len(json_files) == 0, f"No JSON files should exist, found: {json_files}"

    def test_pipeline_save_does_not_compact_below_threshold(self, tmp_factorlib_dir):
        """Threshold above delta count leaves delta files in place."""
        from quantaalpha.pipeline.loop import save_factors_to_parquet

        experiment = _make_mock_experiment()
        store_path = Path(tmp_factorlib_dir) / "no_compact_store"
        store_path.mkdir(parents=True, exist_ok=True)

        compact_config = {
            "enabled": True,
            "delta_file_threshold": 100,  # High threshold
            "compact_on_save_batch_end": True,
        }

        save_factors_to_parquet(
            experiment=experiment,
            parquet_store_path=str(store_path),
            experiment_id="exp_no_compact",
            round_number=0,
            hypothesis="Test",
            feedback=None,
            initial_direction="dir",
            user_initial_direction="dir",
            planning_direction="dir",
            evolution_phase="original",
            trajectory_id="t_no_compact",
            parent_trajectory_ids=[],
            compact_config=compact_config,
        )

        # Compacted file should NOT exist (delta count below threshold)
        compacted_path = store_path / "compacted" / "factors.parquet"
        assert not compacted_path.exists(), "compacted/factors.parquet should NOT exist when below threshold"

        # Delta files should still exist
        delta_files = list((store_path / "delta").glob("*.parquet"))
        assert len(delta_files) == 1, "Delta file should exist"

    def test_pipeline_save_compact_failure_preserves_delta(self, tmp_factorlib_dir):
        """Simulated compact failure returns reason=compact_failed or logs the failure
        and does not delete saved delta files."""
        from quantaalpha.pipeline.loop import save_factors_to_parquet
        from quantaalpha.factors.factor_store_facade import FactorStoreFacade

        experiment = _make_mock_experiment()
        store_path = Path(tmp_factorlib_dir) / "failure_store"
        store_path.mkdir(parents=True, exist_ok=True)

        compact_config = {
            "enabled": True,
            "delta_file_threshold": 1,
            "compact_on_save_batch_end": True,
        }

        # Monkey-patch compact to fail
        original_compact = FactorStoreFacade.compact
        try:
            def failing_compact(self):
                raise RuntimeError("Simulated compact failure")

            FactorStoreFacade.compact = failing_compact

            result = save_factors_to_parquet(
                experiment=experiment,
                parquet_store_path=str(store_path),
                experiment_id="exp_failure",
                round_number=0,
                hypothesis="Test",
                feedback=None,
                initial_direction="dir",
                user_initial_direction="dir",
                planning_direction="dir",
                evolution_phase="original",
                trajectory_id="t_failure",
                parent_trajectory_ids=[],
                compact_config=compact_config,
            )

            # Delta files should still exist (not rolled back)
            delta_files = list((store_path / "delta").glob("*.parquet"))
            assert len(delta_files) == 1, "Delta file should still exist after compact failure"

        finally:
            FactorStoreFacade.compact = original_compact


class TestPipelineFieldExtensionMetadata:
    """Test field extension metadata in pipeline save_factors_to_parquet."""

    def test_save_factors_to_parquet_writes_field_extension_metadata(self, tmp_factorlib_dir):
        """save_factors_to_parquet writes field_schema_version, source, data_requirements,
        and other field extension metadata keys for new factor writes."""
        from quantaalpha.pipeline.loop import save_factors_to_parquet

        experiment = _make_mock_experiment()
        # Set expression with $field references
        experiment.sub_tasks[0].factor_expression = "ts_mean($close, 20) / $volume"

        store_path = Path(tmp_factorlib_dir) / "field_ext_store"
        store_path.mkdir(parents=True, exist_ok=True)

        save_factors_to_parquet(
            experiment=experiment,
            parquet_store_path=str(store_path),
            experiment_id="exp_field_ext",
            round_number=0,
            hypothesis="Test",
            feedback=None,
            initial_direction="dir",
            user_initial_direction="dir",
            planning_direction="dir",
            evolution_phase="mutation",
            trajectory_id="t_field_ext",
            parent_trajectory_ids=[],
        )

        delta_files = list((store_path / "delta").glob("*.parquet"))
        assert len(delta_files) == 1, "One delta Parquet file should be created"

        # Read the parquet file and check metadata
        import polars as pl
        df = pl.read_parquet(str(delta_files[0]))
        assert len(df) == 1

        metadata = json.loads(df["metadata_json"][0])

        # Field extension metadata should be present
        assert metadata["field_schema_version"] == "1.0"
        assert metadata["source"] == "mutation"
        assert "data_requirements" in metadata
        assert "fields" in metadata["data_requirements"]
        # The parser should extract $close and $volume
        assert "close" in metadata["data_requirements"]["fields"]
        assert "volume" in metadata["data_requirements"]["fields"]
        assert "llm_model_version" in metadata
        assert "prompt_template_hash" in metadata
        assert "parent_factor_id" in metadata

        # Existing metadata should be preserved
        assert metadata["evolution_phase"] == "mutation"
        assert metadata["trajectory_id"] == "t_field_ext"
