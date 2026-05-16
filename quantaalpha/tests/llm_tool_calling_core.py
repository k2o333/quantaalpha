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

    def test_parse_tool_calls_even_when_finish_reason_is_stop(self):
        """Some OpenAI-compatible proxies return tool_calls with finish_reason=stop."""
        backend = self._make_backend()

        tool_call_mock = MagicMock()
        tool_call_mock.id = "call_stop_reason"
        tool_call_mock.function.name = "propose_factors"
        tool_call_mock.function.arguments = '{"factors": [{"factor_name": "test", "factor_expression": "ts_mean(close, 5)"}]}'

        message_mock = MagicMock()
        message_mock.content = None
        message_mock.tool_calls = [tool_call_mock]

        choice_mock = MagicMock()
        choice_mock.message = message_mock
        choice_mock.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [choice_mock]
        backend.chat_client.chat.completions.create.return_value = mock_response

        result = self._run_completion(
            backend,
            [{"role": "user", "content": "propose factors"}],
            tools=[{"type": "function", "function": {"name": "propose_factors"}}],
        )

        assert result[1] == "stop"
        assert result[2] is not None
        assert result[2][0]["id"] == "call_stop_reason"
        assert result[2][0]["function"]["name"] == "propose_factors"

    def test_tool_call_requests_bypass_chat_cache(self):
        """Cached text responses must not mask fresh tool_calls for structured requests."""
        backend = self._make_backend()
        backend.use_chat_cache = True
        backend.dump_chat_cache = True
        backend.cache.chat_get.return_value = '{"source": "stale_text_cache"}'

        tool_call_mock = MagicMock()
        tool_call_mock.id = "call_fresh"
        tool_call_mock.function.name = "propose_factors"
        tool_call_mock.function.arguments = '{"source": "fresh_tool_call"}'

        message_mock = MagicMock()
        message_mock.content = None
        message_mock.tool_calls = [tool_call_mock]

        choice_mock = MagicMock()
        choice_mock.message = message_mock
        choice_mock.finish_reason = "tool_calls"

        mock_response = MagicMock()
        mock_response.choices = [choice_mock]
        backend.chat_client.chat.completions.create.return_value = mock_response

        result = self._run_completion(
            backend,
            [{"role": "user", "content": "propose factors"}],
            tools=[{"type": "function", "function": {"name": "propose_factors"}}],
        )

        assert backend.cache.chat_get.call_count == 0
        assert backend.cache.chat_set.call_count == 0
        assert result[2][0]["id"] == "call_fresh"

    def test_non_streaming_tool_calls_with_none_content_not_logged_as_empty_response(self, capsys):
        """Non-streaming tool-call response with content=None must not log 'Empty LLM response'."""
        import logging
        from unittest.mock import patch

        backend = self._make_backend()

        tool_call_mock = MagicMock()
        tool_call_mock.id = "call_xyz789"
        tool_call_mock.function.name = "propose_factors"
        tool_call_mock.function.arguments = '{"factors": [{"factor_name": "test2", "factor_expression": "ts_std(close, 10)"}]}'

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

        # Patch the actual loguru logger used in client.py so we can intercept
        # warning/info calls regardless of caplog incompatibility with loguru.
        logged_messages = []

        def capture_warning(msg, *args, **kwargs):
            logged_messages.append(("warning", str(msg)))

        def capture_info(msg, *args, **kwargs):
            logged_messages.append(("info", str(msg)))

        with (
            patch("quantaalpha.llm.client.logger.warning", side_effect=capture_warning),
            patch("quantaalpha.llm.client.logger.info", side_effect=capture_info),
            patch("quantaalpha.llm.client.LLM_SETTINGS") as mock_settings,
        ):
            mock_settings.log_llm_chat_content = False
            mock_settings.use_auto_chat_cache_seed_gen = False
            result = backend._create_chat_completion_inner_function(
                messages=messages,
                reasoning_flag=False,
                tools=tools,
            )

        # Assert finish_reason and tool_calls are correctly returned
        assert result[1] == "tool_calls"
        assert result[2] is not None
        assert len(result[2]) == 1
        assert result[2][0]["function"]["name"] == "propose_factors"
        assert "ts_std" in result[2][0]["function"]["arguments"]

        # Assert no WARNING log contains the misleading "Empty LLM response" phrase
        for level, msg in logged_messages:
            assert "Empty LLM response" not in msg, f"Must not log 'Empty LLM response' for tool-call with None content: {msg}"

        # Assert a diagnostic about tool_calls and content exists at INFO level
        tool_call_diagnostics = [msg for level, msg in logged_messages if level == "info" and ("tool_call" in msg.lower() or "content" in msg.lower())]
        assert len(tool_call_diagnostics) > 0, f"Expected a diagnostic log about tool_calls/content when tool calls present with None content. Logged messages: {logged_messages}"


