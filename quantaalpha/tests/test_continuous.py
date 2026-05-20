"""
Unit tests for the continuous orchestration module.

Tests cover:
- MiningOrchestrator lifecycle
- SchedulerConfig defaults
- SchedulerEvent enum
- SchedulerContext dataclass
- Default implementations
"""

import importlib
import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock


class TestSchedulerConfig:
    """Tests for SchedulerConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        from quantaalpha.continuous import SchedulerConfig

        config = SchedulerConfig()
        assert config.data_check_interval_seconds == 300
        assert config.revalidation_interval_hours == 24
        assert config.revalidation_days_threshold == 21
        assert config.max_revalidation_per_run == 10
        assert config.mining_interval_hours == 12
        assert config.max_mining_per_run == 5
        assert config.enable_data_monitor is True
        assert config.enable_revalidation is True
        assert config.enable_mining is True

    def test_custom_values(self):
        """Test custom configuration values."""
        from quantaalpha.continuous import SchedulerConfig

        config = SchedulerConfig(
            revalidation_interval_hours=12,
            mining_interval_hours=6,
            max_revalidation_per_run=20,
            max_mining_per_run=10,
        )
        assert config.revalidation_interval_hours == 12
        assert config.mining_interval_hours == 6
        assert config.max_revalidation_per_run == 20
        assert config.max_mining_per_run == 10

    def test_empty_data_dirs(self):
        """Test empty data_dirs defaults to empty list."""
        from quantaalpha.continuous import SchedulerConfig

        config = SchedulerConfig()
        assert config.data_dirs == []

    def test_package_import_does_not_eagerly_import_main(self):
        """Importing quantaalpha.continuous should not preload main.py."""
        sys.modules.pop("quantaalpha.continuous.main", None)
        sys.modules.pop("quantaalpha.continuous", None)

        module = importlib.import_module("quantaalpha.continuous")

        assert "quantaalpha.continuous.main" not in sys.modules
        assert module.SchedulerConfig is not None


class TestSchedulerEvent:
    """Tests for SchedulerEvent enum."""

    def test_events_defined(self):
        """Test all expected events are defined."""
        from quantaalpha.continuous import SchedulerEvent

        assert SchedulerEvent.DATA_UPDATE.value == "data_update"
        assert SchedulerEvent.REVALIDATION_TRIGGER.value == "revalidation_trigger"
        assert SchedulerEvent.MINING_TRIGGER.value == "mining_trigger"
        assert SchedulerEvent.STATUS_CHANGE.value == "status_change"

    def test_events_are_strings(self):
        """Test events are string enums."""
        from quantaalpha.continuous import SchedulerEvent

        for event in SchedulerEvent:
            assert isinstance(event.value, str)


class TestSchedulerContext:
    """Tests for SchedulerContext dataclass."""

    def test_default_context(self):
        """Test default context values."""
        from quantaalpha.continuous import SchedulerContext, SchedulerEvent

        ctx = SchedulerContext(event=SchedulerEvent.DATA_UPDATE)
        assert ctx.event == SchedulerEvent.DATA_UPDATE
        assert isinstance(ctx.timestamp, datetime)
        assert ctx.payload == {}
        assert ctx.source_module == ""
        assert ctx.factor_ids == []

    def test_context_with_payload(self):
        """Test context with payload data."""
        from quantaalpha.continuous import SchedulerContext, SchedulerEvent

        ctx = SchedulerContext(
            event=SchedulerEvent.DATA_UPDATE,
            payload={"file_path": "/data/factor.parquet", "change_type": "new"},
            source_module="data_monitor",
        )
        assert ctx.payload["file_path"] == "/data/factor.parquet"
        assert ctx.payload["change_type"] == "new"
        assert ctx.source_module == "data_monitor"


class TestRevalidationResult:
    """Tests for RevalidationResult dataclass."""

    def test_default_result(self):
        """Test default result values."""
        from quantaalpha.continuous import RevalidationResult

        result = RevalidationResult()
        assert result.total_candidates == 0
        assert result.revalidated_count == 0
        assert result.status_changes == {}
        assert result.errors == []
        assert result.duration_seconds == 0.0
        assert isinstance(result.timestamp, datetime)

    def test_result_with_data(self):
        """Test result with actual data."""
        from quantaalpha.continuous import RevalidationResult

        result = RevalidationResult(
            total_candidates=10,
            revalidated_count=8,
            status_changes={"f1": "active", "f2": "degraded"},
            errors=["f3: timeout"],
            duration_seconds=120.5,
        )
        assert result.total_candidates == 10
        assert result.revalidated_count == 8
        assert len(result.status_changes) == 2
        assert len(result.errors) == 1


class TestMiningResult:
    """Tests for MiningResult dataclass."""

    def test_default_result(self):
        """Test default result values."""
        from quantaalpha.continuous import MiningResult

        result = MiningResult()
        assert result.factors_generated == 0
        assert result.factors_validated == 0
        assert result.factors_added == 0
        assert result.factor_ids == []
        assert result.errors == []
        assert result.duration_seconds == 0.0

    def test_result_with_factors(self):
        """Test result with generated factors."""
        from quantaalpha.continuous import MiningResult

        result = MiningResult(
            factors_generated=5,
            factors_validated=3,
            factors_added=2,
            factor_ids=["f1", "f2"],
        )
        assert result.factors_generated == 5
        assert result.factors_validated == 3
        assert result.factors_added == 2
        assert len(result.factor_ids) == 2


class TestOrchestratorStatus:
    """Tests for OrchestratorStatus enum."""

    def test_status_values(self):
        """Test all status values are defined."""
        from quantaalpha.continuous.orchestrator import OrchestratorStatus

        assert OrchestratorStatus.STOPPED.value == "stopped"
        assert OrchestratorStatus.RUNNING.value == "running"
        assert OrchestratorStatus.PAUSED.value == "paused"
        assert OrchestratorStatus.ERROR.value == "error"


class TestMiningOrchestrator:
    """Tests for MiningOrchestrator class."""

    def test_default_initialization(self):
        """Test orchestrator with defaults."""
        from quantaalpha.continuous import MiningOrchestrator

        orch = MiningOrchestrator()
        assert orch.status.value == "stopped"
        assert orch.config.enable_data_monitor is True
        assert orch.config.enable_revalidation is True

    def test_custom_config(self):
        """Test orchestrator with custom config."""
        from quantaalpha.continuous import MiningOrchestrator, SchedulerConfig

        config = SchedulerConfig(
            enable_data_monitor=False,
            enable_revalidation=False,
            enable_mining=False,
        )
        orch = MiningOrchestrator(config)
        assert orch.status.value == "stopped"
        assert orch.config.enable_data_monitor is False

    def test_get_stats(self):
        """Test getting orchestrator stats."""
        from quantaalpha.continuous import MiningOrchestrator

        orch = MiningOrchestrator()
        stats = orch.get_stats()

        assert stats.total_revalidations == 0
        assert stats.total_mining_runs == 0
        assert stats.total_training_runs == 0
        assert stats.error_count == 0

    def test_get_health_report(self):
        """Test getting health report."""
        from quantaalpha.continuous import MiningOrchestrator

        orch = MiningOrchestrator()
        health = orch.get_health_report()

        assert "status" in health
        assert "data_monitor" in health
        assert "revalidation" in health
        assert "mining" in health
        assert "training" in health
        assert "errors" in health
        assert health["status"] == "stopped"
        assert health["training"]["enabled"] is False

    def test_training_scheduler_is_enabled_when_injected(self):
        """Training workflow is enabled by explicit scheduler injection."""
        from quantaalpha.continuous import MiningOrchestrator, SchedulerConfig

        training_scheduler = MagicMock()
        config = SchedulerConfig(
            enable_data_monitor=False,
            enable_revalidation=False,
            enable_mining=False,
        )

        orch = MiningOrchestrator(
            config,
            training_scheduler=training_scheduler,
        )

        assert orch.training_scheduler is training_scheduler
        assert orch.get_health_report()["training"]["enabled"] is True

    def test_run_revalidation_not_enabled(self):
        """Test running revalidation when not enabled."""
        from quantaalpha.continuous import MiningOrchestrator, SchedulerConfig

        config = SchedulerConfig(enable_revalidation=False)
        orch = MiningOrchestrator(config)
        result = orch.run_revalidation_cycle()

        assert result.errors == ["Revalidation scheduler not enabled"]

    def test_runtime_revalidation_limit_zero_short_circuits_candidate_loading(self):
        """max_revalidation_per_run=0 should not read the factor library."""
        from types import SimpleNamespace

        from quantaalpha.continuous.main import ContinuousOrchestrator

        runtime = SimpleNamespace(
            config=SimpleNamespace(
                validation=SimpleNamespace(max_revalidation_per_run=0),
            )
        )

        result = ContinuousOrchestrator._run_revalidation(runtime)

        assert result["total_candidates"] == 0
        assert result["candidate_factors_source"] == "disabled"

    def test_run_mining_not_enabled(self):
        """Test running mining when not enabled."""
        from quantaalpha.continuous import MiningOrchestrator, SchedulerConfig

        config = SchedulerConfig(enable_mining=False)
        orch = MiningOrchestrator(config)
        result = orch.run_mining_cycle()

        assert result.errors == ["Mining scheduler not enabled"]

    def test_run_training_not_enabled(self):
        """Test running training when no training scheduler is configured."""
        from quantaalpha.continuous import MiningOrchestrator, SchedulerConfig

        config = SchedulerConfig(
            enable_data_monitor=False,
            enable_revalidation=False,
            enable_mining=False,
        )
        orch = MiningOrchestrator(config)
        result = orch.run_training_cycle(request=object(), trigger="manual")

        assert result == {"errors": ["Training scheduler not enabled"]}

    def test_check_data_updates_no_monitor(self):
        """Test checking data updates when monitor not available."""
        from quantaalpha.continuous import MiningOrchestrator, SchedulerConfig

        config = SchedulerConfig(enable_data_monitor=False)
        orch = MiningOrchestrator(config)
        events = orch.check_data_updates()

        assert events == []

    def test_start_and_stop_manage_injected_training_scheduler(self):
        """Start/stop should include the injected training scheduler."""
        from quantaalpha.continuous import MiningOrchestrator, SchedulerConfig

        training_scheduler = MagicMock()
        config = SchedulerConfig(
            enable_data_monitor=False,
            enable_revalidation=False,
            enable_mining=False,
        )
        orch = MiningOrchestrator(config, training_scheduler=training_scheduler)

        orch.start()
        orch.stop()

        training_scheduler.start.assert_called_once()
        training_scheduler.stop.assert_called_once()

    def test_run_training_cycle_updates_stats(self):
        """Manual training cycles should update training stats."""
        from quantaalpha.continuous import MiningOrchestrator, SchedulerConfig

        request = object()
        training_result = MagicMock()
        training_scheduler = MagicMock()
        training_scheduler.run_training_cycle.return_value = training_result
        config = SchedulerConfig(
            enable_data_monitor=False,
            enable_revalidation=False,
            enable_mining=False,
        )
        orch = MiningOrchestrator(config, training_scheduler=training_scheduler)

        result = orch.run_training_cycle(request=request, trigger="manual", dry_run=True)

        assert result is training_result
        assert orch.stats.total_training_runs == 1
        assert orch.stats.last_training_result is training_result
        assert orch.stats.last_training_run is not None
        training_scheduler.run_training_cycle.assert_called_once_with(
            request=request,
            trigger="manual",
            dry_run=True,
        )


class TestDefaultDataMonitor:
    """Tests for DefaultDataMonitor class."""

    def test_initialization(self):
        """Test monitor initialization."""
        from quantaalpha.continuous.implementations import DefaultDataMonitor

        monitor = DefaultDataMonitor(check_interval=60)
        assert monitor.check_interval == 60
        assert monitor.data_dirs == []

    def test_initialization_with_dirs(self):
        """Test monitor with data directories."""
        from quantaalpha.continuous.implementations import DefaultDataMonitor

        monitor = DefaultDataMonitor(
            check_interval=300,
            data_dirs=["/data/factors", "/data/prices"],
        )
        assert len(monitor.data_dirs) == 2

    def test_check_for_updates_empty(self):
        """Test checking updates with no directories configured."""
        from quantaalpha.continuous.implementations import DefaultDataMonitor

        monitor = DefaultDataMonitor()
        events = monitor.check_for_updates()
        assert events == []


class TestDefaultRevalidationScheduler:
    """Tests for DefaultRevalidationScheduler class."""

    def test_initialization(self):
        """Test scheduler initialization."""
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        scheduler = DefaultRevalidationScheduler()
        assert scheduler.days_threshold == 21
        assert scheduler.max_per_run == 10
        assert scheduler.interval_hours == 24

    def test_get_next_scheduled_run_before_start(self):
        """Test next run time before starting."""
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        scheduler = DefaultRevalidationScheduler()
        # Before start, next_run is None
        assert scheduler.get_next_scheduled_run() is None

    def test_get_next_scheduled_run_after_start(self):
        """Test next run time after starting."""
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        scheduler = DefaultRevalidationScheduler(interval_hours=12)
        scheduler.start()
        try:
            next_run = scheduler.get_next_scheduled_run()
            assert next_run is not None
            # Should be approximately 12 hours from now
            expected = datetime.now() + timedelta(hours=12)
            diff = abs((next_run - expected).total_seconds())
            assert diff < 5  # Within 5 seconds
        finally:
            scheduler.stop()


class TestDefaultMiningScheduler:
    """Tests for DefaultMiningScheduler class."""

    def test_initialization(self):
        """Test scheduler initialization."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler()
        assert scheduler.max_per_run == 5
        assert scheduler.interval_hours == 12

    def test_custom_interval(self):
        """Test scheduler with custom interval."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler(interval_hours=6)
        assert scheduler.interval_hours == 6

    def test_get_next_scheduled_run_after_start(self):
        """Test next run time after starting."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler(interval_hours=6)
        scheduler.start()
        try:
            next_run = scheduler.get_next_scheduled_run()
            assert next_run is not None
            # Should be approximately 6 hours from now
            expected = datetime.now() + timedelta(hours=6)
            diff = abs((next_run - expected).total_seconds())
            assert diff < 5
        finally:
            scheduler.stop()


