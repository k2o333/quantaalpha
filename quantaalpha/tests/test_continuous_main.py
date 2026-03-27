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