class TestBuildMessagesToolRole:
    """Tests for tool role in build_messages."""

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

    def test_build_messages_with_tool_results(self):
        """build_messages appends tool role messages."""
        backend = self._make_backend()

        messages = backend.build_messages(
            user_prompt="propose factors",
            system_prompt="You are a factor mining assistant",
            tool_results=[
                {"tool_call_id": "call_abc", "name": "propose_factors", "content": '{"factors": []}'},
            ],
        )

        # Should have system, user, and tool messages
        roles = [m["role"] for m in messages]
        assert "tool" in roles

        tool_msg = [m for m in messages if m["role"] == "tool"][0]
        assert tool_msg["tool_call_id"] == "call_abc"
        assert tool_msg["name"] == "propose_factors"
        assert tool_msg["content"] == '{"factors": []}'


class TestAutoContinueToolCalls:
    """Tests for Bug 4: _auto_continue path must not discard tool_calls."""

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

    def test_auto_continue_preserves_tool_calls(self):
        """_create_chat_completion_auto_continue returns tool_calls when present.

        Bug 4: Previously the function only returned str (response content),
        discarding result[2] (tool_calls) from _create_chat_completion_inner_function.
        """
        backend = self._make_backend()

        tool_call_mock = MagicMock()
        tool_call_mock.id = "call_xyz"
        tool_call_mock.function.name = "propose_factors"
        tool_call_mock.function.arguments = '{"factors": []}'

        message_mock = MagicMock()
        message_mock.content = "I will propose factors"
        message_mock.tool_calls = [tool_call_mock]

        choice_mock = MagicMock()
        choice_mock.message = message_mock
        choice_mock.finish_reason = "tool_calls"

        mock_response = MagicMock()
        mock_response.choices = [choice_mock]
        backend.chat_client.chat.completions.create.return_value = mock_response

        messages = [{"role": "user", "content": "propose factors"}]
        tools = [{"type": "function", "function": {"name": "propose_factors"}}]

        with patch("quantaalpha.llm.client.LLM_SETTINGS") as mock_settings:
            mock_settings.log_llm_chat_content = False
            mock_settings.use_auto_chat_cache_seed_gen = False
            result = backend._create_chat_completion_auto_continue(
                messages=messages,
                tools=tools,
                reasoning_flag=False,
            )

        # When tool_calls are present, result should be a dict containing tool_calls
        assert isinstance(result, dict), f"Expected dict when tool_calls present, got {type(result).__name__}. tool_calls data must not be discarded."
        assert "tool_calls" in result, "Result dict must contain 'tool_calls' key"
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["id"] == "call_xyz"
        assert result["tool_calls"][0]["function"]["name"] == "propose_factors"
        assert result["content"] == "I will propose factors"
        assert result["finish_reason"] == "tool_calls"

    def test_auto_continue_returns_str_when_no_tool_calls(self):
        """_create_chat_completion_auto_continue returns str when no tool_calls (backward compat)."""
        backend = self._make_backend()

        message_mock = MagicMock()
        message_mock.content = "Hello world"
        message_mock.tool_calls = None

        choice_mock = MagicMock()
        choice_mock.message = message_mock
        choice_mock.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [choice_mock]
        backend.chat_client.chat.completions.create.return_value = mock_response

        messages = [{"role": "user", "content": "hello"}]

        with patch("quantaalpha.llm.client.LLM_SETTINGS") as mock_settings:
            mock_settings.log_llm_chat_content = False
            mock_settings.use_auto_chat_cache_seed_gen = False
            result = backend._create_chat_completion_auto_continue(
                messages=messages,
                reasoning_flag=False,
            )

        # No tool_calls — should return str as before
        assert isinstance(result, str)
        assert result == "Hello world"

    def test_auto_continue_does_not_continue_text_when_tools_requested_but_no_tool_calls(self):
        """Tools requests must not use text auto-continue when the provider omits tool_calls."""
        backend = self._make_backend()

        first_result = ("", "length")

        with (
            patch.object(backend, "_create_chat_completion_inner_function", side_effect=[first_result]) as mock_inner,
            patch("quantaalpha.llm.client.LLM_SETTINGS") as mock_settings,
        ):
            mock_settings.log_llm_chat_content = False
            mock_settings.use_auto_chat_cache_seed_gen = False
            result = backend._create_chat_completion_auto_continue(
                messages=[{"role": "user", "content": "return structured data"}],
                tools=[{"type": "function", "function": {"name": "emit_json"}}],
                tool_choice="required",
                reasoning_flag=False,
            )

        assert isinstance(result, dict), "Structured tool requests should return a dict wrapper even when tool_calls are missing"
        assert result["content"] == ""
        assert result["finish_reason"] == "length"
        assert result["tool_calls"] is None
        assert mock_inner.call_count == 1, "Tool requests must not append a text-only 'continue the former output' turn"


