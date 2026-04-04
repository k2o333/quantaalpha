"""Tests for Tool Calling support in APIBackend."""

from unittest.mock import MagicMock, patch

import pytest


class TestToolCallingSupport:
    """Tests for tools/tool_choice parameters in chat completion."""

    def _make_backend(self):
        """Create a minimal APIBackend mock for testing."""
        from quantaalpha.llm.client import APIBackend

        backend = object.__new__(APIBackend)
        backend.use_azure = False
        backend.use_llama2 = False
        backend.use_gcr_endpoint = False
        backend.chat_stream = False
        backend.use_chat_cache = False
        backend.chat_model = "gpt-4-turbo"
        backend.reasoning_model = ""
        backend.chat_client = MagicMock()
        backend.cache = MagicMock()
        backend.cache.chat_get.return_value = None
        backend.task_model_map = {}
        backend.routing_default = ""
        backend.chat_model_map = {}
        backend.chat_api_key = "test"
        backend.base_url = None
        backend.embedding_api_key = ""
        backend.embedding_base_url = None
        backend.encoder = None
        backend.chat_seed = None
        backend.retry_wait_seconds = 1
        backend.dump_chat_cache = False
        return backend

    def _run_completion(self, backend, messages, **kwargs):
        """Helper to run completion with LLM_SETTINGS patched."""
        with patch("quantaalpha.llm.client.LLM_SETTINGS") as mock_settings:
            mock_settings.log_llm_chat_content = False
            mock_settings.use_auto_chat_cache_seed_gen = False
            return backend._create_chat_completion_inner_function(
                messages=messages,
                reasoning_flag=False,
                **kwargs,
            )

    def test_create_chat_completion_accepts_tools_param(self):
        """_create_chat_completion_inner_function passes tools to OpenAI SDK."""
        backend = self._make_backend()

        tools = [{"type": "function", "function": {"name": "test_tool"}}]

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "test response"
        mock_response.choices[0].finish_reason = "stop"
        backend.chat_client.chat.completions.create.return_value = mock_response

        messages = [{"role": "user", "content": "hello"}]
        result = self._run_completion(backend, messages, tools=tools)

        call_kwargs = backend.chat_client.chat.completions.create.call_args[1]
        assert "tools" in call_kwargs
        assert call_kwargs["tools"] == tools
        assert result[0] == "test response"
        assert result[1] == "stop"

    def test_create_chat_completion_accepts_tool_choice(self):
        """_create_chat_completion_inner_function passes tool_choice to OpenAI SDK."""
        backend = self._make_backend()

        tools = [{"type": "function", "function": {"name": "test_tool"}}]

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "test response"
        mock_response.choices[0].finish_reason = "stop"
        backend.chat_client.chat.completions.create.return_value = mock_response

        messages = [{"role": "user", "content": "hello"}]
        self._run_completion(backend, messages, tools=tools, tool_choice="auto")

        call_kwargs = backend.chat_client.chat.completions.create.call_args[1]
        assert call_kwargs["tool_choice"] == "auto"

    def test_create_chat_completion_tools_none_by_default(self):
        """When tools=None, no tools param is passed (backward compat)."""
        backend = self._make_backend()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "response"
        mock_response.choices[0].finish_reason = "stop"
        backend.chat_client.chat.completions.create.return_value = mock_response

        messages = [{"role": "user", "content": "hello"}]
        self._run_completion(backend, messages)

        call_kwargs = backend.chat_client.chat.completions.create.call_args[1]
        assert "tools" not in call_kwargs


class TestToolCallResponseParsing:
    """Tests for parsing tool_calls from OpenAI response."""

    def _make_backend(self):
        from quantaalpha.llm.client import APIBackend

        backend = object.__new__(APIBackend)
        backend.use_azure = False
        backend.use_llama2 = False
        backend.use_gcr_endpoint = False
        backend.chat_stream = False
        backend.use_chat_cache = False
        backend.chat_model = "gpt-4-turbo"
        backend.reasoning_model = ""
        backend.chat_client = MagicMock()
        backend.cache = MagicMock()
        backend.cache.chat_get.return_value = None
        backend.task_model_map = {}
        backend.routing_default = ""
        backend.chat_model_map = {}
        backend.chat_api_key = "test"
        backend.base_url = None
        backend.embedding_api_key = ""
        backend.embedding_base_url = None
        backend.encoder = None
        backend.chat_seed = None
        backend.retry_wait_seconds = 1
        backend.dump_chat_cache = False
        return backend

    def _run_completion(self, backend, messages, **kwargs):
        """Helper to run completion with LLM_SETTINGS patched."""
        with patch("quantaalpha.llm.client.LLM_SETTINGS") as mock_settings:
            mock_settings.log_llm_chat_content = False
            mock_settings.use_auto_chat_cache_seed_gen = False
            return backend._create_chat_completion_inner_function(
                messages=messages,
                reasoning_flag=False,
                **kwargs,
            )

    def test_parse_tool_calls_from_response(self):
        """When finish_reason is tool_calls, extract tool_calls list."""
        backend = self._make_backend()

        tool_call_mock = MagicMock()
        tool_call_mock.id = "call_abc123"
        tool_call_mock.function.name = "propose_factors"
        tool_call_mock.function.arguments = '{"factors": [{"factor_name": "test", "factor_expression": "ts_mean(close, 5)"}]}'

        message_mock = MagicMock()
        message_mock.content = None
        message_mock.tool_calls = [tool_call_mock]

        choice_mock = MagicMock()
        choice_mock.message = message_mock
        choice_mock.finish_reason = "tool_calls"

        mock_response = MagicMock()
        mock_response.choices = [choice_mock]
        backend.chat_client.chat.completions.create.return_value = mock_response

        messages = [{"role": "user", "content": "propose factors"}]
        tools = [{"type": "function", "function": {"name": "propose_factors"}}]

        result = self._run_completion(backend, messages, tools=tools)

        assert result[1] == "tool_calls"
        assert result[2] is not None
        assert len(result[2]) == 1
        assert result[2][0]["id"] == "call_abc123"
        assert result[2][0]["function"]["name"] == "propose_factors"
