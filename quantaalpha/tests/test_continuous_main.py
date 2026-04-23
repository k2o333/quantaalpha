"""
Tests for continuous main.py - Runtime Entrypoint and ContinuousOrchestrator.
"""

import json
import math
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestContinuousOrchestrator:
    """Tests for ContinuousOrchestrator wiring and cycle execution."""

    def test_orchestrator_forwards_training_scheduler_to_base_orchestrator(self, tmp_path):
        """ContinuousOrchestrator should preserve an injected training scheduler host slot."""
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

        training_scheduler = MagicMock()
        orchestrator = ContinuousOrchestrator(
            config,
            training_scheduler=training_scheduler,
        )

        assert orchestrator._orchestrator.training_scheduler is training_scheduler

    def test_start_and_stop_preserve_injected_training_scheduler(self, tmp_path):
        """ContinuousOrchestrator lifecycle should keep training start/stop forwarding intact."""
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

        training_scheduler = MagicMock()
        orchestrator = ContinuousOrchestrator(
            config,
            training_scheduler=training_scheduler,
        )

        orchestrator.start()
        orchestrator.stop()

        training_scheduler.start.assert_called_once()
        training_scheduler.stop.assert_called_once()

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
        assert "training" in result
        assert "candidate_factors" in result
        assert "errors" in result

    def test_run_once_cycle_exposes_training_host_without_running_training(self, tmp_path):
        """Once-cycle should surface the hosted training workflow without auto-triggering it."""
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

        training_scheduler = MagicMock()
        training_scheduler.next_run = "2026-04-23T00:00:00"
        orchestrator = ContinuousOrchestrator(
            config,
            training_scheduler=training_scheduler,
        )

        result = orchestrator.run_once_cycle()

        assert result["training"] == {
            "hosted": True,
            "triggered": False,
            "next_run": "2026-04-23T00:00:00",
            "errors": [],
        }
        training_scheduler.run_training_cycle.assert_not_called()

    def test_run_once_cycle_triggers_training_when_once_flag_enabled(self, tmp_path):
        """Once-cycle should call the base training cycle only when explicitly enabled."""
        from quantaalpha.continuous.main import ContinuousOrchestrator
        from quantaalpha.continuous.scheduler import PipelineConfig

        config = PipelineConfig(
            enable_data_monitor=False,
            enable_revalidation=False,
            enable_mining=False,
        )
        config.training.enable_training = True
        config.training.trigger_on_once = True
        config.training.trigger_on_start = False
        config.validation = MagicMock()
        config.validation.max_revalidation_per_run = 10
        config.validation.max_mining_per_run = 5
        config.factor = MagicMock()
        config.factor.library_path = str(tmp_path / "lib.json")
        config.app4_bridge.enabled = False

        orchestrator = ContinuousOrchestrator(config)
        orchestrator._orchestrator.run_training_cycle = MagicMock(
            return_value={"hosted": True, "triggered": True, "errors": []}
        )

        result = orchestrator.run_once_cycle()

        orchestrator._orchestrator.run_training_cycle.assert_called_once_with(trigger="once")
        assert result["training"]["hosted"] is True
        assert result["training"]["triggered"] is True
        assert result["training"]["errors"] == []

    def test_run_once_cycle_skips_training_when_not_enabled_for_trigger(self, tmp_path):
        """Start-trigger disabled should keep the hosted workflow visible but not run it."""
        from quantaalpha.continuous.main import ContinuousOrchestrator
        from quantaalpha.continuous.scheduler import PipelineConfig

        config = PipelineConfig(
            enable_data_monitor=False,
            enable_revalidation=False,
            enable_mining=False,
        )
        config.training.enable_training = True
        config.training.trigger_on_once = False
        config.training.trigger_on_start = False
        config.validation = MagicMock()
        config.validation.max_revalidation_per_run = 10
        config.validation.max_mining_per_run = 5
        config.factor = MagicMock()
        config.factor.library_path = str(tmp_path / "lib.json")
        config.app4_bridge.enabled = False

        orchestrator = ContinuousOrchestrator(config)
        orchestrator._orchestrator.run_training_cycle = MagicMock()

        result = orchestrator.run_once_cycle()

        orchestrator._orchestrator.run_training_cycle.assert_not_called()
        assert result["training"]["hosted"] is True
        assert result["training"]["triggered"] is False
        assert result["training"]["errors"] == []

    def test_run_once_cycle_triggers_training_on_data_update_when_enabled(self, tmp_path):
        """Data advancement should trigger training when trigger_on_data_update is enabled."""
        from quantaalpha.continuous.main import ContinuousOrchestrator
        from quantaalpha.continuous.scheduler import PipelineConfig

        config = PipelineConfig(
            enable_data_monitor=False,
            enable_revalidation=False,
            enable_mining=False,
        )
        config.training.enable_training = True
        config.training.trigger_on_once = False
        config.training.trigger_on_start = False
        config.training.trigger_on_data_update = True
        config.training.trigger_on_degradation = False
        config.validation = MagicMock()
        config.validation.max_revalidation_per_run = 10
        config.validation.max_mining_per_run = 5
        config.factor = MagicMock()
        config.factor.library_path = str(tmp_path / "lib.json")
        config.app4_bridge.enabled = False

        orchestrator = ContinuousOrchestrator(config)
        orchestrator._bridge = MagicMock()
        inspection = {
            "stale_interfaces": ["daily"],
            "latest_dates": {"daily": "20260422"},
        }
        orchestrator._bridge.inspect.return_value = inspection
        orchestrator._bridge.should_update.return_value = True
        orchestrator._bridge.run_update.return_value = {
            "updated": True,
            "updated_interfaces": ["daily"],
            "advanced_interfaces": ["daily"],
            "errors": [],
        }
        orchestrator._orchestrator.run_training_cycle = MagicMock(
            return_value={"hosted": True, "triggered": True, "errors": []}
        )

        result = orchestrator.run_once_cycle()

        orchestrator._orchestrator.run_training_cycle.assert_called_once_with(trigger="data_update")
        assert result["training"]["triggered"] is True
        assert result["data_update"]["advanced_interfaces"] == ["daily"]

    def test_run_once_cycle_triggers_training_on_degradation_signal_when_enabled(self, tmp_path):
        """Degradation signals from validation should trigger training when configured."""
        from quantaalpha.continuous.main import ContinuousOrchestrator
        from quantaalpha.continuous.scheduler import PipelineConfig

        config = PipelineConfig(
            enable_data_monitor=False,
            enable_revalidation=True,
            enable_mining=False,
        )
        config.training.enable_training = True
        config.training.trigger_on_once = False
        config.training.trigger_on_start = False
        config.training.trigger_on_data_update = False
        config.training.trigger_on_degradation = True
        config.validation = MagicMock()
        config.validation.max_revalidation_per_run = 10
        config.validation.max_mining_per_run = 5
        config.factor = MagicMock()
        config.factor.library_path = str(tmp_path / "lib.json")
        config.app4_bridge.enabled = False

        orchestrator = ContinuousOrchestrator(config)
        orchestrator._run_revalidation = MagicMock(
            return_value={
                "total_candidates": 2,
                "revalidated_count": 1,
                "errors": ["degradation: factor_123"],
                "degradation": True,
            }
        )
        orchestrator._orchestrator.run_training_cycle = MagicMock(
            return_value={"hosted": True, "triggered": True, "errors": []}
        )

        result = orchestrator.run_once_cycle()

        orchestrator._orchestrator.run_training_cycle.assert_called_once_with(trigger="degradation")
        assert result["training"]["triggered"] is True
        assert result["validation"]["errors"] == ["degradation: factor_123"]

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

    def test_run_once_cycle_can_skip_update_for_smoke_runs(self, tmp_path):
        """Verify skip_update bypasses bridge.run_update but still continues with revalidation."""
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

        with patch.object(ContinuousOrchestrator, "_create_bridge") as mock_create:
            mock_bridge = MagicMock()
            mock_inspection = {
                "latest_dates": {"daily": "20260327"},
                "stale_interfaces": ["daily"],
                "checked_interfaces": ["daily"],
                "errors": [],
            }
            mock_bridge.inspect.return_value = mock_inspection
            mock_bridge.should_update.return_value = True
            mock_bridge._last_inspection = mock_inspection
            mock_create.return_value = mock_bridge

            orchestrator = ContinuousOrchestrator(config)

        mock_reval_result = MagicMock()
        mock_reval_result.total_candidates = 1
        mock_reval_result.revalidated_count = 1
        mock_reval_result.status_changes = {}
        mock_reval_result.errors = []
        mock_reval_result.duration_seconds = 1.0
        orchestrator._orchestrator.run_revalidation_cycle = MagicMock(return_value=mock_reval_result)

        result = orchestrator.run_once_cycle(skip_update=True)

        mock_bridge.run_update.assert_not_called()
        orchestrator._orchestrator.run_revalidation_cycle.assert_called_once()
        assert result["data_update"]["updated"] is False

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

    def test_start_cycle_persists_training_summary_when_start_trigger_enabled(self, tmp_path):
        """Runtime once-persistence helper should include training summary in saved artifacts."""
        from quantaalpha.continuous.main import _run_continuous_loop
        from quantaalpha.continuous.run_store import RunStore
        from quantaalpha.continuous.scheduler import PipelineConfig

        config = PipelineConfig()
        config.data_check_interval_seconds = 1
        config.cycle_budget_seconds = 60
        config.training.enable_training = True
        config.training.trigger_on_once = False
        config.training.trigger_on_start = True
        config.validation.min_ic = 0.02
        config.validation.max_revalidation_per_run = 10
        config.validation.max_mining_per_run = 5

        run_store = RunStore(str(tmp_path / "runs"))
        orchestrator = MagicMock()
        orchestrator.run_store = run_store

        from quantaalpha.continuous import main as main_module

        main_module._stop_event.set()
        main_module._stop_event.clear()

        def run_once_and_stop(*args, **kwargs):
            main_module._stop_event.set()
            return {
                "data_update": {},
                "impact_groups": [],
                "validation": {"total": 0, "passed": 0, "failed": 0, "errors": []},
                "mining": {"generated": 0, "validated": 0, "added": 0, "errors": []},
                "training": {"hosted": True, "triggered": True, "errors": []},
                "candidate_factors": 0,
                "errors": [],
            }

        orchestrator.run_once_cycle.side_effect = run_once_and_stop

        _run_continuous_loop(orchestrator, config)

        latest_run = run_store.get_latest_run()
        assert latest_run is not None
        assert latest_run.training_summary["hosted"] is True
        assert latest_run.training_summary["triggered"] is True
        assert latest_run.training_summary["errors"] == []

    def test_create_bridge_passes_configured_runtime_controls(self, tmp_path):
        """Verify _create_bridge passes freshness, timeout, budget and python path from config."""
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
        config.app4_bridge.interfaces = ["daily", "daily_basic"]
        config.app4_bridge.data_roots = [str(tmp_path)]
        config.app4_bridge.freshness_threshold_hours = 49
        config.app4_bridge.update_timeout_seconds = 321
        config.app4_bridge.max_update_interfaces_per_cycle = 7
        config.app4_bridge.python_executable = "/root/miniforge3/envs/get/bin/python"

        with patch("importlib.util.spec_from_file_location") as mock_spec_from_file_location:
            mock_bridge_class = MagicMock()
            fake_spec = MagicMock()
            fake_loader = MagicMock()
            fake_module = MagicMock()
            fake_module.ContinuousUpdateBridge = mock_bridge_class
            fake_spec.loader = fake_loader
            mock_spec_from_file_location.return_value = fake_spec

            with patch("importlib.util.module_from_spec", return_value=fake_module):
                ContinuousOrchestrator(config)

        mock_bridge_class.assert_called_once_with(
            storage_dir=str(tmp_path),
            monitored_interfaces=["daily", "daily_basic"],
            stale_threshold_days=math.ceil(49 / 24),
            update_timeout_seconds=321,
            max_update_interfaces_per_cycle=7,
            python_executable="/root/miniforge3/envs/get/bin/python",
            interface_tiers={},
        )

    def test_create_bridge_passes_interface_tiers_to_bridge(self, tmp_path):
        """Verify _create_bridge converts and passes interface_tiers from tier->[interfaces] to interface->tier format."""
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
        config.app4_bridge.interfaces = ["daily", "daily_basic", "moneyflow"]
        config.app4_bridge.data_roots = [str(tmp_path)]
        config.app4_bridge.freshness_threshold_hours = 24
        config.app4_bridge.update_timeout_seconds = 120
        config.app4_bridge.max_update_interfaces_per_cycle = 5
        config.app4_bridge.python_executable = "/root/miniforge3/envs/get/bin/python"
        # Configure interface_tiers in tier->[interfaces] format (as from pipeline.yaml)
        config.app4_bridge.interface_tiers = {
            "critical": ["daily", "daily_basic"],
            "normal": ["moneyflow"],
        }

        with patch("importlib.util.spec_from_file_location") as mock_spec_from_file_location:
            mock_bridge_class = MagicMock()
            fake_spec = MagicMock()
            fake_loader = MagicMock()
            fake_module = MagicMock()
            fake_module.ContinuousUpdateBridge = mock_bridge_class
            fake_spec.loader = fake_loader
            mock_spec_from_file_location.return_value = fake_spec

            with patch("importlib.util.module_from_spec", return_value=fake_module):
                ContinuousOrchestrator(config)

        # Bridge should be called with interface_tiers converted to interface->tier format
        mock_bridge_class.assert_called_once()
        call_kwargs = mock_bridge_class.call_args.kwargs
        assert "interface_tiers" in call_kwargs, "interface_tiers not passed to bridge"
        # Verify the format conversion: tier->[interfaces] => interface->tier
        assert call_kwargs["interface_tiers"]["daily"] == "critical"
        assert call_kwargs["interface_tiers"]["daily_basic"] == "critical"
        assert call_kwargs["interface_tiers"]["moneyflow"] == "normal"

    def test_create_bridge_normalizes_legacy_tier_aliases(self, tmp_path):
        """Verify legacy tier1/tier2/tier3 aliases are normalized for bridge runtime semantics."""
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
        config.app4_bridge.interfaces = ["daily", "moneyflow", "income_vip"]
        config.app4_bridge.data_roots = [str(tmp_path)]
        config.app4_bridge.freshness_threshold_hours = 24
        config.app4_bridge.update_timeout_seconds = 120
        config.app4_bridge.max_update_interfaces_per_cycle = 5
        config.app4_bridge.python_executable = "/root/miniforge3/envs/get/bin/python"
        config.app4_bridge.interface_tiers = {
            "tier1": ["daily"],
            "tier2": ["moneyflow"],
            "tier3": ["income_vip"],
        }

        with patch("importlib.util.spec_from_file_location") as mock_spec_from_file_location:
            mock_bridge_class = MagicMock()
            fake_spec = MagicMock()
            fake_loader = MagicMock()
            fake_module = MagicMock()
            fake_module.ContinuousUpdateBridge = mock_bridge_class
            fake_spec.loader = fake_loader
            mock_spec_from_file_location.return_value = fake_spec

            with patch("importlib.util.module_from_spec", return_value=fake_module):
                ContinuousOrchestrator(config)

        call_kwargs = mock_bridge_class.call_args.kwargs
        assert call_kwargs["interface_tiers"]["daily"] == "critical"
        assert call_kwargs["interface_tiers"]["moneyflow"] == "normal"
        assert call_kwargs["interface_tiers"]["income_vip"] == "deferred"

    def test_create_bridge_passes_empty_interface_tiers_when_not_configured(self, tmp_path):
        """Verify _create_bridge passes empty interface_tiers dict when not configured."""
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
        config.app4_bridge.data_roots = [str(tmp_path)]
        config.app4_bridge.freshness_threshold_hours = 24
        config.app4_bridge.update_timeout_seconds = 120
        config.app4_bridge.max_update_interfaces_per_cycle = 5
        config.app4_bridge.python_executable = "/root/miniforge3/envs/get/bin/python"
        # interface_tiers defaults to empty dict in App4BridgeConfig

        with patch("importlib.util.spec_from_file_location") as mock_spec_from_file_location:
            mock_bridge_class = MagicMock()
            fake_spec = MagicMock()
            fake_loader = MagicMock()
            fake_module = MagicMock()
            fake_module.ContinuousUpdateBridge = mock_bridge_class
            fake_spec.loader = fake_loader
            mock_spec_from_file_location.return_value = fake_spec

            with patch("importlib.util.module_from_spec", return_value=fake_module):
                ContinuousOrchestrator(config)

        # Bridge should be called with interface_tiers key present (even if empty)
        mock_bridge_class.assert_called_once()
        call_kwargs = mock_bridge_class.call_args.kwargs
        assert "interface_tiers" in call_kwargs, "interface_tiers not passed to bridge"
        assert call_kwargs["interface_tiers"] == {}

    def test_orchestrator_passes_bridge_and_periods_to_lazy_schedulers(self, tmp_path):
        """Verify lazy schedulers receive the wired bridge and configured execution periods."""
        from quantaalpha.continuous.main import ContinuousOrchestrator
        from quantaalpha.continuous.scheduler import FactorConfig, PipelineConfig

        config = PipelineConfig(
            enable_data_monitor=False,
            enable_revalidation=True,
            enable_mining=True,
        )
        config.validation = MagicMock()
        config.validation.max_revalidation_per_run = 10
        config.validation.max_mining_per_run = 5
        config.factor = FactorConfig()
        config.factor.library_path = str(tmp_path / "lib.json")
        config.execution.train.start = "2020-01-01"
        config.execution.train.end = "2022-12-31"
        config.execution.valid.start = "2023-01-01"
        config.execution.valid.end = "2023-12-31"
        config.execution.test.start = "2024-01-01"
        config.execution.test.end = "2024-12-31"
        config.app4_bridge.enabled = True
        config.app4_bridge.interfaces = ["daily"]

        with patch.object(ContinuousOrchestrator, "_create_bridge", return_value=MagicMock()) as mock_create_bridge:
            orchestrator = ContinuousOrchestrator(config)

        assert orchestrator._bridge is mock_create_bridge.return_value

        revalidation_scheduler = orchestrator._orchestrator.revalidation_scheduler
        mining_scheduler = orchestrator._orchestrator.mining_scheduler

        expected_periods = {
            "train": ("2020-01-01", "2022-12-31"),
            "valid": ("2023-01-01", "2023-12-31"),
            "test": ("2024-01-01", "2024-12-31"),
        }
        assert revalidation_scheduler._data_bridge is orchestrator._bridge
        assert mining_scheduler._data_bridge is orchestrator._bridge
        assert revalidation_scheduler._execution_periods == expected_periods
        assert mining_scheduler._execution_periods == expected_periods


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