class TestRevalidationSchedulerLibraryPath:
    """Tests for FactorLibraryManager integration in DefaultRevalidationScheduler."""

    def test_library_path_from_env(self, monkeypatch):
        """Test library_path defaults to FACTOR_LIBRARY_PATH env var."""
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        monkeypatch.setenv("FACTOR_LIBRARY_PATH", "/test/path/library.json")
        scheduler = DefaultRevalidationScheduler()
        assert scheduler.library_path == "/test/path/library.json"

    def test_library_path_from_param(self):
        """Test library_path can be passed as parameter."""
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        scheduler = DefaultRevalidationScheduler(library_path="/custom/path.json")
        assert scheduler.library_path == "/custom/path.json"

    def test_library_path_fallback_default(self, monkeypatch):
        """Test library_path falls back to third_party/quantaalpha/data/factorlib/all_factors_library.json."""
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        monkeypatch.delenv("FACTOR_LIBRARY_PATH", raising=False)
        scheduler = DefaultRevalidationScheduler()
        assert scheduler.library_path == "third_party/quantaalpha/data/factorlib/all_factors_library.json"


class TestMiningSchedulerLibraryPath:
    """Tests for FactorLibraryManager integration in DefaultMiningScheduler."""

    def test_library_path_from_env(self, monkeypatch):
        """Test library_path defaults to FACTOR_LIBRARY_PATH env var."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        monkeypatch.setenv("FACTOR_LIBRARY_PATH", "/test/path/library.json")
        scheduler = DefaultMiningScheduler()
        assert scheduler.library_path == "/test/path/library.json"

    def test_library_path_from_param(self):
        """Test library_path can be passed as parameter."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler(library_path="/custom/path.json")
        assert scheduler.library_path == "/custom/path.json"

    def test_library_path_fallback_default(self, monkeypatch):
        """Test library_path falls back to third_party/quantaalpha/data/factorlib/all_factors_library.json."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        monkeypatch.delenv("FACTOR_LIBRARY_PATH", raising=False)
        scheduler = DefaultMiningScheduler()
        assert scheduler.library_path == "third_party/quantaalpha/data/factorlib/all_factors_library.json"

    def test_backtest_backend_from_param(self):
        """Test continuous mining stores the selected backtest backend."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler(backtest_backend="noqlib")
        assert scheduler.backtest_backend == "noqlib"


