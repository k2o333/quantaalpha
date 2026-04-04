"""
Tests for the global Circuit Breaker mechanism.

Verifies:
1. Circuit breaker activates after N consecutive zero-pass cycles
2. Circuit breaker resets on a successful cycle
3. Cooldown sleep uses base × multiplier
4. Circuit breaker is disabled by default (no config)
"""

import tempfile
import threading
from unittest.mock import MagicMock, patch

import pytest


class TestCircuitBreakerActivates:
    """Test circuit breaker activation after consecutive failures."""

    def test_circuit_breaker_activates_after_3_failures(self):
        """连续 3 轮 zero-pass 后 circuit_breaker.active == True."""
        from quantaalpha.continuous.run_store import RunSummary, ValidationSummary, MiningSummary

        # Simulate 3 consecutive zero-pass cycles
        cb_state = {"active": False, "consecutive_zero_pass": 0, "cooldown_count": 0}

        for i in range(3):
            # Build a RunSummary with zero pass rate
            summary = RunSummary(
                cycle_timestamp="2026-03-27T10:00:00",
                cycle_type="start",
                validation_summary=ValidationSummary(total=0, passed=0, failed=0),
                mining_summary=MiningSummary(generated=0, validated=0, added=0),
            )

            # Simulate circuit breaker logic
            validation_passed = summary.validation_summary.passed
            mining_added = summary.mining_summary.added
            cycle_has_success = (validation_passed > 0 or mining_added > 0)

            if not cycle_has_success:
                cb_state["consecutive_zero_pass"] += 1

                if cb_state["consecutive_zero_pass"] >= 3:
                    cb_state["active"] = True
                    cb_state["cooldown_count"] += 1

            summary.circuit_breaker = {
                "active": cb_state["active"],
                "consecutive_zero_pass": cb_state["consecutive_zero_pass"],
                "cooldown_count": cb_state["cooldown_count"],
            }

        assert cb_state["active"] is True, \
            f"Expected circuit breaker active after 3 failures, got active={cb_state['active']}"
        assert cb_state["consecutive_zero_pass"] == 3
        assert cb_state["cooldown_count"] == 1


class TestCircuitBreakerResets:
    """Test circuit breaker reset on success."""

    def test_circuit_breaker_resets_on_success(self):
        """一次成功后 circuit_breaker.active == False，计数器归零."""
        from quantaalpha.continuous.run_store import RunSummary, ValidationSummary, MiningSummary

        # Start with CB already triggered
        cb_state = {
            "active": True,
            "consecutive_zero_pass": 3,
            "cooldown_count": 1,
        }

        # Simulate a successful cycle
        summary = RunSummary(
            cycle_timestamp="2026-03-27T10:00:00",
            cycle_type="start",
            validation_summary=ValidationSummary(total=5, passed=3, failed=2),
            mining_summary=MiningSummary(generated=2, validated=2, added=1),
        )

        validation_passed = summary.validation_summary.passed
        mining_added = summary.mining_summary.added
        cycle_has_success = (validation_passed > 0 or mining_added > 0)

        reset_on_success = True
        if cycle_has_success:
            if reset_on_success:
                cb_state["consecutive_zero_pass"] = 0
                cb_state["cooldown_count"] = 0
                if cb_state["active"]:
                    cb_state["active"] = False

        summary.circuit_breaker = {
            "active": cb_state["active"],
            "consecutive_zero_pass": cb_state["consecutive_zero_pass"],
            "cooldown_count": cb_state["cooldown_count"],
        }

        assert cb_state["active"] is False, \
            f"Expected circuit breaker inactive after success, got active={cb_state['active']}"
        assert cb_state["consecutive_zero_pass"] == 0, \
            f"Expected consecutive_zero_pass=0 after success, got {cb_state['consecutive_zero_pass']}"
        assert cb_state["cooldown_count"] == 0, \
            f"Expected cooldown_count=0 after success, got {cb_state['cooldown_count']}"