class TestJsonModeToolCallPriority:
    """Tests for JSON parsing priority when tool calls are available."""

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

    def test_json_mode_prefers_tool_call_arguments_before_text_json(self):
        """When tool_calls exist, parse function.arguments before text response JSON."""
        backend = self._make_backend()
        backend._try_create_chat_completion_or_embedding = MagicMock(
            return_value={
                "content": '{"source": "text", "value": 1}',
                "finish_reason": "tool_calls",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "emit_json",
                            "arguments": '{"source": "tool", "value": 2}',
                        },
                    }
                ],
            }
        )

        result = backend.build_messages_and_create_chat_completion_json(
            user_prompt="return structured data",
            tools=[{"type": "function", "function": {"name": "emit_json"}}],
        )

        assert result == {"source": "tool", "value": 2}

    def test_json_mode_falls_back_to_text_when_tool_call_arguments_invalid(self):
        """Invalid tool call JSON should fall back to text JSON content."""
        backend = self._make_backend()
        backend._try_create_chat_completion_or_embedding = MagicMock(
            return_value={
                "content": '{"source": "text", "value": 1}',
                "finish_reason": "tool_calls",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "emit_json",
                            "arguments": "definitely not json",
                        },
                    }
                ],
            }
        )

        result = backend.build_messages_and_create_chat_completion_json(
            user_prompt="return structured data",
            tools=[{"type": "function", "function": {"name": "emit_json"}}],
        )

        assert result == {"source": "text", "value": 1}

    def test_json_mode_keeps_text_parsing_when_no_tool_calls_present(self):
        """Plain JSON text path stays backward compatible when no tool_calls exist."""
        backend = self._make_backend()
        backend._try_create_chat_completion_or_embedding = MagicMock(return_value='{"source": "text", "value": 1}')

        result = backend.build_messages_and_create_chat_completion_json(
            user_prompt="return structured data",
        )

        assert result == {"source": "text", "value": 1}

    def test_call_structured_disables_streaming_when_tools_are_used(self):
        """Structured tool calls must force non-streaming to preserve tool_calls payloads."""
        from quantaalpha.llm.client import call_structured

        backend = self._make_backend()
        backend.chat_stream = True

        def _fake_call(**kwargs):
            assert backend.chat_stream is False
            return {
                "content": None,
                "finish_reason": "tool_calls",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "emit_json",
                            "arguments": '{"source": "tool", "value": 2}',
                        },
                    }
                ],
            }

        backend._try_create_chat_completion_or_embedding = MagicMock(side_effect=_fake_call)

        result = call_structured(
            backend,
            [{"role": "user", "content": "return structured data"}],
            tools=[{"type": "function", "function": {"name": "emit_json"}}],
            tool_choice="required",
            json_mode=True,
        )

        assert result == {"source": "tool", "value": 2}
        assert backend.chat_stream is True
        call_kwargs = backend._try_create_chat_completion_or_embedding.call_args.kwargs
        assert call_kwargs["json_mode"] is False