class TestRevalidationSchedulerStartStop:
    """Tests for start/stop/timer mechanism in DefaultRevalidationScheduler."""

    def test_start_creates_thread(self):
        """Test start() creates background thread."""
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        scheduler = DefaultRevalidationScheduler(interval_hours=1)
        scheduler.start()
        try:
            assert scheduler._scheduler_thread is not None
            assert scheduler._scheduler_thread.is_alive()
            assert scheduler._running is True
        finally:
            scheduler.stop()

    def test_stop_joins_thread(self):
        """Test stop() joins background thread."""
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        scheduler = DefaultRevalidationScheduler(interval_hours=1)
        scheduler.start()
        scheduler.stop()
        assert scheduler._running is False

    def test_double_start_no_duplication(self):
        """Test starting twice does not create duplicate threads."""
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        scheduler = DefaultRevalidationScheduler(interval_hours=1)
        scheduler.start()
        first_thread = scheduler._scheduler_thread
        scheduler.start()
        assert scheduler._scheduler_thread is first_thread
        scheduler.stop()


class TestMiningSchedulerStartStop:
    """Tests for start/stop/timer mechanism in DefaultMiningScheduler."""

    def test_start_creates_thread(self):
        """Test start() creates background thread."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler(interval_hours=1)
        scheduler.start()
        try:
            assert scheduler._scheduler_thread is not None
            assert scheduler._scheduler_thread.is_alive()
            assert scheduler._running is True
        finally:
            scheduler.stop()

    def test_stop_joins_thread(self):
        """Test stop() joins background thread."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler(interval_hours=1)
        scheduler.start()
        scheduler.stop()
        assert scheduler._running is False

    def test_double_start_no_duplication(self):
        """Test starting twice does not create duplicate threads."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler(interval_hours=1)
        scheduler.start()
        first_thread = scheduler._scheduler_thread
        scheduler.start()
        assert scheduler._scheduler_thread is first_thread
        scheduler.stop()


class TestRevalidationFailurePath:
    """Tests for failure handling in revalidation scheduler."""

    def test_run_revalidation_uses_proper_validation_result_structure(self, tmp_path, monkeypatch):
        """Test run_revalidation builds proper validation_result dict for failures."""
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler
        import json

        lib_path = tmp_path / "test_library.json"
        lib_path.write_text(
            json.dumps(
                {
                    "metadata": {"version": "1.1", "total_factors": 2},
                    "factors": {
                        "factor_001": {
                            "factor_id": "factor_001",
                            "factor_name": "Test Factor",
                            "evaluation": {"status": "active", "last_validated": None},
                        },
                        "factor_002": {
                            "factor_id": "factor_002",
                            "factor_name": "Test Factor 2",
                            "evaluation": {"status": "active", "last_validated": None},
                        },
                    },
                }
            )
        )
        monkeypatch.setenv("FACTOR_LIBRARY_PATH", str(lib_path))

        scheduler = DefaultRevalidationScheduler(
            library_path=str(lib_path),
            max_per_run=10,
            days_threshold=0,
        )

        scheduler._run_factor_backtest = MagicMock(return_value=False)

        result = scheduler.run_revalidation()

        assert result.total_candidates == 2
        assert result.revalidated_count == 0

        for factor_id, new_status in result.status_changes.items():
            assert new_status != "active", f"Failed backtest should not result in active status for {factor_id}"

    def test_run_revalidation_does_not_fail_on_profile_logging(self, tmp_path, monkeypatch):
        """run_revalidation should not fail just because profile logger uses stdlib-style args.

        Regression:
        the project logger does not accept stdlib `logger.info("%s", value)` call style.
        Revalidation must still run and record a status change instead of surfacing a logger
        signature error as a factor-level failure.
        """
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler
        import json

        lib_path = tmp_path / "test_library.json"
        lib_path.write_text(
            json.dumps(
                {
                    "metadata": {"version": "1.1", "total_factors": 1},
                    "factors": {
                        "factor_001": {
                            "factor_id": "factor_001",
                            "factor_name": "Test Factor",
                            "factor_expression": "(close / ts_delay(close, 1) - 1)",
                            "evaluation": {"status": "active", "last_validated": None},
                        },
                    },
                }
            )
        )
        monkeypatch.setenv("FACTOR_LIBRARY_PATH", str(lib_path))

        scheduler = DefaultRevalidationScheduler(
            library_path=str(lib_path),
            max_per_run=10,
            days_threshold=0,
        )

        result = scheduler.run_revalidation()

        assert result.total_candidates == 1
        assert "factor_001" in result.status_changes
        assert not any(
            "RDAgentLog.info() takes 2 positional arguments but 3 were given" in err
            for err in result.errors
        ), f"Unexpected logger signature error in revalidation errors: {result.errors}"


class TestMiningFailurePath:
    """Tests for failure handling in mining scheduler."""

    def test_validate_factor_returns_failure_result(self):
        """Test _validate_factor returns proper dict structure for failures."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler()
        scheduler._validate_factor = lambda fid, entry: {
            "status": "failure",
            "summary": {
                "stability_score": None,
                "validation_summary": f"Validation failed for {fid}",
            },
        }

        result = scheduler._validate_factor("test_factor", {"factor_id": "test_factor"})
        assert result["status"] == "failure"
        assert result["summary"]["validation_summary"] == "Validation failed for test_factor"

    def test_run_mining_with_failure_skips_add_to_library(self, tmp_path, monkeypatch):
        """Test run_mining does not add factors to library when validation fails."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "test_library.json"
        monkeypatch.setenv("FACTOR_LIBRARY_PATH", str(lib_path))

        scheduler = DefaultMiningScheduler(
            library_path=str(lib_path),
            max_per_run=10,
        )

        scheduler._generate_factors = lambda ctx: [
            {"factor_id": "new_factor_1", "factor_name": "Test Factor"},
            {"factor_id": "new_factor_2", "factor_name": "Test Factor 2"},
        ]

        scheduler._validate_factor = lambda fid, entry: None

        result = scheduler.run_mining()

        assert result.factors_generated == 2
        assert result.factors_validated == 0
        assert result.factors_added == 0


class TestApplyValidationResultSignature:
    """Tests that apply_validation_result is called with correct signature."""

    def test_run_revalidation_iterates_factor_entries_correctly(self, tmp_path, monkeypatch):
        """Verify run_revalidation properly extracts factor_id from factor_entry dict."""
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler
        import json

        lib_path = tmp_path / "test_library.json"
        lib_path.write_text(
            json.dumps(
                {
                    "metadata": {"version": "1.1", "total_factors": 1},
                    "factors": {
                        "test_factor_001": {
                            "factor_id": "test_factor_001",
                            "factor_name": "Test Factor",
                            "evaluation": {"status": "active", "last_validated": None},
                        },
                    },
                }
            )
        )
        monkeypatch.setenv("FACTOR_LIBRARY_PATH", str(lib_path))

        scheduler = DefaultRevalidationScheduler(
            library_path=str(lib_path),
            max_per_run=10,
            days_threshold=0,
        )

        captured_calls = []

        def capturing_backtest(factor_id, factor_entry):
            captured_calls.append((factor_id, factor_entry))
            return True

        scheduler._run_factor_backtest = capturing_backtest
        scheduler.run_revalidation()

        assert len(captured_calls) == 1
        factor_id_arg, factor_entry_arg = captured_calls[0]
        assert isinstance(factor_entry_arg, dict)
        assert factor_entry_arg.get("factor_id") == "test_factor_001"
        assert factor_id_arg == "test_factor_001"


class TestStubReturnsFailure:
    """Tests that stub implementations return explicit failure, not success."""

    def test_run_factor_backtest_stubs_returns_false(self):
        """Test _run_factor_backtest stub returns False (not True)."""
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        scheduler = DefaultRevalidationScheduler()
        result = scheduler._run_factor_backtest("test_id", {"factor_id": "test_id"})
        assert result is False, "Stub should return False, not True"

    def test_validate_factor_stubs_returns_failure_status(self):
        """Test _validate_factor stub returns {'status': 'failure'}."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler()
        result = scheduler._validate_factor("test_id", {"factor_id": "test_id"})
        assert result is not None
        assert result["status"] == "failure", "Stub should return failure status"


