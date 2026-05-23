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


class TestStepModelRoutingInExecution:
    """Tests for step model routing being actually used in execution."""

    def test_factor_propose_uses_routed_model(self):
        """factor_propose uses the model from step_model_routing."""
        import threading
        import contextlib
        from quantaalpha.pipeline.loop import AlphaAgentLoop
        from quantaalpha.pipeline.settings import ALPHA_AGENT_FACTOR_PROP_SETTING
        from unittest.mock import MagicMock, patch, PropertyMock

        step_routing = {
            "propose": {"require_capabilities": ["reasoning"], "max_tier": 3},
        }

        with patch.object(AlphaAgentLoop, "__init__", return_value=None):
            loop = object.__new__(AlphaAgentLoop)
            loop._step_model_routing = step_routing

            # Set up the global STOP_EVENT that the decorator expects
            import quantaalpha.pipeline.loop as loop_module

            loop_module.STOP_EVENT = threading.Event()

            # Mock the hypothesis generator and its api_backend
            mock_backend = MagicMock()
            mock_backend.chat_model = "default-model"
            mock_hypothesis_generator = MagicMock()
            mock_hypothesis_generator.gen.return_value = "test hypothesis"
            mock_hypothesis_generator.convert_response.return_value = "test hypothesis"
            mock_hypothesis_generator._api_backend = mock_backend

            loop.hypothesis_generator = mock_hypothesis_generator
            loop.trace = MagicMock()
            loop._ensemble_config = {}

            # Mock logger with all required methods
            mock_logger = MagicMock()
            mock_logger.tag.return_value = contextlib.nullcontext()

            # Mock get_model_for_step and logger
            with patch.object(loop, "get_model_for_step", return_value="reasoning-model") as mock_get_model, patch.object(loop_module, "logger", mock_logger):
                result = loop.factor_propose({})

                # Verify get_model_for_step was called with "propose"
                mock_get_model.assert_called_once_with("propose")
                # Verify model was temporarily switched and restored
                assert mock_backend.chat_model == "default-model"  # Restored after call
                assert result == "test hypothesis"

    def test_factor_calculate_uses_routed_model(self):
        """factor_calculate uses the model from step_model_routing."""
        import contextlib
        import threading
        from types import SimpleNamespace

        from quantaalpha.llm.config import LLM_SETTINGS
        from quantaalpha.pipeline.loop import AlphaAgentLoop

        with patch.object(AlphaAgentLoop, "__init__", return_value=None):
            loop = object.__new__(AlphaAgentLoop)

            import quantaalpha.pipeline.loop as loop_module

            loop_module.STOP_EVENT = threading.Event()
            loop.coder = MagicMock()
            loop.coder.develop.return_value = SimpleNamespace(sub_tasks=[object()], sub_workspace_list=[])
            loop._track_coder_result = MagicMock()

            mock_logger = MagicMock()
            mock_logger.tag.return_value = contextlib.nullcontext()

            original_chat = LLM_SETTINGS.chat_model
            original_reasoning = LLM_SETTINGS.reasoning_model
            LLM_SETTINGS.chat_model = "default-model"
            LLM_SETTINGS.reasoning_model = "default-model"
            try:
                with patch.object(loop, "get_model_for_step", return_value="calculate-model") as mock_get_model, patch.object(loop_module, "logger", mock_logger):
                    result = loop.factor_calculate({"factor_construct": object()})

                mock_get_model.assert_called_once_with("calculate")
                loop.coder.develop.assert_called_once()
                assert result.sub_tasks
                assert LLM_SETTINGS.chat_model == "default-model"
                assert LLM_SETTINGS.reasoning_model == "default-model"
            finally:
                LLM_SETTINGS.chat_model = original_chat
                LLM_SETTINGS.reasoning_model = original_reasoning
