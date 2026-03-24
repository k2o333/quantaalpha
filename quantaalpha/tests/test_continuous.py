"""
Unit tests for the continuous orchestration module.

Tests cover:
- MiningOrchestrator lifecycle
- SchedulerConfig defaults
- SchedulerEvent enum
- SchedulerContext dataclass
- Default implementations
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


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
        assert "errors" in health
        assert health["status"] == "stopped"

    def test_run_revalidation_not_enabled(self):
        """Test running revalidation when not enabled."""
        from quantaalpha.continuous import MiningOrchestrator, SchedulerConfig

        config = SchedulerConfig(enable_revalidation=False)
        orch = MiningOrchestrator(config)
        result = orch.run_revalidation_cycle()

        assert result.errors == ["Revalidation scheduler not enabled"]

    def test_run_mining_not_enabled(self):
        """Test running mining when not enabled."""
        from quantaalpha.continuous import MiningOrchestrator, SchedulerConfig

        config = SchedulerConfig(enable_mining=False)
        orch = MiningOrchestrator(config)
        result = orch.run_mining_cycle()

        assert result.errors == ["Mining scheduler not enabled"]

    def test_check_data_updates_no_monitor(self):
        """Test checking data updates when monitor not available."""
        from quantaalpha.continuous import MiningOrchestrator, SchedulerConfig

        config = SchedulerConfig(enable_data_monitor=False)
        orch = MiningOrchestrator(config)
        events = orch.check_data_updates()

        assert events == []


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
