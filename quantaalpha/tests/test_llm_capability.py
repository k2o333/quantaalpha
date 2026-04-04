"""Tests for capability-aware model routing."""

from unittest.mock import MagicMock, patch

import pytest


class TestCapabilityAwareRouting:
    """Tests for get_model_for_task with required_capabilities."""

    def _make_backend_with_pool(self):
        from quantaalpha.llm.client import APIBackend
        from quantaalpha.llm.provider_pool import ProviderPool

        backend = object.__new__(APIBackend)
        backend.chat_model = "gpt-4-turbo"
        backend.reasoning_model = ""
        backend.task_model_map = {}
        backend.routing_default = ""
        backend.chat_model_map = {}

        pool = ProviderPool()
        pool.add_provider("gpt4", api_keys=["k1"], model="gpt-4-turbo", tags=["tool_calling", "structured", "general"], tier=3)
        pool.add_provider("gpt35", api_keys=["k2"], model="gpt-3.5-turbo", tags=["general"], tier=1)
        pool.add_provider("claude", api_keys=["k3"], model="claude-3-sonnet", tags=["tool_calling", "reasoning", "general"], tier=3)
        backend._provider_pool = pool

        return backend

    def test_get_model_for_task_with_required_capabilities(self):
        """Returns model matching required capabilities."""
        backend = self._make_backend_with_pool()

        model = backend.get_model_for_task(
            required_capabilities=["tool_calling"],
            max_tier=3,
        )
        # Should return cheapest matching model
        assert model in ["gpt-4-turbo", "claude-3-sonnet"]

    def test_get_model_for_task_prefers_lower_tier(self):
        """When multiple models match, prefers lower tier."""
        backend = self._make_backend_with_pool()

        model = backend.get_model_for_task(
            required_capabilities=["general"],
            max_tier=2,
        )
        assert model == "gpt-3.5-turbo"

    def test_get_model_for_task_fallbacks_on_no_match(self):
        """Falls back to chat_model when no provider matches."""
        backend = self._make_backend_with_pool()

        with patch("quantaalpha.llm.client.logger") as mock_logger:
            model = backend.get_model_for_task(
                required_capabilities=["nonexistent"],
                max_tier=3,
            )
            assert model == "gpt-4-turbo"
            mock_logger.warning.assert_called_once()

    def test_get_model_for_task_without_capabilities(self):
        """Without required_capabilities, uses existing routing logic."""
        backend = self._make_backend_with_pool()

        model = backend.get_model_for_task()
        assert model == "gpt-4-turbo"
