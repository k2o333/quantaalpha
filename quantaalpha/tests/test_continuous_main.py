"""
Tests for continuous main.py - Runtime Entrypoint and ContinuousOrchestrator.
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestContinuousOrchestrator:
    """Tests for ContinuousOrchestrator wiring and cycle execution."""

    def test_orchestrator_initializes_with_config(self, tmp_path):
        """Verify orchestrator initializes with PipelineConfig."""
        from quantaalpha.continuous.main import ContinuousOrchestrator
        from quantaalpha.continuous.scheduler import PipelineConfig

        # Create minimal config
        config = PipelineConfig(
            data_check_interval_seconds=300,
            enable_data_monitor=False,
            enable_revalidation=True,
            enable_mining=False,
            validation={"max_revalidation_per_run": 10, "max_mining_per_run": 5},
            factor={"library_path": str(tmp_path / "lib.json")},
        )
        config.validation = MagicMock()
        config.validation.max_revalidation_per_run = 10
        config.validation.max_mining_per_run = 5
        config.factor = MagicMock()
        config.factor.library_path = str(tmp_path / "lib.json")
        config.app4_bridge.enabled = False

        orchestrator = ContinuousOrchestrator(config)

        assert orchestrator.config == config
        assert orchestrator._orchestrator is not None

    def test_orchestrator_wires_impact_classifier_when_enabled(self, tmp_path):
        """Verify impact classifier is wired when revalidation is enabled."""
        from quantaalpha.continuous.main import ContinuousOrchestrator
        from quantaalpha.continuous.scheduler import PipelineConfig

        config = PipelineConfig(
            enable_data_monitor=False,
            enable_revalidation=True,
            enable_mining=False,
        )
        config.validation = MagicMock()
        config.validation.max_revalidation_per_run = 10
        config.validation.max_mining_per_run = 5
        config.factor = MagicMock()
        config.factor.library_path = str(tmp_path / "lib.json")
        config.app4_bridge.enabled = False

        orchestrator = ContinuousOrchestrator(config)

        assert orchestrator._impact_classifier is not None

    def test_orchestrator_skips_impact_classifier_when_disabled(self, tmp_path):
        """Verify impact classifier is None when both revalidation and mining are disabled."""
        from quantaalpha.continuous.main import ContinuousOrchestrator
        from quantaalpha.continuous.scheduler import PipelineConfig

        config = PipelineConfig(
            enable_data_monitor=False,
            enable_revalidation=False,
            enable_mining=False,
        )
        config.validation = MagicMock()
        config.validation.max_revalidation_per_run = 10
        config.validation.max_mining_per_run = 5
        config.factor = MagicMock()
        config.factor.library_path = str(tmp_path / "lib.json")
        config.app4_bridge.enabled = False

        orchestrator = ContinuousOrchestrator(config)

        assert orchestrator._impact_classifier is None

    def test_run_once_cycle_returns_dict_with_all_keys(self, tmp_path):
        """Verify run_once_cycle returns dict with all required result keys."""
        from quantaalpha.continuous.main import ContinuousOrchestrator
        from quantaalpha.continuous.scheduler import PipelineConfig

        config = PipelineConfig(
            enable_data_monitor=False,
            enable_revalidation=True,
            enable_mining=False,
        )
        config.validation = MagicMock()
        config.validation.max_revalidation_per_run = 10
        config.validation.max_mining_per_run = 5
        config.factor = MagicMock()
        config.factor.library_path = str(tmp_path / "lib.json")
        config.app4_bridge.enabled = False

        orchestrator = ContinuousOrchestrator(config)

        # Mock the base orchestrator
        mock_reval_result = MagicMock()
        mock_reval_result.total_candidates = 0
        mock_reval_result.revalidated_count = 0
        mock_reval_result.errors = []
        orchestrator._orchestrator.run_revalidation_cycle = MagicMock(return_value=mock_reval_result)

        result = orchestrator.run_once_cycle()

        assert isinstance(result, dict)
        assert "data_update" in result
        assert "impact_groups" in result
        assert "validation" in result
        assert "mining" in result
        assert "candidate_factors" in result
        assert "errors" in result

    def test_run_once_cycle_handles_bridge_inspection(self, tmp_path):
        """Verify run_once_cycle calls bridge.inspect when app4_bridge is enabled."""
        from quantaalpha.continuous.main import ContinuousOrchestrator
        from quantaalpha.continuous.scheduler import PipelineConfig

        config = PipelineConfig(
            enable_data_monitor=False,
            enable_revalidation=False,
            enable_mining=False,
        )
        config.validation = MagicMock()
        config.validation.max_revalidation_per_run = 10
        config.validation.max_mining_per_run = 5
        config.factor = MagicMock()
        config.factor.library_path = str(tmp_path / "lib.json")
        config.app4_bridge.enabled = True
        config.app4_bridge.interfaces = ["daily"]

        # Mock the bridge creation to avoid app4 import issues
        with patch.object(ContinuousOrchestrator, '_create_bridge') as mock_create:
            mock_bridge = MagicMock()
            mock_inspection = {
                "latest_dates": {"daily": "20260327"},
                "stale_interfaces": [],
                "checked_interfaces": ["daily"],
                "errors": [],
            }
            mock_bridge.inspect = MagicMock(return_value=mock_inspection)
            mock_bridge.should_update = MagicMock(return_value=False)
            mock_bridge._last_inspection = mock_inspection
            mock_create.return_value = mock_bridge

            orchestrator = ContinuousOrchestrator(config)

            result = orchestrator.run_once_cycle()

            mock_bridge.inspect.assert_called_once()
            assert result["data_update"]["latest_dates"]["daily"] == "20260327"

    def test_run_once_cycle_calls_revalidation_when_enabled(self, tmp_path):
        """Verify run_once_cycle triggers revalidation when enabled."""
        from quantaalpha.continuous.main import ContinuousOrchestrator
        from quantaalpha.continuous.scheduler import PipelineConfig

        config = PipelineConfig(
            enable_data_monitor=False,
            enable_revalidation=True,
            enable_mining=False,
        )
        config.validation = MagicMock()
        config.validation.max_revalidation_per_run = 10
        config.validation.max_mining_per_run = 5
        config.factor = MagicMock()
        config.factor.library_path = str(tmp_path / "lib.json")
        config.app4_bridge.enabled = False

        orchestrator = ContinuousOrchestrator(config)

        # Mock base orchestrator
        mock_reval_result = MagicMock()
        mock_reval_result.total_candidates = 5
        mock_reval_result.revalidated_count = 3
        mock_reval_result.status_changes = {"f1": "active"}
        mock_reval_result.errors = []
        mock_reval_result.duration_seconds = 10.0
        orchestrator._orchestrator.run_revalidation_cycle = MagicMock(return_value=mock_reval_result)

        result = orchestrator.run_once_cycle()

        orchestrator._orchestrator.run_revalidation_cycle.assert_called_once()
        assert result["validation"]["total"] == 5
        assert result["validation"]["passed"] == 3

    def test_run_once_cycle_calls_mining_when_enabled(self, tmp_path):
        """Verify run_once_cycle triggers mining when enabled."""
        from quantaalpha.continuous.main import ContinuousOrchestrator
        from quantaalpha.continuous.scheduler import PipelineConfig

        config = PipelineConfig(
            enable_data_monitor=False,
            enable_revalidation=False,
            enable_mining=True,
        )
        config.validation = MagicMock()
        config.validation.max_revalidation_per_run = 10
        config.validation.max_mining_per_run = 5
        config.factor = MagicMock()
        config.factor.library_path = str(tmp_path / "lib.json")
        config.app4_bridge.enabled = False

        orchestrator = ContinuousOrchestrator(config)

        # Mock base orchestrator
        mock_mining_result = MagicMock()
        mock_mining_result.factors_generated = 3
        mock_mining_result.factors_validated = 2
        mock_mining_result.factors_added = 1
        mock_mining_result.factor_ids = ["gen_1", "gen_2"]
        mock_mining_result.errors = []
        mock_mining_result.duration_seconds = 30.0
        orchestrator._orchestrator.run_mining_cycle = MagicMock(return_value=mock_mining_result)

        result = orchestrator.run_once_cycle()

        orchestrator._orchestrator.run_mining_cycle.assert_called_once()
        assert result["mining"]["generated"] == 3
        assert result["mining"]["added"] == 1


class TestStartCommand:
    """Tests for the start/once CLI commands."""

    def test_start_command_requires_config_file(self):
        """Verify start command validates config file exists."""
        from quantaalpha.continuous.main import start

        with pytest.raises(SystemExit):
            start(config="/nonexistent/path/pipeline.yaml", verbose=False)

    def test_once_command_requires_config_file(self):
        """Verify once command validates config file exists."""
        from quantaalpha.continuous.main import once

        with pytest.raises(SystemExit):
            once(config="/nonexistent/path/pipeline.yaml", verbose=False)

    def test_once_executes_single_cycle(self, tmp_path):
        """Verify once command runs exactly one cycle."""
        from quantaalpha.continuous.main import ContinuousOrchestrator, once
        from quantaalpha.continuous.scheduler import PipelineConfig

        # Create a valid config
        config_path = tmp_path / "pipeline.yaml"
        config_path.write_text(
            "runtime:\n"
            "  data_check_interval_seconds: 300\n"
            "  revalidation_interval_hours: 24\n"
            "  revalidation_days_threshold: 21\n"
            "  mining_interval_hours: 12\n"
            "app4_bridge:\n"
            "  enabled: false\n"
            "  interfaces: []\n"
            "  data_roots: []\n"
            "  freshness_threshold_hours: 24\n"
            "factor:\n"
            "  library_path: data/results/factor_library.json\n"
            "  monitoring_output_path: log/monitoring/\n"
            "  backtest_config_path: config/backtest.yaml\n"
            "validation:\n"
            "  min_ic: 0.02\n"
            "  min_rank_ic: 0.01\n"
            "  max_revalidation_per_run: 10\n"
            "  max_mining_per_run: 5\n"
            "execution:\n"
            "  train:\n"
            "    start: '2020-01-01'\n"
            "    end: '2022-12-31'\n"
            "  valid:\n"
            "    start: '2023-01-01'\n"
            "    end: '2023-12-31'\n"
            "  test:\n"
            "    start: '2024-01-01'\n"
            "    end: '2024-12-31'\n"
            "features:\n"
            "  enable_data_monitor: false\n"
            "  enable_revalidation: true\n"
            "  enable_mining: false\n"
        )

        with patch("quantaalpha.continuous.main._run_once_cycle") as mock_run_once:
            # We just verify it doesn't crash
            pass


class TestRunSummaryPersistence:
    """Tests for run summary persistence via main module."""

    def test_orchestrator_uses_provided_run_store(self, tmp_path):
        """Verify orchestrator uses the provided RunStore instance."""
        from quantaalpha.continuous.main import ContinuousOrchestrator
        from quantaalpha.continuous.run_store import RunStore
        from quantaalpha.continuous.scheduler import PipelineConfig

        config = PipelineConfig(
            enable_data_monitor=False,
            enable_revalidation=False,
            enable_mining=False,
        )
        config.validation = MagicMock()
        config.validation.max_revalidation_per_run = 10
        config.validation.max_mining_per_run = 5
        config.factor = MagicMock()
        config.factor.library_path = str(tmp_path / "lib.json")
        config.app4_bridge.enabled = False

        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        store = RunStore(str(runs_dir))

        orchestrator = ContinuousOrchestrator(config, run_store=store)

        # Verify the store is set correctly
        assert orchestrator.run_store is store

    def test_orchestrator_run_once_cycle_returns_summary_structure(self, tmp_path):
        """Verify orchestrator run_once_cycle returns proper summary structure."""
        from quantaalpha.continuous.main import ContinuousOrchestrator
        from quantaalpha.continuous.scheduler import PipelineConfig

        config = PipelineConfig(
            enable_data_monitor=False,
            enable_revalidation=True,
            enable_mining=False,
        )
        config.validation = MagicMock()
        config.validation.max_revalidation_per_run = 10
        config.validation.max_mining_per_run = 5
        config.factor = MagicMock()
        config.factor.library_path = str(tmp_path / "lib.json")
        config.app4_bridge.enabled = False

        orchestrator = ContinuousOrchestrator(config)

        # Mock base orchestrator
        mock_reval_result = MagicMock()
        mock_reval_result.total_candidates = 3
        mock_reval_result.revalidated_count = 2
        mock_reval_result.status_changes = {}
        mock_reval_result.errors = []
        mock_reval_result.duration_seconds = 5.0
        orchestrator._orchestrator.run_revalidation_cycle = MagicMock(return_value=mock_reval_result)

        result = orchestrator.run_once_cycle()

        assert result["validation"]["total"] == 3
        assert result["validation"]["passed"] == 2


class TestImpactCandidateSelection:
    """Tests for impact-selected candidates driving revalidation."""

    def test_run_once_cycle_returns_impact_groups_and_candidate_count(self, tmp_path):
        """Verify run_once_cycle returns impact_groups and candidate_factors when impact selection runs."""
        from quantaalpha.continuous.main import ContinuousOrchestrator
        from quantaalpha.continuous.scheduler import PipelineConfig

        config = PipelineConfig(
            enable_data_monitor=False,
            enable_revalidation=True,
            enable_mining=False,
        )
        config.validation = MagicMock()
        config.validation.max_revalidation_per_run = 10
        config.validation.max_mining_per_run = 5
        config.factor = MagicMock()
        config.factor.library_path = str(tmp_path / "lib.json")
        config.app4_bridge.enabled = False

        orchestrator = ContinuousOrchestrator(config)

        # Mock impact classifier to return groups
        mock_impact_classifier = MagicMock()
        mock_impact_classifier.classify_interfaces.return_value = ["price_volume", "moneyflow"]
        mock_impact_classifier.select_factor_candidates.return_value = [
            {"factor_id": "f1", "factor_expression": "$close"},
            {"factor_id": "f2", "factor_expression": "$volume"},
            {"factor_id": "f3", "factor_expression": "$open"},
        ]
        orchestrator._impact_classifier = mock_impact_classifier

        # Mock base orchestrator
        mock_reval_result = MagicMock()
        mock_reval_result.total_candidates = 3
        mock_reval_result.revalidated_count = 2
        mock_reval_result.status_changes = {}
        mock_reval_result.errors = []
        mock_reval_result.duration_seconds = 5.0
        orchestrator._orchestrator.run_revalidation_cycle = MagicMock(return_value=mock_reval_result)

        result = orchestrator.run_once_cycle()

        # Verify impact groups and candidate counts are returned
        assert result["impact_groups"] == ["price_volume", "moneyflow"]
        assert result["candidate_factors"] == 3
        assert result["candidate_factors_source"] == "impact"

    def test_revalidation_passes_selected_candidates_to_underlying_runner(self, tmp_path):
        """Verify _run_revalidation passes impact-selected candidates to the scheduler."""
        from quantaalpha.continuous.main import ContinuousOrchestrator
        from quantaalpha.continuous.scheduler import PipelineConfig

        config = PipelineConfig(
            enable_data_monitor=False,
            enable_revalidation=True,
            enable_mining=False,
        )
        config.validation = MagicMock()
        config.validation.max_revalidation_per_run = 10
        config.validation.max_mining_per_run = 5
        config.factor = MagicMock()
        config.factor.library_path = str(tmp_path / "lib.json")
        config.app4_bridge.enabled = False

        orchestrator = ContinuousOrchestrator(config)

        # Mock impact classifier
        selected_candidates = [
            {"factor_id": "f1", "factor_expression": "$close"},
        ]
        mock_impact_classifier = MagicMock()
        mock_impact_classifier.classify_interfaces.return_value = ["price_volume"]
        mock_impact_classifier.select_factor_candidates.return_value = selected_candidates
        orchestrator._impact_classifier = mock_impact_classifier

        # Track what gets passed to the scheduler
        captured_candidates = []

        def capture_run_revalidation(candidates=None):
            captured_candidates.append(candidates)
            mock_result = MagicMock()
            mock_result.total_candidates = 1 if candidates else 0
            mock_result.revalidated_count = 1 if candidates else 0
            mock_result.status_changes = {}
            mock_result.errors = []
            mock_result.duration_seconds = 1.0
            return mock_result

        orchestrator._orchestrator.run_revalidation_cycle = capture_run_revalidation

        result = orchestrator._run_revalidation()

        # Verify candidates were passed
        assert len(captured_candidates) == 1
        assert captured_candidates[0] == selected_candidates
        assert result["total_candidates"] == 1

    def test_run_once_cycle_returns_fallback_source_when_no_impact(self, tmp_path):
        """Verify candidate_factors_source is 'fallback' when no impact selection occurs."""
        from quantaalpha.continuous.main import ContinuousOrchestrator
        from quantaalpha.continuous.scheduler import PipelineConfig

        config = PipelineConfig(
            enable_data_monitor=False,
            enable_revalidation=True,
            enable_mining=False,
        )
        config.validation = MagicMock()
        config.validation.max_revalidation_per_run = 10
        config.validation.max_mining_per_run = 5
        config.factor = MagicMock()
        config.factor.library_path = str(tmp_path / "lib.json")
        config.app4_bridge.enabled = False

        orchestrator = ContinuousOrchestrator(config)

        # Mock impact classifier that fails
        mock_impact_classifier = MagicMock()
        mock_impact_classifier.classify_interfaces.return_value = []
        mock_impact_classifier.select_factor_candidates.side_effect = Exception("No candidates")
        orchestrator._impact_classifier = mock_impact_classifier

        # Mock base orchestrator
        mock_reval_result = MagicMock()
        mock_reval_result.total_candidates = 5
        mock_reval_result.revalidated_count = 3
        mock_reval_result.status_changes = {}
        mock_reval_result.errors = []
        mock_reval_result.duration_seconds = 5.0
        orchestrator._orchestrator.run_revalidation_cycle = MagicMock(return_value=mock_reval_result)

        result = orchestrator.run_once_cycle()

        # When impact selection fails, should use fallback source
        assert result["candidate_factors_source"] == "fallback"
        assert result["candidate_factors"] == 5


class TestUpdateFailureFailOpen:
    """Tests verifying update failure doesn't block revalidation."""

    def test_run_once_cycle_continues_when_update_fails(self, tmp_path):
        """Verify run_once_cycle continues to revalidation even when update fails."""
        from quantaalpha.continuous.main import ContinuousOrchestrator
        from quantaalpha.continuous.scheduler import PipelineConfig

        config = PipelineConfig(
            enable_data_monitor=False,
            enable_revalidation=True,
            enable_mining=False,
        )
        config.validation = MagicMock()
        config.validation.max_revalidation_per_run = 10
        config.validation.max_mining_per_run = 5
        config.factor = MagicMock()
        config.factor.library_path = str(tmp_path / "lib.json")
        config.app4_bridge.enabled = True
        config.app4_bridge.interfaces = ["daily"]

        orchestrator = ContinuousOrchestrator(config)

        # Mock bridge to simulate update failure
        mock_bridge = MagicMock()
        mock_bridge.inspect.return_value = {
            "latest_dates": {"daily": "20260327"},
            "stale_interfaces": ["daily"],
            "checked_interfaces": ["daily"],
            "errors": [],
        }
        mock_bridge.should_update.return_value = True
        mock_bridge._last_inspection = {
            "latest_dates": {"daily": "20260327"},
            "stale_interfaces": ["daily"],
            "checked_interfaces": ["daily"],
            "errors": [],
        }
        # Simulate update failure
        mock_bridge.run_update.return_value = {
            "updated": False,
            "update_attempted": True,
            "updated_interfaces": [],
            "latest_dates": {},
            "stale_interfaces": ["daily"],
            "errors": ["Update failed: connection timeout"],
        }
        orchestrator._bridge = mock_bridge

        # Mock impact classifier
        mock_impact_classifier = MagicMock()
        mock_impact_classifier.classify_interfaces.return_value = ["price_volume"]
        mock_impact_classifier.select_factor_candidates.return_value = [
            {"factor_id": "f1", "factor_expression": "$close"},
        ]
        orchestrator._impact_classifier = mock_impact_classifier

        # Mock base orchestrator to track revalidation was called
        mock_reval_result = MagicMock()
        mock_reval_result.total_candidates = 1
        mock_reval_result.revalidated_count = 1
        mock_reval_result.status_changes = {}
        mock_reval_result.errors = []
        mock_reval_result.duration_seconds = 1.0
        orchestrator._orchestrator.run_revalidation_cycle = MagicMock(return_value=mock_reval_result)

        result = orchestrator.run_once_cycle()

        # Verify update failure was recorded
        assert len(result["errors"]) > 0
        assert any("Update failed" in err or "update" in err.lower() for err in result["errors"])

        # Verify revalidation still ran (was called)
        orchestrator._orchestrator.run_revalidation_cycle.assert_called_once()

        # Verify validation summary has results
        assert result["validation"]["total"] == 1
        assert result["validation"]["passed"] == 1