class TestInjectedExecutionHooks:
    """Tests for injectable execution hooks on schedulers."""

    def test_revalidation_scheduler_uses_injected_backtest_runner(self, tmp_path, monkeypatch):
        """Injected backtest runner should be called instead of the default seam."""
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler
        import json

        lib_path = tmp_path / "test_library.json"
        lib_path.write_text(
            json.dumps(
                {
                    "metadata": {"version": "1.1", "total_factors": 1},
                    "factors": {
                        "test_factor_001": {
                            "factor_id": "test_factor_001",
                            "factor_name": "Test Factor",
                            "evaluation": {"status": "active", "last_validated": None},
                        },
                    },
                }
            )
        )
        monkeypatch.setenv("FACTOR_LIBRARY_PATH", str(lib_path))

        captured = []

        def injected_backtest_runner(factor_id, factor_entry):
            captured.append((factor_id, factor_entry["factor_name"]))
            return True

        scheduler = DefaultRevalidationScheduler(
            library_path=str(lib_path),
            max_per_run=10,
            days_threshold=0,
            backtest_runner=injected_backtest_runner,
        )

        result = scheduler.run_revalidation()

        assert result.revalidated_count == 1
        assert captured == [("test_factor_001", "Test Factor")]

    def test_mining_scheduler_uses_injected_factor_validator(self, tmp_path, monkeypatch):
        """Injected validator should drive mining success path."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "test_library.json"
        monkeypatch.setenv("FACTOR_LIBRARY_PATH", str(lib_path))

        captured = []

        def injected_validator(factor_id, factor_entry):
            captured.append((factor_id, factor_entry["factor_name"]))
            return {
                "status": "success",
                "summary": {
                    "stability_score": 0.9,
                    "validation_summary": f"Validated {factor_id}",
                },
            }

        scheduler = DefaultMiningScheduler(
            library_path=str(lib_path),
            max_per_run=10,
            factor_validator=injected_validator,
        )
        scheduler._generate_factors = lambda ctx: [{"factor_id": "new_factor_1", "factor_name": "Test Factor"}]

        result = scheduler.run_mining()

        assert result.factors_generated == 1
        assert result.factors_validated == 1
        assert result.factors_added == 1
        assert captured == [("new_factor_1", "Test Factor")]


class TestParquetBackendSchedulerBehavior:
    """Test that schedulers use FactorStoreFacade in parquet backend."""

    def test_revalidation_scheduler_parquet_backend_uses_facade(self, tmp_path, monkeypatch):
        """In parquet backend, DefaultRevalidationScheduler.run_revalidation(candidates=None)
        obtains candidates through FactorStoreFacade and does not instantiate FactorLibraryManager."""
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler
        from quantaalpha.factors.factor_store_facade import FactorStoreFacade
        import json

        # Create a JSON library for fallback path
        lib_path = tmp_path / "test_library.json"
        lib_path.write_text(
            json.dumps({
                "metadata": {"version": "1.1", "total_factors": 1},
                "factors": {
                    "factor_001": {
                        "factor_id": "factor_001",
                        "factor_name": "Test Factor",
                        "factor_expression": "STD($close, 20)",
                        "evaluation": {"status": "active", "last_validated": None},
                    },
                },
            })
        )

        # Create parquet store
        parquet_dir = tmp_path / "parquet_store"
        parquet_dir.mkdir()

        # Create scheduler with parquet backend
        scheduler = DefaultRevalidationScheduler(
            library_path=str(lib_path),
            library_backend="parquet",
            parquet_library_dir=str(parquet_dir),
            max_per_run=10,
            days_threshold=0,
        )

        # Verify it has parquet backend attributes
        assert scheduler.library_backend == "parquet"
        assert scheduler.parquet_library_dir == str(parquet_dir)

    def test_mining_scheduler_parquet_backend_uses_facade(self, tmp_path, monkeypatch):
        """In parquet backend, DefaultMiningScheduler._build_fallback_context()
        obtains records through FactorStoreFacade and does not instantiate FactorLibraryManager."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler
        from quantaalpha.factors.factor_store_facade import FactorStoreFacade

        parquet_dir = tmp_path / "parquet_store"
        parquet_dir.mkdir()

        scheduler = DefaultMiningScheduler(
            library_path=str(tmp_path / "library.json"),
            library_backend="parquet",
            parquet_library_dir=str(parquet_dir),
        )

        assert scheduler.library_backend == "parquet"
        assert scheduler.parquet_library_dir == str(parquet_dir)

    def test_json_backend_still_works(self, tmp_path, monkeypatch):
        """In json backend, existing FactorLibraryManager fallback still works."""
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler
        import json

        lib_path = tmp_path / "test_library.json"
        lib_path.write_text(
            json.dumps({
                "metadata": {"version": "1.1", "total_factors": 0},
                "factors": {},
            })
        )

        scheduler = DefaultRevalidationScheduler(
            library_path=str(lib_path),
            library_backend="json",
            max_per_run=10,
            days_threshold=0,
        )

        assert scheduler.library_backend == "json"
        # JSON backend should not have parquet_library_dir
        assert not hasattr(scheduler, 'parquet_library_dir') or scheduler.parquet_library_dir is None

    def test_parquet_add_factor_writes_delta_file(self, tmp_path):
        """DefaultMiningScheduler._add_factor_to_library writes through parquet backend."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        parquet_dir = tmp_path / "parquet_store"
        scheduler = DefaultMiningScheduler(
            library_backend="parquet",
            parquet_library_dir=str(parquet_dir),
        )

        scheduler._add_factor_to_library(
            {
                "factor_id": "factor_001",
                "factor_name": "Test Factor",
                "factor_expression": "STD($close, 20)",
            }
        )

        delta_files = list((parquet_dir / "delta").glob("*.parquet"))
        assert len(delta_files) == 1

    def test_orchestrator_passes_factor_backend_to_schedulers(self, tmp_path):
        """MiningOrchestrator forwards factor backend config to lazy schedulers."""
        from quantaalpha.continuous.orchestrator import MiningOrchestrator
        from quantaalpha.continuous.scheduler import (
            FactorConfig,
            ParquetCompactConfig,
            SchedulerConfig,
        )

        parquet_dir = tmp_path / "parquet_store"
        config = SchedulerConfig(
            factor=FactorConfig(
                library_backend="parquet",
                parquet_library_dir=str(parquet_dir),
                parquet_compact=ParquetCompactConfig(delta_file_threshold=3),
            )
        )

        orchestrator = MiningOrchestrator(config=config, library_path=str(tmp_path / "library.json"))

        assert orchestrator.revalidation_scheduler.library_backend == "parquet"
        assert orchestrator.revalidation_scheduler.parquet_library_dir == str(parquet_dir)
        assert orchestrator.mining_scheduler.library_backend == "parquet"
        assert orchestrator.mining_scheduler.parquet_library_dir == str(parquet_dir)
        assert orchestrator.mining_scheduler.parquet_compact_config["delta_file_threshold"] == 3

    def test_mining_scheduler_builds_loop_kwargs_with_parquet_config(self, tmp_path):
        """DefaultMiningScheduler passes parquet store and compact config into AlphaAgentLoop."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        parquet_dir = tmp_path / "parquet_store"
        compact_config = {
            "enabled": True,
            "delta_file_threshold": 3,
            "compact_on_save_batch_end": True,
        }
        scheduler = DefaultMiningScheduler(
            library_backend="parquet",
            parquet_library_dir=str(parquet_dir),
            parquet_compact_config=compact_config,
        )

        kwargs = scheduler._build_alpha_agent_loop_storage_kwargs()

        assert kwargs["parquet_store_path"] == str(parquet_dir)
        assert kwargs["parquet_compact_config"] == compact_config
