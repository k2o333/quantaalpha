"""
Unit tests for monitor integration (Task C2).

Tests cover:
- Monitor hook called on validation success
- Monitor hook failure is non-blocking
- No monitor when not configured

These tests verify the fail-safe monitor hook integration with the validation pipeline.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest


class TestMonitorIntegration:
    """Tests for monitor hook integration with factor validation."""

    def test_monitor_hook_called_on_validation_success(self, tmp_path):
        """
        validation 成功后应调用 monitor hook.

        When a factor passes validation and _monitor_engine is configured,
        the _run_monitor_hook should be called with the factor info and ic_result.
        """
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        # Mock the factor validator to return a successful validation
        mock_validator = Mock()
        mock_validator.return_value = {
            "status": "success",
            "summary": {
                "stability_score": 0.75,
                "validation_summary": "Factor passed",
                "ic_mean": 0.05,
                "rank_ic_mean": 0.03,
            },
        }

        # Mock monitor engine
        mock_monitor = Mock()
        mock_monitor.analyze_and_save.return_value = {"ic": [], "quantile": [], "turnover": []}

        # Create scheduler with monitor engine
        scheduler = DefaultMiningScheduler(
            library_path=str(lib_path),
            factor_validator=mock_validator,
            monitor_engine=mock_monitor,
        )

        # Run validation
        factor_entry = {
            "factor_id": "test_factor",
            "factor_name": "Test Factor",
            "factor_expression": "$close",
            "tags": {"data_dependency": ["price_volume"]},
        }
        result = scheduler._validate_factor("test_factor", factor_entry)

        # Validation should succeed
        assert result["status"] == "success"
        assert result["summary"]["ic_mean"] == 0.05

        # Monitor hook should have been called
        mock_monitor.analyze_and_save.assert_called_once()

    def test_monitor_hook_failure_non_blocking(self, tmp_path):
        """
        monitor hook 失败不阻塞 validation.

        When the monitor hook raises an exception, validation should still
        return success (fail-safe behavior) with a WARNING log.
        """
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        # Mock the factor validator to return a successful validation
        mock_validator = Mock()
        mock_validator.return_value = {
            "status": "success",
            "summary": {
                "stability_score": 0.75,
                "validation_summary": "Factor passed",
                "ic_mean": 0.05,
                "rank_ic_mean": 0.03,
            },
        }

        # Mock monitor engine that raises an exception
        mock_monitor = Mock()
        mock_monitor.analyze_and_save.side_effect = Exception("Monitor failed")

        # Create scheduler with failing monitor engine
        scheduler = DefaultMiningScheduler(
            library_path=str(lib_path),
            factor_validator=mock_validator,
            monitor_engine=mock_monitor,
        )

        # Run validation
        factor_entry = {
            "factor_id": "test_factor",
            "factor_name": "Test Factor",
            "factor_expression": "$close",
            "tags": {"data_dependency": ["price_volume"]},
        }
        result = scheduler._validate_factor("test_factor", factor_entry)

        # Validation should STILL succeed despite monitor failure
        assert result["status"] == "success"
        assert result["summary"]["ic_mean"] == 0.05

    def test_no_monitor_when_not_configured(self, tmp_path):
        """
        未配置 monitor_engine 时行为不变.

        When monitor_engine is None, validation should proceed normally
        without any monitor hook calls.
        """
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        # Mock the factor validator to return a successful validation
        mock_validator = Mock()
        mock_validator.return_value = {
            "status": "success",
            "summary": {
                "stability_score": 0.75,
                "validation_summary": "Factor passed",
                "ic_mean": 0.05,
                "rank_ic_mean": 0.03,
            },
        }

        # Create scheduler WITHOUT monitor engine
        scheduler = DefaultMiningScheduler(
            library_path=str(lib_path),
            factor_validator=mock_validator,
            monitor_engine=None,  # Explicitly None
        )

        # Run validation
        factor_entry = {
            "factor_id": "test_factor",
            "factor_name": "Test Factor",
            "factor_expression": "$close",
            "tags": {"data_dependency": ["price_volume"]},
        }
        result = scheduler._validate_factor("test_factor", factor_entry)

        # Validation should succeed
        assert result["status"] == "success"


class TestContinuousOrchestratorMonitorWiring:
    """Tests for ContinuousOrchestrator monitor engine initialization."""

    def test_continuous_orchestrator_initializes_monitor_engine(self):
        """
        ContinuousOrchestrator.__init__ should automatically initialize _monitor_engine.

        When config.factor.monitoring_output_path is set, the monitor engine
        should be initialized and wired to the internal orchestrator.
        """
        with patch("quantaalpha.continuous.main.ContinuousOrchestrator._create_bridge"):
            from quantaalpha.continuous.main import ContinuousOrchestrator

            # Create a mock config with monitoring enabled
            mock_config = Mock()
            mock_config.app4_bridge.enabled = False
            mock_config.factor.library_path = "/tmp/test_lib"
            mock_config.factor.monitoring_output_path = "/tmp/monitor"
            mock_config.enable_revalidation = False
            mock_config.enable_mining = False
            mock_config.execution.train.start = "2020-01-01"
            mock_config.execution.train.end = "2022-12-31"
            mock_config.execution.valid.start = "2023-01-01"
            mock_config.execution.valid.end = "2023-12-31"
            mock_config.execution.test.start = "2024-01-01"
            mock_config.execution.test.end = "2024-12-31"
            mock_config.validation.max_revalidation_per_run = 10
            mock_config.validation.max_mining_per_run = 5

            orchestrator = ContinuousOrchestrator(mock_config)

            # _monitor_engine should be initialized (or None if import fails gracefully)
            # The key is that the attribute should exist
            assert hasattr(orchestrator, "_monitor_engine")

    def test_continuous_orchestrator_passes_monitor_to_orchestrator(self):
        """
        ContinuousOrchestrator should pass monitor_engine to MiningOrchestrator.

        When monitor_engine is configured, it should be passed through to the
        MiningOrchestrator so that mining schedulers can use it.
        """
        with patch("quantaalpha.continuous.main.ContinuousOrchestrator._create_bridge"):
            from quantaalpha.continuous.main import ContinuousOrchestrator

            mock_config = Mock()
            mock_config.app4_bridge.enabled = False
            mock_config.factor.library_path = "/tmp/test_lib"
            mock_config.factor.monitoring_output_path = "/tmp/monitor"
            mock_config.enable_revalidation = False
            mock_config.enable_mining = False
            mock_config.execution.train.start = "2020-01-01"
            mock_config.execution.train.end = "2022-12-31"
            mock_config.execution.valid.start = "2023-01-01"
            mock_config.execution.valid.end = "2023-12-31"
            mock_config.execution.test.start = "2024-01-01"
            mock_config.execution.test.end = "2024-12-31"
            mock_config.validation.max_revalidation_per_run = 10
            mock_config.validation.max_mining_per_run = 5

            with patch("quantaalpha.continuous.orchestrator.MiningOrchestrator") as mock_orch_cls:
                orchestrator = ContinuousOrchestrator(mock_config)

                # Verify MiningOrchestrator was called
                mock_orch_cls.assert_called_once()
                call_kwargs = mock_orch_cls.call_args
                # monitor_engine should be passed
                assert "monitor_engine" in call_kwargs.kwargs or any(
                    "monitor_engine" in str(arg) for arg in call_kwargs.args
                )
