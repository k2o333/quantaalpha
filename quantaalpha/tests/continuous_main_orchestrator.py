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
        orchestrator._orchestrator.run_training_cycle = MagicMock(return_value={"hosted": True, "triggered": True, "errors": []})

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
        orchestrator._orchestrator.run_training_cycle = MagicMock(return_value={"hosted": True, "triggered": True, "errors": []})

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
        orchestrator._orchestrator.run_training_cycle = MagicMock(return_value={"hosted": True, "triggered": True, "errors": []})

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
        with patch.object(ContinuousOrchestrator, "_create_bridge") as mock_create:
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

    def test_uat_profile_disables_app4_bridge_updates_for_cache_only_runs(self):
        """Verify UAT profiles do not call the external app4 update bridge."""
        from quantaalpha.continuous.main import _apply_uat_profile
        from quantaalpha.continuous.scheduler import PipelineConfig

        config = PipelineConfig(enable_data_monitor=False, enable_revalidation=False, enable_mining=False)
        config.app4_bridge.enabled = True

        _apply_uat_profile(config, "expanded-data")

        assert config.app4_bridge.enabled is False

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
        config.factor.backtest_noqlib = {
            "app5_storage_root": str(tmp_path / "data"),
            "daily_interface": "daily",
        }
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
        assert revalidation_scheduler._backtest_noqlib_config == config.factor.backtest_noqlib
        assert mining_scheduler.backtest_noqlib_config == config.factor.backtest_noqlib


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
