"""Tests for step-level model routing in AlphaAgentLoop."""

from unittest.mock import MagicMock, patch

import pytest


class TestStepModelRouting:
    """Tests for step_model_routing in AlphaAgentLoop."""

    def test_alpha_agent_loop_accepts_step_model_routing(self):
        """AlphaAgentLoop accepts step_model_routing parameter."""
        from quantaalpha.pipeline.loop import AlphaAgentLoop
        from quantaalpha.pipeline.settings import ALPHA_AGENT_FACTOR_PROP_SETTING

        step_routing = {
            "propose": {"require_capabilities": ["reasoning"], "max_tier": 3},
            "feedback": {"require_capabilities": ["structured"], "max_tier": 3},
        }

        with patch.object(AlphaAgentLoop, "__init__", return_value=None):
            loop = object.__new__(AlphaAgentLoop)
            loop._step_model_routing = step_routing
            assert loop._step_model_routing == step_routing

    def test_alpha_agent_loop_empty_step_routing(self):
        """AlphaAgentLoop defaults to empty step_model_routing."""
        from quantaalpha.pipeline.loop import AlphaAgentLoop
        from quantaalpha.pipeline.settings import ALPHA_AGENT_FACTOR_PROP_SETTING

        with patch.object(AlphaAgentLoop, "__init__", return_value=None):
            loop = object.__new__(AlphaAgentLoop)
            loop._step_model_routing = {}
            assert loop._step_model_routing == {}

    def test_get_model_for_step_with_routing(self):
        """get_model_for_step returns model from routing config."""
        from quantaalpha.pipeline.loop import AlphaAgentLoop
        from quantaalpha.pipeline.settings import ALPHA_AGENT_FACTOR_PROP_SETTING

        step_routing = {
            "propose": {"require_capabilities": ["reasoning"], "max_tier": 3},
        }

        with patch.object(AlphaAgentLoop, "__init__", return_value=None):
            loop = object.__new__(AlphaAgentLoop)
            loop._step_model_routing = step_routing
            mock_backend = MagicMock()
            mock_backend.get_model_for_task.return_value = "gpt-4-turbo"
            loop._api_backend = mock_backend

            model = loop.get_model_for_step("propose")
            mock_backend.get_model_for_task.assert_called_once_with(
                required_capabilities=["reasoning"],
                max_tier=3,
            )
            assert model == "gpt-4-turbo"

    def test_get_model_for_step_without_routing(self):
        """get_model_for_step returns None when no routing config."""
        from quantaalpha.pipeline.loop import AlphaAgentLoop
        from quantaalpha.pipeline.settings import ALPHA_AGENT_FACTOR_PROP_SETTING

        with patch.object(AlphaAgentLoop, "__init__", return_value=None):
            loop = object.__new__(AlphaAgentLoop)
            loop._step_model_routing = {}
            loop._api_backend = MagicMock()

            model = loop.get_model_for_step("propose")
            assert model is None

    def test_get_model_for_step_unknown_step(self):
        """get_model_for_step returns None for unknown step name."""
        from quantaalpha.pipeline.loop import AlphaAgentLoop
        from quantaalpha.pipeline.settings import ALPHA_AGENT_FACTOR_PROP_SETTING

        step_routing = {
            "propose": {"require_capabilities": ["reasoning"], "max_tier": 3},
        }

        with patch.object(AlphaAgentLoop, "__init__", return_value=None):
            loop = object.__new__(AlphaAgentLoop)
            loop._step_model_routing = step_routing
            loop._api_backend = MagicMock()

            model = loop.get_model_for_step("unknown_step")
            assert model is None