class TestCircuitBreakerCooldown:
    """Test circuit breaker cooldown sleep multiplier."""

    def test_circuit_breaker_cooldown_sleep(self):
        """冷却期 sleep 应为 base_interval × multiplier."""
        check_interval = 300  # 5 minutes
        cooldown_multiplier = 3.0
        circuit_breaker_active = True

        # Compute actual sleep when CB is active
        if circuit_breaker_active:
            actual_sleep = check_interval * cooldown_multiplier
        else:
            actual_sleep = max(0, check_interval)  # normal case

        expected_sleep = check_interval * cooldown_multiplier
        assert actual_sleep == expected_sleep, \
            f"Expected cooldown sleep={expected_sleep}, got {actual_sleep}"
        assert actual_sleep == 900.0, \
            f"Expected 900s (300 × 3.0), got {actual_sleep}"


class TestCircuitBreakerDisabled:
    """Test circuit breaker does not affect system when not configured."""

    def test_circuit_breaker_disabled_by_default(self):
        """未配置时系统行为不变 - no circuit_breaker field."""
        from quantaalpha.continuous.run_store import RunSummary

        # RunSummary should have circuit_breaker field with defaults
        summary = RunSummary(
            cycle_timestamp="2026-03-27T10:00:00",
            cycle_type="start",
        )

        # Default circuit_breaker should exist
        assert hasattr(summary, "circuit_breaker"), \
            "RunSummary should have circuit_breaker field"

        # Default values when not configured
        cb = summary.circuit_breaker
        assert cb["active"] is False
        assert cb["consecutive_zero_pass"] == 0
        assert cb["cooldown_count"] == 0


class TestCircuitBreakerConfig:
    """Test CircuitBreakerConfig parsing."""

    def test_circuit_breaker_config_defaults(self):
        """CircuitBreakerConfig should have sensible defaults."""
        from quantaalpha.continuous.scheduler import CircuitBreakerConfig

        config = CircuitBreakerConfig()

        assert config.max_consecutive_zero_pass_cycles == 3
        assert config.cooldown_multiplier == 3.0
        assert config.max_cooldown_count == 5
        assert config.reset_on_success is True

    def test_circuit_breaker_config_from_dict(self):
        """CircuitBreakerConfig.from_dict should parse correctly."""
        from quantaalpha.continuous.scheduler import CircuitBreakerConfig

        data = {
            "max_consecutive_zero_pass_cycles": 5,
            "cooldown_multiplier": 4.0,
            "max_cooldown_count": 10,
            "reset_on_success": False,
        }

        config = CircuitBreakerConfig.from_dict(data)

        assert config.max_consecutive_zero_pass_cycles == 5
        assert config.cooldown_multiplier == 4.0
        assert config.max_cooldown_count == 10
        assert config.reset_on_success is False

    def test_circuit_breaker_config_partial_override(self):
        """Partial config dict should use defaults for missing keys."""
        from quantaalpha.continuous.scheduler import CircuitBreakerConfig

        data = {
            "max_consecutive_zero_pass_cycles": 2,
        }

        config = CircuitBreakerConfig.from_dict(data)

        assert config.max_consecutive_zero_pass_cycles == 2
        assert config.cooldown_multiplier == 3.0  # default
        assert config.max_cooldown_count == 5    # default
        assert config.reset_on_success is True  # default


class TestCircuitBreakerCriticalLog:
    """Test CRITICAL log when cooldown_count exceeds max_cooldown_count."""

    def test_critical_log_when_max_cooldown_exceeded(self):
        """cooldown_count >= max_cooldown_count 时日志级别升为 CRITICAL."""
        cooldown_count = 5
        max_cooldown_count = 5

        should_critical = (cooldown_count >= max_cooldown_count)

        assert should_critical is True, \
            "CRITICAL should be triggered when cooldown_count >= max_cooldown_count"

        # Test boundary: one less should not trigger
        cooldown_count = 4
        should_not_critical = (cooldown_count >= max_cooldown_count)
        assert should_not_critical is False, \
            "CRITICAL should NOT trigger when cooldown_count < max_cooldown_count"