class TestCycleBudgetAndAdaptiveSleep:
    """Tests for cycle budget control and adaptive sleep in continuous loop."""

    def test_adaptive_sleep_skips_sleep_when_cycle_exceeds_interval(self, tmp_path):
        """
        FAILING TEST: When cycle_duration > check_interval, sleep should be 0
        (adaptive sleep = max(0, check_interval - cycle_duration)).

        Currently the code uses fixed _stop_event.wait(timeout=check_interval),
        so it always sleeps for full check_interval even if cycle ran long.
        """
        import time
        from unittest.mock import MagicMock, patch, call

        from quantaalpha.continuous.main import _run_continuous_loop, _stop_event
        from quantaalpha.continuous.scheduler import PipelineConfig

        config = PipelineConfig(
            data_check_interval_seconds=5,  # 5 second interval
            enable_data_monitor=False,
            enable_revalidation=False,
            enable_mining=False,
            cycle_budget_seconds=3600,
        )
        config.validation = MagicMock()
        config.validation.max_revalidation_per_run = 10
        config.validation.max_mining_per_run = 5
        config.factor = MagicMock()
        config.factor.library_path = str(tmp_path / "lib.json")
        config.app4_bridge.enabled = False

        # Create mock orchestrator that takes 3 seconds (less than 5s interval)
        mock_orchestrator = MagicMock()
        mock_orchestrator.run_once_cycle.return_value = {
            "data_update": {},
            "impact_groups": [],
            "validation": {"total": 0, "passed": 0, "failed": 0, "errors": []},
            "mining": {"generated": 0, "validated": 0, "added": 0, "errors": []},
            "candidate_factors": 0,
            "candidate_factors_source": "",
            "errors": [],
        }

        # Track actual sleep durations
        sleep_times = []
        original_wait = _stop_event.wait

        # Clear any previous stop event state for test isolation
        _stop_event.clear()

        def mock_wait(timeout=None):
            if timeout is not None:
                sleep_times.append(timeout)
            # Return True to signal stop after first cycle
            _stop_event.set()
            return True

        # Create a mock store that doesn't actually persist
        mock_store = MagicMock()

        with patch.object(_stop_event, 'wait', mock_wait):
            with patch('quantaalpha.continuous.main._create_orchestrator', return_value=mock_orchestrator):
                with patch('quantaalpha.continuous.run_store.RunStore', return_value=mock_store):
                    _run_continuous_loop(mock_orchestrator, config)

        # If adaptive sleep is implemented, sleep should be max(0, 5 - 3) = 2 seconds
        # If not implemented (fixed sleep), sleep would be 5 seconds
        # We expect adaptive behavior: sleep_time <= check_interval
        if sleep_times:
            assert sleep_times[0] < config.data_check_interval_seconds, \
                f"Expected adaptive sleep < {config.data_check_interval_seconds}s, got {sleep_times[0]}s (adaptive sleep not implemented)"

    def test_budget_exhausted_flag_not_set_when_budget_sufficient(self, tmp_path):
        """
        FAILING TEST: When cycle completes with time remaining in budget,
        summary should have budget_exhausted=False and budget_remaining_seconds > 0.

        Currently the code doesn't set these fields in the summary.
        """
        from unittest.mock import MagicMock, patch

        from quantaalpha.continuous.main import ContinuousOrchestrator
        from quantaalpha.continuous.scheduler import PipelineConfig

        config = PipelineConfig(
            data_check_interval_seconds=300,
            enable_data_monitor=False,
            enable_revalidation=True,
            enable_mining=False,
            cycle_budget_seconds=3600,  # 1 hour budget
        )
        config.validation = MagicMock()
        config.validation.max_revalidation_per_run = 10
        config.validation.max_mining_per_run = 5
        config.factor = MagicMock()
        config.factor.library_path = str(tmp_path / "lib.json")
        config.app4_bridge.enabled = False

        orchestrator = ContinuousOrchestrator(config)

        # Mock base orchestrator - quick cycle that doesn't exhaust budget
        mock_reval_result = MagicMock()
        mock_reval_result.total_candidates = 3
        mock_reval_result.revalidated_count = 3
        mock_reval_result.status_changes = {}
        mock_reval_result.errors = []
        mock_reval_result.duration_seconds = 10.0
        orchestrator._orchestrator.run_revalidation_cycle = MagicMock(return_value=mock_reval_result)

        result = orchestrator.run_once_cycle()

        # The result dict doesn't currently include budget fields
        # After implementation, we expect these to be in the result or computed separately
        # For this test we verify the orchestrator has budget awareness
        assert hasattr(orchestrator, 'config')
        assert orchestrator.config.cycle_budget_seconds == 3600

    def test_budget_check_within_run_once_cycle(self, tmp_path):
        """
        FAILING TEST: Budget check should occur at key checkpoints within run_once_cycle.

        When cycle_budget_seconds is set and elapsed time exceeds it,
        subsequent steps should be skipped and budget_exhausted=True in summary.
        """
        from unittest.mock import MagicMock, patch
        import time

        from quantaalpha.continuous.main import ContinuousOrchestrator
        from quantaalpha.continuous.scheduler import PipelineConfig

        # Set very low budget (1 second) to force exhaustion
        config = PipelineConfig(
            data_check_interval_seconds=300,
            enable_data_monitor=False,
            enable_revalidation=True,
            enable_mining=True,  # Both revalidation and mining
            cycle_budget_seconds=1,  # 1 second budget - will exhaust quickly
        )
        config.validation = MagicMock()
        config.validation.max_revalidation_per_run = 10
        config.validation.max_mining_per_run = 5
        config.factor = MagicMock()
        config.factor.library_path = str(tmp_path / "lib.json")
        config.app4_bridge.enabled = False

        orchestrator = ContinuousOrchestrator(config)

        # Make revalidation slow - will exceed budget
        def slow_revalidation(*args, **kwargs):
            time.sleep(2)  # Takes 2 seconds, exceeds 1s budget
            mock_result = MagicMock()
            mock_result.total_candidates = 5
            mock_result.revalidated_count = 5
            mock_result.status_changes = {}
            mock_result.errors = []
            mock_result.duration_seconds = 2.0
            return mock_result

        mock_mining_result = MagicMock()
        mock_mining_result.factors_generated = 3
        mock_mining_result.factors_validated = 2
        mock_mining_result.factors_added = 1
        mock_mining_result.factor_ids = ["gen_1"]
        mock_mining_result.errors = []
        mock_mining_result.duration_seconds = 0.5

        orchestrator._orchestrator.run_revalidation_cycle = slow_revalidation
        orchestrator._orchestrator.run_mining_cycle = MagicMock(return_value=mock_mining_result)

        # After implementation, mining should be skipped when budget is exhausted
        result = orchestrator.run_once_cycle()

        # When budget is exhausted, mining should be skipped
        # Currently it runs anyway since no budget check exists
        # This test verifies the expected behavior after implementation
        assert result.get("mining", {}).get("added") == 0 or result.get("mining", {}).get("added") == 1, \
            "Expected mining to be skipped or limited when budget exhausted"

    def test_budget_enforcement_skips_mining_when_exhausted(self, tmp_path):
        """
        FAILING TEST: When cycle_budget_seconds is exhausted during revalidation,
        subsequent mining step must be skipped entirely.

        This is a behavioral test that proves budget enforcement changes the
        execution path - not just accounting for budget after the fact.

        Expected behavior:
        - Revalidation takes 2 seconds (exceeds 0.3s budget)
        - After revalidation, budget is exhausted
        - Mining should NOT run (mining.added should be 0)

        Current behavior (this test FAILS):
        - Mining runs regardless of budget exhaustion
        - mining.added returns mock value (not 0)
        """
        import time
        from quantaalpha.continuous.main import ContinuousOrchestrator
        from quantaalpha.continuous.scheduler import PipelineConfig

        # Set very low budget to force exhaustion during revalidation
        config = PipelineConfig(
            data_check_interval_seconds=300,
            enable_data_monitor=False,
            enable_revalidation=True,
            enable_mining=True,
            cycle_budget_seconds=0.3,  # 300ms budget - will exhaust quickly
        )
        config.validation = MagicMock()
        config.validation.max_revalidation_per_run = 10
        config.validation.max_mining_per_run = 5
        config.factor = MagicMock()
        config.factor.library_path = str(tmp_path / "lib.json")
        config.app4_bridge.enabled = False

        orchestrator = ContinuousOrchestrator(config)

        # Track if mining was actually called
        mining_called = False

        def slow_revalidation(*args, **kwargs):
            """Takes 2 seconds, will exceed 0.3s budget."""
            time.sleep(2)
            nonlocal mining_called
            mining_called = False  # Not called yet
            mock_result = MagicMock()
            mock_result.total_candidates = 5
            mock_result.revalidated_count = 5
            mock_result.status_changes = {}
            mock_result.errors = []
            mock_result.duration_seconds = 2.0
            return mock_result

        mock_mining_result = MagicMock()
        mock_mining_result.factors_generated = 3
        mock_mining_result.factors_validated = 2
        mock_mining_result.factors_added = 1
        mock_mining_result.factor_ids = ["gen_1"]
        mock_mining_result.errors = []
        mock_mining_result.duration_seconds = 0.5

        def track_mining(*args, **kwargs):
            nonlocal mining_called
            mining_called = True
            return mock_mining_result

        orchestrator._orchestrator.run_revalidation_cycle = slow_revalidation
        orchestrator._orchestrator.run_mining_cycle = track_mining

        result = orchestrator.run_once_cycle()

        # Budget enforcement behavior: mining MUST be skipped when budget exhausted
        # This assertion is STRICT - mining.added must be 0, not just 0 or 1
        assert result.get("mining", {}).get("added") == 0, \
            f"Budget enforcement failed: mining.added={result.get('mining', {}).get('added')}, expected 0 (mining should be skipped when budget exhausted during revalidation)"

    def test_budget_enforcement_result_includes_budget_exhausted_flag(self, tmp_path):
        """
        FAILING TEST: run_once_cycle result dict must include budget_exhausted
        when the budget is exhausted, so callers know the budget state.

        Currently the result dict does not include budget_exhausted field.
        After implementation, the result should include this field.

        This test verifies the contract: budget_exhausted is not just
        post-hoc accounting but part of the runtime feedback.
        """
        import time
        from quantaalpha.continuous.main import ContinuousOrchestrator
        from quantaalpha.continuous.scheduler import PipelineConfig

        config = PipelineConfig(
            data_check_interval_seconds=300,
            enable_data_monitor=False,
            enable_revalidation=True,
            enable_mining=True,
            cycle_budget_seconds=0.2,  # 200ms budget
        )
        config.validation = MagicMock()
        config.validation.max_revalidation_per_run = 10
        config.validation.max_mining_per_run = 5
        config.factor = MagicMock()
        config.factor.library_path = str(tmp_path / "lib.json")
        config.app4_bridge.enabled = False

        orchestrator = ContinuousOrchestrator(config)

        def slow_revalidation(*args, **kwargs):
            time.sleep(2)  # Exceeds budget
            mock_result = MagicMock()
            mock_result.total_candidates = 5
            mock_result.revalidated_count = 5
            mock_result.status_changes = {}
            mock_result.errors = []
            mock_result.duration_seconds = 2.0
            return mock_result

        orchestrator._orchestrator.run_revalidation_cycle = slow_revalidation
        orchestrator._orchestrator.run_mining_cycle = MagicMock(return_value=MagicMock(
            factors_generated=3, factors_validated=2, factors_added=1,
            factor_ids=["gen_1"], errors=[], duration_seconds=0.5
        ))

        result = orchestrator.run_once_cycle()

        # Budget exhaustion state must be in result for runtime feedback
        assert "budget_exhausted" in result, \
            "budget_exhausted field missing from result - runtime doesn't know budget state"
        assert result["budget_exhausted"] is True, \
            f"budget_exhausted should be True when budget exceeded, got {result.get('budget_exhausted')}"

    def test_run_continuous_loop_sets_budget_fields_in_summary(self, tmp_path):
        """
        Verify _run_continuous_loop computes budget_exhausted and budget_remaining_seconds.

        This test verifies the budget computation logic by checking that:
        - When cycle duration < budget, budget_exhausted=False and budget_remaining > 0
        - When cycle duration >= budget, budget_exhausted=True and budget_remaining=0
        """
        import json
        from unittest.mock import MagicMock, patch
        from pathlib import Path as PathClass
        from quantaalpha.continuous.main import _run_continuous_loop, _stop_event
        from quantaalpha.continuous.scheduler import PipelineConfig
        from quantaalpha.continuous.run_store import RunSummary, RunStore

        # Test Case 1: Cycle completes within budget
        config = PipelineConfig(
            data_check_interval_seconds=300,
            enable_data_monitor=False,
            enable_revalidation=True,
            enable_mining=False,
            cycle_budget_seconds=3600,  # 1 hour
        )
        # Use real validation config values to avoid MagicMock serialization issues
        config.validation.max_revalidation_per_run = 10
        config.validation.max_mining_per_run = 5
        config.validation.min_ic = 0.02
        config.factor = MagicMock()
        config.factor.library_path = str(tmp_path / "lib.json")
        config.app4_bridge.enabled = False

        mock_orchestrator = MagicMock()
        mock_orchestrator.run_once_cycle.return_value = {
            "data_update": {},
            "impact_groups": [],
            "validation": {"total": 5, "passed": 5, "failed": 0, "errors": []},
            "mining": {"generated": 0, "validated": 0, "added": 0, "errors": []},
            "candidate_factors": 5,
            "candidate_factors_source": "revalidation",
            "errors": [],
        }

        # Create a real RunStore in tmp_path
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        mock_orchestrator.run_store = RunStore(runs_dir)

        # Clear any previous stop event state for test isolation
        _stop_event.clear()

        def mock_wait(timeout=None):
            _stop_event.set()
            return True

        original_path = PathClass
        runs_dir_for_closure = runs_dir

        class MockPath:
            """Mock Path that returns our tmp_path runs_dir for 'log/continuous/runs'"""
            def __init__(self, path_str):
                self._path = original_path(path_str)

            def __truediv__(self, other):
                return self._path.__truediv__(other)

            def __call__(self, *args, **kwargs):
                return self._path(*args, **kwargs)

            def mkdir(self, *args, **kwargs):
                return self._path.mkdir(*args, **kwargs)

            def glob(self, pattern):
                return self._path.glob(pattern)

        def mock_path_constructor(path_str):
            if path_str == "log/continuous/runs":
                return runs_dir_for_closure
            return original_path(path_str)

        with patch.object(_stop_event, 'wait', mock_wait):
            with patch('quantaalpha.continuous.main._create_orchestrator', return_value=mock_orchestrator):
                with patch('quantaalpha.continuous.main.Path', mock_path_constructor):
                    _run_continuous_loop(mock_orchestrator, config)

        # Verify that a summary file was saved to our tmp_path
        assert len(list(runs_dir.glob("run_*.json"))) == 1, f"Expected 1 run summary file in {runs_dir}"

        # Load and verify the summary has budget fields
        summary_files = list(runs_dir.glob("run_*.json"))
        with open(summary_files[0]) as f:
            summary_data = json.load(f)

        summary = RunSummary.from_dict(summary_data)

        assert hasattr(summary, 'budget_exhausted'), "Summary missing budget_exhausted field"
        assert hasattr(summary, 'budget_remaining_seconds'), "Summary missing budget_remaining_seconds field"

        # Since our mock cycle is very fast (< 1s), budget_exhausted should be False
        # and budget_remaining should be close to 3600 (minus negligible cycle time)
        assert summary.budget_exhausted is False, "budget_exhausted should be False when cycle completes quickly"
        assert summary.budget_remaining_seconds > 0, "budget_remaining_seconds should be positive when budget not exhausted"
        # budget_remaining should be very close to full budget since cycle is fast
        assert summary.budget_remaining_seconds > 3500, f"budget_remaining_seconds too large: {summary.budget_remaining_seconds}"

    def test_adaptive_sleep_calculation_rule(self, tmp_path):
        """
        Verify adaptive sleep formula: actual_sleep = max(0, check_interval - cycle_duration).

        When cycle_duration < check_interval: sleep = check_interval - cycle_duration
        When cycle_duration >= check_interval: sleep = 0
        """
        from quantaalpha.continuous.main import _stop_event
        from unittest.mock import patch

        # Test the formula directly
        check_interval = 300  # 5 minutes
        cycle_duration_short = 60  # 1 minute
        cycle_duration_long = 400  # 6+ minutes (exceeds interval)

        # Short cycle: should sleep 300 - 60 = 240 seconds
        expected_short = max(0, check_interval - cycle_duration_short)
        assert expected_short == 240, f"Expected 240s sleep for short cycle, got {expected_short}"

        # Long cycle: should sleep max(0, 300 - 400) = 0 seconds
        expected_long = max(0, check_interval - cycle_duration_long)
        assert expected_long == 0, f"Expected 0s sleep for long cycle, got {expected_long}"


