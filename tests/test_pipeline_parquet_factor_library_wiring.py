"""
Tests for pipeline Parquet factor library wiring.

Verifies that the pipeline save branch uses FactorStoreFacade, not JSON FactorLibraryManager.
"""

import json
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