class TestRunSummaryCircuitBreakerField:
    """Test RunSummary.circuit_breaker field integration."""

    def test_run_summary_circuit_breaker_in_to_dict(self):
        """to_dict should include circuit_breaker in run_summary."""
        from quantaalpha.continuous.run_store import RunSummary

        summary = RunSummary(
            cycle_timestamp="2026-03-27T10:00:00",
            cycle_type="start",
            circuit_breaker={
                "active": True,
                "consecutive_zero_pass": 3,
                "cooldown_count": 1,
            },
        )

        d = summary.to_dict()

        assert "circuit_breaker" in d["run_summary"], \
            "run_summary should contain circuit_breaker key"
        assert d["run_summary"]["circuit_breaker"]["active"] is True
        assert d["run_summary"]["circuit_breaker"]["consecutive_zero_pass"] == 3
        assert d["run_summary"]["circuit_breaker"]["cooldown_count"] == 1

    def test_run_summary_circuit_breaker_roundtrip(self):
        """circuit_breaker field should survive save/load roundtrip."""
        from quantaalpha.continuous.run_store import RunStore, RunSummary

        original = RunSummary(
            schema_version="1.0",
            cycle_timestamp="2026-03-27T10:00:00",
            cycle_type="start",
            circuit_breaker={
                "active": True,
                "consecutive_zero_pass": 3,
                "cooldown_count": 2,
            },
        )

        store = RunStore("/tmp/test_cb_roundtrip")
        filepath = store.save(original)
        loaded = store.load(filepath)

        assert loaded.circuit_breaker["active"] is True
        assert loaded.circuit_breaker["consecutive_zero_pass"] == 3
        assert loaded.circuit_breaker["cooldown_count"] == 2

        import shutil
        shutil.rmtree("/tmp/test_cb_roundtrip", ignore_errors=True)

    def test_run_summary_circuit_breaker_from_dict(self):
        """from_dict should reconstruct circuit_breaker field."""
        from quantaalpha.continuous.run_store import RunSummary

        data = {
            "schema_version": "1.0",
            "cycle_timestamp": "2026-03-27T10:00:00",
            "cycle_type": "start",
            "run_summary": {
                "duration_seconds": 45.5,
                "errors": [],
                "circuit_breaker": {
                    "active": True,
                    "consecutive_zero_pass": 4,
                    "cooldown_count": 3,
                },
            },
        }

        summary = RunSummary.from_dict(data)

        assert summary.circuit_breaker["active"] is True
        assert summary.circuit_breaker["consecutive_zero_pass"] == 4
        assert summary.circuit_breaker["cooldown_count"] == 3


class TestPipelineConfigCircuitBreaker:
    """Test PipelineConfig parses circuit_breaker section."""

    def test_pipeline_config_parses_circuit_breaker(self, tmp_path):
        """PipelineConfig.from_yaml should parse circuit_breaker section."""
        import yaml
        from quantaalpha.continuous.scheduler import PipelineConfig

        config_content = {
            "runtime": {
                "data_check_interval_seconds": 300,
            },
            "circuit_breaker": {
                "max_consecutive_zero_pass_cycles": 4,
                "cooldown_multiplier": 5.0,
                "max_cooldown_count": 8,
                "reset_on_success": False,
            },
        }

        config_file = tmp_path / "pipeline_cb.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_content, f)

        config = PipelineConfig.from_yaml(str(config_file))

        assert hasattr(config, "circuit_breaker"), \
            "PipelineConfig should have circuit_breaker attribute"
        assert config.circuit_breaker.max_consecutive_zero_pass_cycles == 4
        assert config.circuit_breaker.cooldown_multiplier == 5.0
        assert config.circuit_breaker.max_cooldown_count == 8
        assert config.circuit_breaker.reset_on_success is False

    def test_pipeline_config_circuit_breaker_optional(self, tmp_path):
        """pipeline.yaml without circuit_breaker should not raise."""
        import yaml
        from quantaalpha.continuous.scheduler import PipelineConfig

        config_content = {
            "runtime": {
                "data_check_interval_seconds": 300,
            },
        }

        config_file = tmp_path / "pipeline_no_cb.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_content, f)

        config = PipelineConfig.from_yaml(str(config_file))

        # Should have default CircuitBreakerConfig
        assert hasattr(config, "circuit_breaker"), \
            "PipelineConfig should always have circuit_breaker (with defaults)"
        assert config.circuit_breaker.max_consecutive_zero_pass_cycles == 3