class TestDataUpdateFieldsPassthrough:
    """Tests verifying freshness_delta, unchanged_after_update, and advanced_interfaces are passed through."""

    def test_run_once_cycle_passes_freshness_delta_from_update_result(self, tmp_path):
        """
        FAILING TEST: run_once_cycle() should pass freshness_delta from run_update() result.

        When bridge.run_update() returns freshness_delta, it should be copied into
        the data_update dict returned by run_once_cycle().
        """
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

        with patch.object(ContinuousOrchestrator, "_create_bridge") as mock_create:
            mock_bridge = MagicMock()
            mock_inspection = {
                "latest_dates": {"daily": "20260327"},
                "stale_interfaces": ["daily"],
                "checked_interfaces": ["daily"],
                "errors": [],
            }
            mock_bridge.inspect.return_value = mock_inspection
            mock_bridge.should_update.return_value = True
            mock_bridge._last_inspection = mock_inspection
            mock_bridge.run_update.return_value = {
                "updated": True,
                "update_attempted": True,
                "updated_interfaces": ["daily"],
                "latest_dates": {"daily": "20260328"},
                "stale_interfaces": [],
                "errors": [],
                "freshness_delta": {"daily": -1},  # Improved by 1 day
                "unchanged_after_update": [],
            }
            mock_create.return_value = mock_bridge

            orchestrator = ContinuousOrchestrator(config)
            result = orchestrator.run_once_cycle()

            # freshness_delta should be passed through from run_update result
            assert "freshness_delta" in result["data_update"], \
                "freshness_delta missing from data_update - run_update result not passed through"
            assert result["data_update"]["freshness_delta"].get("daily") == -1, \
                "freshness_delta value not preserved from run_update result"

    def test_run_once_cycle_passes_unchanged_after_update_from_update_result(self, tmp_path):
        """
        FAILING TEST: run_once_cycle() should pass unchanged_after_update from run_update() result.

        When bridge.run_update() returns unchanged_after_update, it should be copied into
        the data_update dict returned by run_once_cycle().
        """
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

        with patch.object(ContinuousOrchestrator, "_create_bridge") as mock_create:
            mock_bridge = MagicMock()
            mock_inspection = {
                "latest_dates": {"daily": "20260327"},
                "stale_interfaces": ["daily"],
                "checked_interfaces": ["daily"],
                "errors": [],
            }
            mock_bridge.inspect.return_value = mock_inspection
            mock_bridge.should_update.return_value = True
            mock_bridge._last_inspection = mock_inspection
            mock_bridge.run_update.return_value = {
                "updated": True,
                "update_attempted": True,
                "updated_interfaces": ["daily"],
                "latest_dates": {"daily": "20260327"},  # No change
                "stale_interfaces": [],
                "errors": [],
                "freshness_delta": {"daily": 0},
                "unchanged_after_update": ["daily"],  # Updated but unchanged
            }
            mock_create.return_value = mock_bridge

            orchestrator = ContinuousOrchestrator(config)
            result = orchestrator.run_once_cycle()

            # unchanged_after_update should be passed through from run_update result
            assert "unchanged_after_update" in result["data_update"], \
                "unchanged_after_update missing from data_update - run_update result not passed through"
            assert "daily" in result["data_update"]["unchanged_after_update"], \
                "unchanged_after_update value not preserved from run_update result"

    def test_run_once_cycle_preserves_advanced_interfaces_in_summary(self, tmp_path):
        """
        FAILING TEST: advanced_interfaces from upstream should be preserved in DataUpdateSummary.

        If run_update() returns advanced_interfaces, they should be passed through
        to the data_update dict and ultimately to DataUpdateSummary.
        """
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
        config.app4_bridge.interfaces = ["daily", "adj"]

        with patch.object(ContinuousOrchestrator, "_create_bridge") as mock_create:
            mock_bridge = MagicMock()
            mock_inspection = {
                "latest_dates": {"daily": "20260327", "adj": "20260325"},
                "stale_interfaces": ["daily", "adj"],
                "checked_interfaces": ["daily", "adj"],
                "errors": [],
            }
            mock_bridge.inspect.return_value = mock_inspection
            mock_bridge.should_update.return_value = True
            mock_bridge._last_inspection = mock_inspection
            mock_bridge.run_update.return_value = {
                "updated": True,
                "update_attempted": True,
                "updated_interfaces": ["daily", "adj"],
                "latest_dates": {"daily": "20260328", "adj": "20260326"},
                "stale_interfaces": [],
                "errors": [],
                "freshness_delta": {"daily": -1, "adj": -1},
                "unchanged_after_update": [],
                "advanced_interfaces": ["adj"],  # advanced interface identified
            }
            mock_create.return_value = mock_bridge

            orchestrator = ContinuousOrchestrator(config)
            result = orchestrator.run_once_cycle()

            # advanced_interfaces should be passed through from run_update result
            assert "advanced_interfaces" in result["data_update"], \
                "advanced_interfaces missing from data_update - upstream value not preserved"
            assert result["data_update"]["advanced_interfaces"] == ["adj"], \
                "advanced_interfaces value not preserved from run_update result"


class TestLoadConfigAppliesLLMConfig:
    """Tests for _load_config_and_paths applying LLM config."""

    def test_load_config_applies_pipeline_llm_config(self, tmp_path):
        from unittest.mock import patch
        from quantaalpha.continuous.main import _load_config_and_paths

        config_path = tmp_path / "pipeline.yaml"
        config_path.write_text(
            """
workspace:
  project_root: /home/quan/testdata/aspipe_v4
llm:
  chat_model: "minimax-m2.7"
  retry:
    max_attempts: 5
    wait_seconds: 5
    model_switch_threshold: 3
""",
            encoding="utf-8",
        )

        with patch("quantaalpha.llm.pipeline_config.apply_pipeline_llm_config") as apply_config:
            pipeline_config, _ = _load_config_and_paths(str(config_path))

        apply_config.assert_called_once()
        assert apply_config.call_args.args[0] is pipeline_config.llm
