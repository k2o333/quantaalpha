"""
Tests for DataFrame cache cross-stage reuse in ContinuousOrchestrator.

These tests verify that the DataFrame cache is only invalidated when data
actually advances, not unconditionally at the start of every cycle.
"""

import math
from unittest.mock import MagicMock, patch

import pytest


class TestDataFrameCacheInvalidation:
    """Tests for DataFrame cache invalidation logic in run_once_cycle."""

    def _make_orchestrator(self, tmp_path, bridge_enabled=True, interfaces=None):
        """Create a ContinuousOrchestrator with mocked bridge."""
        from quantaalpha.continuous.main import ContinuousOrchestrator
        from quantaalpha.continuous.scheduler import PipelineConfig

        config = PipelineConfig(
            enable_data_monitor=False,
            enable_revalidation=True,
            enable_mining=False,
            cycle_budget_seconds=300,
        )
        config.validation = MagicMock()
        config.validation.max_revalidation_per_run = 10
        config.validation.max_mining_per_run = 5
        config.factor = MagicMock()
        config.factor.library_path = str(tmp_path / "lib.json")
        config.app4_bridge.enabled = bridge_enabled
        config.app4_bridge.interfaces = interfaces or ["daily"]

        return config, ContinuousOrchestrator

    def test_cache_preserved_when_no_data_update(self, tmp_path):
        """
        RED TEST: When data update completes but no interfaces advanced,
        the cache should NOT be invalidated.

        Current behavior: run_once_cycle() calls _clear_runtime_caches()
        unconditionally at line 623, so cache is always cleared.
        Expected: cache_invalidated should be False when advanced_interfaces is [].
        """
        from quantaalpha.continuous.main import ContinuousOrchestrator
        from quantaalpha.continuous.scheduler import PipelineConfig

        config = PipelineConfig(
            enable_data_monitor=False,
            enable_revalidation=True,
            enable_mining=False,
            cycle_budget_seconds=300,
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
            mock_bridge.inspect = MagicMock(return_value=mock_inspection)
            mock_bridge.should_update = MagicMock(return_value=True)
            mock_bridge._last_inspection = mock_inspection
            # Simulate update that completed but did NOT advance data
            mock_bridge.run_update = MagicMock(return_value={
                "updated": True,
                "updated_interfaces": ["daily"],
                "advanced_interfaces": [],  # No data advancement
                "unchanged_after_update": ["daily"],
                "freshness_delta": {},
                "errors": [],
            })
            mock_create.return_value = mock_bridge

            orchestrator = ContinuousOrchestrator(config)

            # Mock the base orchestrator's revalidation to avoid full cycle
            mock_reval_result = MagicMock()
            mock_reval_result.total_candidates = 0
            mock_reval_result.revalidated_count = 0
            mock_reval_result.errors = []
            mock_reval_result.impact_groups = []
            mock_reval_result.candidate_factors = None
            mock_reval_result.candidate_factors_source = ""
            orchestrator._orchestrator.run_revalidation_cycle = MagicMock(
                return_value=mock_reval_result
            )

            # Track whether _clear_runtime_caches was called
            clear_call_count = 0
            original_clear = orchestrator._clear_runtime_caches
            def track_clear():
                nonlocal clear_call_count
                clear_call_count += 1
                return original_clear()
            orchestrator._clear_runtime_caches = track_clear

            result = orchestrator.run_once_cycle()

            # The key assertion: when advanced_interfaces is empty,
            # cache should NOT have been invalidated
            assert result.get("cache_invalidated") is False, (
                f"cache_invalidated should be False when advanced_interfaces=[], "
                f"but got {result.get('cache_invalidated')}. "
                f"_clear_runtime_caches was called {clear_call_count} times."
            )

    def test_cache_invalidated_on_data_advance(self, tmp_path):
        """
        GREEN TEST: When data update reports advanced_interfaces,
        the cache should be invalidated.
        """
        from quantaalpha.continuous.main import ContinuousOrchestrator
        from quantaalpha.continuous.scheduler import PipelineConfig

        config = PipelineConfig(
            enable_data_monitor=False,
            enable_revalidation=True,
            enable_mining=False,
            cycle_budget_seconds=300,
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
            mock_bridge.inspect = MagicMock(return_value=mock_inspection)
            mock_bridge.should_update = MagicMock(return_value=True)
            mock_bridge._last_inspection = mock_inspection
            # Simulate update that DID advance data
            mock_bridge.run_update = MagicMock(return_value={
                "updated": True,
                "updated_interfaces": ["daily"],
                "advanced_interfaces": ["daily"],  # Data advanced
                "unchanged_after_update": [],
                "freshness_delta": {"daily": "20260328"},
                "errors": [],
            })
            mock_create.return_value = mock_bridge

            orchestrator = ContinuousOrchestrator(config)

            mock_reval_result = MagicMock()
            mock_reval_result.total_candidates = 0
            mock_reval_result.revalidated_count = 0
            mock_reval_result.errors = []
            mock_reval_result.impact_groups = []
            mock_reval_result.candidate_factors = None
            mock_reval_result.candidate_factors_source = ""
            orchestrator._orchestrator.run_revalidation_cycle = MagicMock(
                return_value=mock_reval_result
            )

            clear_call_count = 0
            original_clear = orchestrator._clear_runtime_caches
            def track_clear():
                nonlocal clear_call_count
                clear_call_count += 1
                return original_clear()
            orchestrator._clear_runtime_caches = track_clear

            result = orchestrator.run_once_cycle()

            assert result.get("cache_invalidated") is True, (
                f"cache_invalidated should be True when advanced_interfaces=['daily'], "
                f"but got {result.get('cache_invalidated')}. "
                f"_clear_runtime_caches was called {clear_call_count} times."
            )

    def test_cache_invalidated_on_exception(self, tmp_path):
        """
        GREEN TEST: When data inspection raises an exception,
        the cache should be invalidated as a safety fallback.
        """
        from quantaalpha.continuous.main import ContinuousOrchestrator
        from quantaalpha.continuous.scheduler import PipelineConfig

        config = PipelineConfig(
            enable_data_monitor=False,
            enable_revalidation=True,
            enable_mining=False,
            cycle_budget_seconds=300,
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
            # Simulate inspect raising an exception
            mock_bridge.inspect = MagicMock(side_effect=RuntimeError("Bridge inspection failed"))
            mock_bridge._last_inspection = None
            mock_create.return_value = mock_bridge

            orchestrator = ContinuousOrchestrator(config)

            mock_reval_result = MagicMock()
            mock_reval_result.total_candidates = 0
            mock_reval_result.revalidated_count = 0
            mock_reval_result.errors = []
            mock_reval_result.impact_groups = []
            mock_reval_result.candidate_factors = None
            mock_reval_result.candidate_factors_source = ""
            orchestrator._orchestrator.run_revalidation_cycle = MagicMock(
                return_value=mock_reval_result
            )

            clear_call_count = 0
            original_clear = orchestrator._clear_runtime_caches
            def track_clear():
                nonlocal clear_call_count
                clear_call_count += 1
                return original_clear()
            orchestrator._clear_runtime_caches = track_clear

            result = orchestrator.run_once_cycle()

            # On exception, cache should be invalidated for safety
            assert result.get("cache_invalidated") is True, (
                f"cache_invalidated should be True on data exception, "
                f"but got {result.get('cache_invalidated')}. "
                f"_clear_runtime_caches was called {clear_call_count} times."
            )
            assert "data_inspection" in str(result.get("errors", [])), (
                "Expected data_inspection error in result"
            )

    def test_result_contains_cache_invalidated_key(self, tmp_path):
        """
        GREEN TEST: run_once_cycle result should contain cache_invalidated key.
        """
        from quantaalpha.continuous.main import ContinuousOrchestrator
        from quantaalpha.continuous.scheduler import PipelineConfig

        config = PipelineConfig(
            enable_data_monitor=False,
            enable_revalidation=True,
            enable_mining=False,
            cycle_budget_seconds=300,
        )
        config.validation = MagicMock()
        config.validation.max_revalidation_per_run = 10
        config.validation.max_mining_per_run = 5
        config.factor = MagicMock()
        config.factor.library_path = str(tmp_path / "lib.json")
        config.app4_bridge.enabled = False  # No bridge - no data update

        orchestrator = ContinuousOrchestrator(config)

        mock_reval_result = MagicMock()
        mock_reval_result.total_candidates = 0
        mock_reval_result.revalidated_count = 0
        mock_reval_result.errors = []
        mock_reval_result.impact_groups = []
        mock_reval_result.candidate_factors = None
        mock_reval_result.candidate_factors_source = ""
        orchestrator._orchestrator.run_revalidation_cycle = MagicMock(
            return_value=mock_reval_result
        )

        result = orchestrator.run_once_cycle()

        assert "cache_invalidated" in result, (
            f"result should contain 'cache_invalidated' key, "
            f"but got keys: {list(result.keys())}"
        )