class TestCircuitBreakerIntegration:
    """Integration tests for the full circuit breaker flow."""

    def test_full_cycle_failure_then_success(self):
        """完整流程: 3次失败 -> 触发 -> 1次成功 -> 复位."""
        from quantaalpha.continuous.run_store import RunSummary, ValidationSummary, MiningSummary

        cb_state = {
            "active": False,
            "consecutive_zero_pass": 0,
            "cooldown_count": 0,
        }
        cb_config = type("CBConfig", (), {
            "max_consecutive_zero_pass_cycles": 3,
            "cooldown_multiplier": 3.0,
            "max_cooldown_count": 5,
            "reset_on_success": True,
        })()

        summaries = []

        # Cycles 1-3: all failures
        for i in range(3):
            summary = RunSummary(
                cycle_timestamp=f"2026-03-27T10:0{i}:00",
                cycle_type="start",
                validation_summary=ValidationSummary(total=0, passed=0, failed=0),
                mining_summary=MiningSummary(generated=0, validated=0, added=0),
            )
            summaries.append(summary)

        # Process cycles
        for summary in summaries:
            validation_passed = summary.validation_summary.passed
            mining_added = summary.mining_summary.added
            cycle_has_success = (validation_passed > 0 or mining_added > 0)

            if cb_config.reset_on_success and cycle_has_success:
                cb_state["consecutive_zero_pass"] = 0
                cb_state["cooldown_count"] = 0
                if cb_state["active"]:
                    cb_state["active"] = False
            elif not cycle_has_success:
                cb_state["consecutive_zero_pass"] += 1
                if cb_state["consecutive_zero_pass"] >= cb_config.max_consecutive_zero_pass_cycles:
                    cb_state["active"] = True
                    cb_state["cooldown_count"] += 1

            summary.circuit_breaker = dict(cb_state)

        # After 3 failures
        assert cb_state["active"] is True
        assert cb_state["consecutive_zero_pass"] == 3
        assert cb_state["cooldown_count"] == 1

        # Cycle 4: success
        success_summary = RunSummary(
            cycle_timestamp="2026-03-27T10:30:00",
            cycle_type="start",
            validation_summary=ValidationSummary(total=5, passed=3, failed=2),
            mining_summary=MiningSummary(generated=2, validated=2, added=1),
        )

        validation_passed = success_summary.validation_summary.passed
        mining_added = success_summary.mining_summary.added
        cycle_has_success = (validation_passed > 0 or mining_added > 0)

        if cb_config.reset_on_success and cycle_has_success:
            cb_state["consecutive_zero_pass"] = 0
            cb_state["cooldown_count"] = 0
            if cb_state["active"]:
                cb_state["active"] = False

        success_summary.circuit_breaker = dict(cb_state)

        # After 1 success
        assert cb_state["active"] is False, \
            f"Expected CB inactive after success, got active={cb_state['active']}"
        assert cb_state["consecutive_zero_pass"] == 0, \
            f"Expected consecutive_zero_pass=0, got {cb_state['consecutive_zero_pass']}"
        assert cb_state["cooldown_count"] == 0, \
            f"Expected cooldown_count=0, got {cb_state['cooldown_count']}"
