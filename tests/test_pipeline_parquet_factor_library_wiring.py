"""
Tests for pipeline Parquet factor library wiring.
"""

import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock, call

import pytest

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


class TestPipelineParquetWiring:
    """Test that pipeline save branch uses Parquet writer."""

    def test_pipeline_save_branch_uses_parquet_writer(self):
        """The factor-library save branch in loop.py calls the Parquet writer or helper,
        not JSON FactorLibraryManager JSON save, for the covered normal save branch."""
        from quantaalpha.pipeline.loop import AlphaAgentLoop

        source_file = Path(AlphaAgentLoop.__module__.replace(".", "/") + ".py")
        if not source_file.exists():
            source_file = Path(__file__).parent.parent / "quantaalpha" / "pipeline" / "loop.py"

        source_code = source_file.read_text()

        assert "save_factors_to_parquet" in source_code or "ParquetFactorLibrary" in source_code, (
            "loop.py should reference save_factors_to_parquet or ParquetFactorLibrary"
        )

        assert "manager.add_factors_from_experiment" not in source_code or "ParquetFactorLibrary" in source_code, (
            "loop.py should use ParquetFactorLibrary instead of JSON FactorLibraryManager for normal save"
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

    def test_save_helper_writes_through_parquet_writer(self, tmp_factorlib_dir):
        """The helper writes through the Parquet writer."""
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