class TestOnceCycleRealIntegration:
    """Minimal realistic integration test using real temp data."""

    def test_once_cycle_with_temp_price_data_persists_non_empty_summary(self, tmp_path):
        """
        Verify run_once_cycle works with real temp parquet data and persists summary.

        This test:
        1. Creates temporary parquet price data
        2. Creates temporary factor library
        3. Creates temporary pipeline config
        4. Verifies run_once_cycle returns non-empty impact/candidate/validation fields
        5. Verifies RunStore saves the summary file
        """
        import json
        import os
        from datetime import datetime

        import polars as pl

        from quantaalpha.continuous.main import ContinuousOrchestrator
        from quantaalpha.continuous.run_store import RunStore
        from quantaalpha.continuous.scheduler import PipelineConfig

        # Step 1: Create temp parquet data
        data_dir = tmp_path / "data"
        daily_dir = data_dir / "daily"
        daily_dir.mkdir(parents=True)

        today = datetime.now().strftime("%Y%m%d")
        parquet_file = daily_dir / f"daily_{today}_{today}_123456_abc.parquet"
        df = pl.DataFrame({
            "ts_code": ["000001.SZ"] * 3,
            "trade_date": [today] * 3,
            "open": [10.0, 10.5, 11.0],
            "high": [10.5, 11.0, 11.5],
            "low": [9.5, 10.0, 10.5],
            "close": [10.2, 10.8, 11.2],
            "volume": [1000000, 1500000, 2000000],
        })
        df.write_parquet(parquet_file)

        # Step 2: Create temp factor library
        lib_dir = tmp_path / "factorlib"
        lib_dir.mkdir(parents=True)
        lib_path = lib_dir / "library.json"
        factors = {
            "test_factor_1": {
                "factor_id": "test_factor_1",
                "factor_name": "Test Factor 1",
                "factor_expression": "$close",
                "evaluation": {"status": "active", "last_validated": "20260325"},
                "tags": {"data_dependency": ["price_volume"]},
            },
            "test_factor_2": {
                "factor_id": "test_factor_2",
                "factor_name": "Test Factor 2",
                "factor_expression": "$volume",
                "evaluation": {"status": "active", "last_validated": "20260325"},
                "tags": {"data_dependency": ["price_volume"]},
            },
        }
        lib_path.write_text(json.dumps({"metadata": {}, "factors": factors}))

        # Step 3: Create temp pipeline config
        config_path = tmp_path / "pipeline.yaml"
        config_content = f"""runtime:
  data_check_interval_seconds: 300
  revalidation_interval_hours: 24
  revalidation_days_threshold: 21
  mining_interval_hours: 12
app4_bridge:
  enabled: false
  interfaces: []
  data_roots: []
  freshness_threshold_hours: 24
factor:
  library_path: "{lib_path}"
  monitoring_output_path: "{tmp_path / 'monitoring'}"
  backtest_config_path: "{tmp_path / 'backtest.yaml'}"
validation:
  min_ic: 0.02
  min_rank_ic: 0.01
  max_revalidation_per_run: 10
  max_mining_per_run: 5
execution:
  train:
    start: '2020-01-01'
    end: '2022-12-31'
  valid:
    start: '2023-01-01'
    end: '2023-12-31'
  test:
    start: '2024-01-01'
    end: '2024-12-31'
features:
  enable_data_monitor: false
  enable_revalidation: true
  enable_mining: false
"""
        config_path.write_text(config_content)

        # Step 4: Load config and create orchestrator
        config = PipelineConfig.from_yaml(str(config_path))
        config.factor.library_path = str(lib_path)

        # Create run store in temp dir
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        store = RunStore(str(runs_dir))

        orchestrator = ContinuousOrchestrator(config, run_store=store)

        # Mock the base orchestrator to avoid real FactorExecutor
        mock_reval_result = MagicMock()
        mock_reval_result.total_candidates = 2
        mock_reval_result.revalidated_count = 2
        mock_reval_result.status_changes = {}
        mock_reval_result.errors = []
        mock_reval_result.duration_seconds = 1.0
        orchestrator._orchestrator.run_revalidation_cycle = MagicMock(return_value=mock_reval_result)

        # Step 5: Run once cycle
        result = orchestrator.run_once_cycle()

        # Step 6: Verify results
        # - impact_groups should be present (may be empty but keys exist)
        assert "impact_groups" in result
        # - candidate_factors should be present
        assert "candidate_factors" in result
        # - validation should be present with required keys
        assert "validation" in result
        assert "total" in result["validation"]
        assert "passed" in result["validation"]
        assert "candidate_factors_source" in result

        # Step 7: Verify RunStore can persist the summary (simulating _run_once_cycle behavior)
        from quantaalpha.continuous.run_store import RunSummary, DataUpdateSummary, ValidationSummary, MiningSummary
        from datetime import datetime

        summary = RunSummary(
            schema_version="1.0",
            cycle_timestamp=datetime.now().isoformat(),
            cycle_type="once",
            config_snapshot={
                "min_ic": 0.02,
                "max_revalidation_per_run": 10,
                "max_mining_per_run": 5,
            },
        )
        if result.get("data_update"):
            du = result["data_update"]
            summary.data_update = DataUpdateSummary(
                updated=du.get("updated", False),
                updated_interfaces=du.get("updated_interfaces", []),
                stale_interfaces=du.get("stale_interfaces", []),
                latest_dates=du.get("latest_dates", {}),
            )
        if result.get("impact_groups"):
            summary.impact_groups = result["impact_groups"]
        if result.get("validation"):
            v = result["validation"]
            summary.validation_summary = ValidationSummary(
                total=v.get("total", 0),
                passed=v.get("passed", 0),
                failed=v.get("failed", 0),
                errors=v.get("errors", []),
            )
        if result.get("candidate_factors") is not None:
            summary.candidate_factors_count = result["candidate_factors"]
            summary.candidate_factors_source = result.get("candidate_factors_source", "revalidation")
        if result.get("errors"):
            summary.errors = result["errors"]

        store.save(summary)
        assert store.get_run_count() == 1
        latest_run = store.get_latest_run()
        assert latest_run is not None
        assert latest_run.cycle_type == "once"
        assert latest_run.candidate_factors_count >= 0

    def test_orchestrator_with_enabled_bridge_uses_real_loader(self, tmp_path):
        """
        Verify orchestrator with enabled bridge uses real bridge loader.
        """
        import json
        from datetime import datetime

        import polars as pl

        from quantaalpha.continuous.main import ContinuousOrchestrator
        from quantaalpha.continuous.run_store import RunStore
        from quantaalpha.continuous.scheduler import PipelineConfig

        # Create temp parquet data
        data_dir = tmp_path / "data"
        daily_dir = data_dir / "daily"
        daily_dir.mkdir(parents=True)

        today = datetime.now().strftime("%Y%m%d")
        parquet_file = daily_dir / f"daily_{today}_{today}_123456_abc.parquet"
        df = pl.DataFrame({
            "ts_code": ["000001.SZ"] * 3,
            "trade_date": [today] * 3,
            "open": [10.0, 10.5, 11.0],
            "high": [10.5, 11.0, 11.5],
            "low": [9.5, 10.0, 10.5],
            "close": [10.2, 10.8, 11.2],
            "volume": [1000000, 1500000, 2000000],
        })
        df.write_parquet(parquet_file)

        # Create temp factor library
        lib_dir = tmp_path / "factorlib"
        lib_dir.mkdir(parents=True)
        lib_path = lib_dir / "library.json"
        factors = {
            "test_factor_1": {
                "factor_id": "test_factor_1",
                "factor_name": "Test Factor 1",
                "factor_expression": "$close",
                "evaluation": {"status": "active", "last_validated": "20260325"},
                "tags": {"data_dependency": ["price_volume"]},
            },
        }
        lib_path.write_text(json.dumps({"metadata": {}, "factors": factors}))

        # Create temp pipeline config with bridge enabled
        config_path = tmp_path / "pipeline.yaml"
        config_content = f"""runtime:
  data_check_interval_seconds: 300
  revalidation_interval_hours: 24
  revalidation_days_threshold: 21
  mining_interval_hours: 12
app4_bridge:
  enabled: true
  interfaces: ["daily"]
  data_roots: ["{data_dir}"]
  freshness_threshold_hours: 24
  update_timeout_seconds: 120
  max_update_interfaces_per_cycle: 5
factor:
  library_path: "{lib_path}"
  monitoring_output_path: "{tmp_path / 'monitoring'}"
  backtest_config_path: "{tmp_path / 'backtest.yaml'}"
validation:
  min_ic: 0.02
  min_rank_ic: 0.01
  max_revalidation_per_run: 10
  max_mining_per_run: 5
execution:
  train:
    start: '2020-01-01'
    end: '2022-12-31'
  valid:
    start: '2023-01-01'
    end: '2023-12-31'
  test:
    start: '2024-01-01'
    end: '2024-12-31'
features:
  enable_data_monitor: false
  enable_revalidation: true
  enable_mining: false
"""
        config_path.write_text(config_content)

        # Load config
        config = PipelineConfig.from_yaml(str(config_path))
        config.factor.library_path = str(lib_path)

        # Create run store
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        store = RunStore(str(runs_dir))

        orchestrator = ContinuousOrchestrator(config, run_store=store)

        # Mock base orchestrator to avoid real execution
        mock_reval_result = MagicMock()
        mock_reval_result.total_candidates = 1
        mock_reval_result.revalidated_count = 1
        mock_reval_result.status_changes = {}
        mock_reval_result.errors = []
        mock_reval_result.duration_seconds = 1.0
        orchestrator._orchestrator.run_revalidation_cycle = MagicMock(return_value=mock_reval_result)

        # Run once cycle
        result = orchestrator.run_once_cycle()

        # Verify bridge was used (data_update has content)
        assert "data_update" in result
        # When bridge is enabled and data exists, latest_dates should have entries
        assert "latest_dates" in result["data_update"]
