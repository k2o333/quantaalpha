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


class TestUseToolCallingGatewaySwitch:
    """Tests proving call_structured() respects LLM_SETTINGS.use_tool_calling.

    These tests verify that:
    - When use_tool_calling=True (default), tools are passed through.
    - When use_tool_calling=False, tools/tool_choice are cleared and json_mode=True.
    """

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

    def test_call_structured_respects_use_tool_calling_false(self):
        """When use_tool_calling=False, call_structured must clear tools and enable json_mode."""
        from quantaalpha.llm.client import call_structured

        backend = self._make_backend()
        tools = [{"type": "function", "function": {"name": "emit_json"}}]

        captured_kwargs = {}

        def _capture(**kwargs):
            captured_kwargs.update(kwargs)
            return {"content": '{"hypothesis": "test"}', "finish_reason": "stop", "tool_calls": None}

        backend._try_create_chat_completion_or_embedding = MagicMock(side_effect=_capture)

        with patch("quantaalpha.llm.client.LLM_SETTINGS") as mock_settings:
            mock_settings.log_llm_chat_content = False
            mock_settings.use_tool_calling = False
            call_structured(
                backend,
                [{"role": "user", "content": "test"}],
                tools=tools,
                tool_choice="required",
                json_mode=False,
            )

        assert captured_kwargs["tools"] is None, "tools must be cleared when use_tool_calling=False"
        assert captured_kwargs["tool_choice"] is None, "tool_choice must be cleared when use_tool_calling=False"
        assert captured_kwargs["json_mode"] is True, "json_mode must be True when falling back"

    def test_call_structured_passes_tools_when_use_tool_calling_true(self):
        """When use_tool_calling=True, call_structured must pass tools through."""
        from quantaalpha.llm.client import call_structured

        backend = self._make_backend()
        tools = [{"type": "function", "function": {"name": "emit_json"}}]

        captured_kwargs = {}

        def _capture(**kwargs):
            captured_kwargs.update(kwargs)
            return {
                "content": None,
                "finish_reason": "tool_calls",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "emit_json", "arguments": '{"hypothesis": "test"}'},
                    }
                ],
            }

        backend._try_create_chat_completion_or_embedding = MagicMock(side_effect=_capture)

        with patch("quantaalpha.llm.client.LLM_SETTINGS") as mock_settings:
            mock_settings.log_llm_chat_content = False
            mock_settings.use_tool_calling = True
            call_structured(
                backend,
                [{"role": "user", "content": "test"}],
                tools=tools,
                tool_choice="required",
            )

        assert captured_kwargs["tools"] == tools, "tools must be passed when use_tool_calling=True"
        assert captured_kwargs["tool_choice"] == "required"
        assert captured_kwargs["json_mode"] is False, "json_mode should be False when tools are used"


class TestModelDegradationContract:
    """Tests for process-local model-level tool-call degradation.

    These tests MUST fail before implementation because:
    - _MODEL_DEGRADATION_STATE does not exist yet
    - call_structured() has no degradation logic yet
    - No capability-failure counting exists yet
    """

    def _make_backend(self, model_name="gpt-4-turbo"):
        from quantaalpha.llm.client import APIBackend

        backend = object.__new__(APIBackend)
        backend.use_azure = False
        backend.use_llama2 = False
        backend.use_gcr_endpoint = False
        backend.chat_stream = False
        backend.use_chat_cache = False
        backend.chat_model = model_name
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

    def test_first_tool_call_capability_failure_does_not_degrade(self):
        """First tool-call capability failure must NOT immediately degrade the model."""
        from quantaalpha.llm.client import call_structured, _is_tool_call_capability_failure, _MODEL_DEGRADATION_STATE

        backend = self._make_backend()
        backend._try_create_chat_completion_or_embedding = MagicMock(
            return_value={"content": '{"fallback": "no_tools"}', "finish_reason": "stop", "tool_calls": None}
        )

        with patch("quantaalpha.llm.client.LLM_SETTINGS") as mock_settings:
            mock_settings.log_llm_chat_content = False
            mock_settings.use_tool_calling = True
            # First failure: should still attempt tool call, not yet degraded
            result = call_structured(
                backend,
                [{"role": "user", "content": "test"}],
                tools=[{"type": "function", "function": {"name": "test_tool"}}],
                tool_choice="required",
                allow_text_fallback=True,
            )

        # After one failure, the model should NOT be degraded yet
        model_name = backend.chat_model
        state = _MODEL_DEGRADATION_STATE.get(model_name, {})
        assert state.get("tool_call_failure_count", 0) == 1, "First failure should be counted but not yet trigger degradation"
        assert state.get("force_text_json_fallback", False) is False, "Model must NOT be flagged as degraded after 1 failure"

    def test_third_tool_call_capability_failure_triggers_degradation(self):
        """Third consecutive tool-call capability failure MUST mark the model as degraded."""
        from quantaalpha.llm.client import call_structured, _MODEL_DEGRADATION_STATE

        backend = self._make_backend()

        # Simulate 3 consecutive failures
        for i in range(3):
            backend._try_create_chat_completion_or_embedding = MagicMock(
                return_value={"content": f'{{"attempt": {i}}}', "finish_reason": "stop", "tool_calls": None}
            )
            with patch("quantaalpha.llm.client.LLM_SETTINGS") as mock_settings:
                mock_settings.log_llm_chat_content = False
                mock_settings.use_tool_calling = True
                call_structured(
                    backend,
                    [{"role": "user", "content": f"test attempt {i}"}],
                    tools=[{"type": "function", "function": {"name": "test_tool"}}],
                    tool_choice="required",
                    allow_text_fallback=True,
                )

        model_name = backend.chat_model
        state = _MODEL_DEGRADATION_STATE.get(model_name, {})
        assert state.get("force_text_json_fallback", False) is True, (
            "Model MUST be flagged as degraded after 3 consecutive tool-call capability failures"
        )
        assert state.get("tool_call_failure_count", 0) >= 3, (
            "Failure count must be at least 3 after triggering degradation"
        )

    def test_degraded_model_skips_tool_call_on_subsequent_calls(self):
        """Once degraded, subsequent structured calls for the same model must skip tool call entirely."""
        from quantaalpha.llm.client import call_structured, _MODEL_DEGRADATION_STATE

        backend = self._make_backend()
        captured_kwargs_list = []

        def _capture(**kwargs):
            captured_kwargs_list.append(kwargs)
            return {"content": '{"result": "fallback"}', "finish_reason": "stop", "tool_calls": None}

        backend._try_create_chat_completion_or_embedding = MagicMock(side_effect=_capture)

        with patch("quantaalpha.llm.client.LLM_SETTINGS") as mock_settings:
            mock_settings.log_llm_chat_content = False
            mock_settings.use_tool_calling = True

            # First, degrade the model with 3 failures
            for i in range(3):
                backend._try_create_chat_completion_or_embedding = MagicMock(
                    return_value={"content": f'{{"fail": {i}}}', "finish_reason": "stop", "tool_calls": None}
                )
                call_structured(
                    backend,
                    [{"role": "user", "content": f"degrade {i}"}],
                    tools=[{"type": "function", "function": {"name": "test_tool"}}],
                    tool_choice="required",
                    allow_text_fallback=True,
                )

            # Reset capture and set up for the post-degradation call
            captured_kwargs_list.clear()
            backend._try_create_chat_completion_or_embedding = MagicMock(side_effect=_capture)

            # This call should skip tool call because model is degraded
            call_structured(
                backend,
                [{"role": "user", "content": "post-degradation call"}],
                tools=[{"type": "function", "function": {"name": "test_tool"}}],
                tool_choice="required",
                allow_text_fallback=True,
            )

        assert len(captured_kwargs_list) == 1
        call_kwargs = captured_kwargs_list[0]
        assert call_kwargs["tools"] is None, "Degraded model must NOT receive tools on subsequent calls"
        assert call_kwargs["json_mode"] is True, "Degraded model MUST use json_mode on subsequent calls"

    def test_different_models_have_independent_degradation(self):
        """Degradation state must be isolated per model — degrading one model must not affect another."""
        from quantaalpha.llm.client import call_structured, _MODEL_DEGRADATION_STATE

        backend_a = self._make_backend(model_name="model-a")
        backend_b = self._make_backend(model_name="model-b")

        # Degrade model-a with 3 failures
        for backend in [backend_a]:
            for i in range(3):
                backend._try_create_chat_completion_or_embedding = MagicMock(
                    return_value={"content": f'{{"fail": {i}}}', "finish_reason": "stop", "tool_calls": None}
                )
                with patch("quantaalpha.llm.client.LLM_SETTINGS") as mock_settings:
                    mock_settings.log_llm_chat_content = False
                    mock_settings.use_tool_calling = True
                    call_structured(
                        backend,
                        [{"role": "user", "content": f"degrade {i}"}],
                        tools=[{"type": "function", "function": {"name": "test_tool"}}],
                        tool_choice="required",
                        allow_text_fallback=True,
                    )

        # model-a should be degraded
        assert _MODEL_DEGRADATION_STATE.get("model-a", {}).get("force_text_json_fallback", False) is True

        # model-b should NOT be degraded
        assert _MODEL_DEGRADATION_STATE.get("model-b", {}).get("force_text_json_fallback", False) is False

    def test_non_capability_failure_does_not_trigger_degradation(self):
        """Network errors, 429, timeouts must NOT count as tool-call capability failures."""
        from quantaalpha.llm.client import call_structured, _MODEL_DEGRADATION_STATE, _is_tool_call_capability_failure

        # Test the capability failure detection function directly
        # A generic network error should NOT be classified as capability failure
        network_error = Exception("Connection timeout")
        assert _is_tool_call_capability_failure(network_error) is False, "Network errors must NOT be classified as capability failures"

        # A rate limit error should NOT be classified as capability failure
        rate_limit_error = Exception("Rate limit exceeded: 429")
        assert _is_tool_call_capability_failure(rate_limit_error) is False, "Rate limit errors must NOT be classified as capability failures"

    def test_tool_unsupported_exception_triggers_capability_failure(self):
        """Provider returning 'tools not supported' type errors MUST be classified as capability failure."""
        from quantaalpha.llm.client import _is_tool_call_capability_failure

        # Tool-not-supported errors MUST be classified as capability failures
        err1 = Exception("This model does not support function calling")
        assert _is_tool_call_capability_failure(err1) is True

        err2 = Exception("tool_choice is not supported")
        assert _is_tool_call_capability_failure(err2) is True

        err3 = Exception("tools parameter is not supported")
        assert _is_tool_call_capability_failure(err3) is True


    def test_provider_unsupported_tools_exception_triggers_capability_failure(self):
        """Provider returning 'does not support tools/function calling' MUST be classified as capability failure."""
        from quantaalpha.llm.client import _is_tool_call_capability_failure

        # Various "unsupported" error messages from providers MUST be classified as capability failures
        err_unsupported_function_calling = Exception("This model does not support function calling")
        assert _is_tool_call_capability_failure(err_unsupported_function_calling) is True

        err_unsupported_tools = Exception("This model does not support tools")
        assert _is_tool_call_capability_failure(err_unsupported_tools) is True

        err_unsupported_tool_choice = Exception("This model does not support tool_choice")
        assert _is_tool_call_capability_failure(err_unsupported_tool_choice) is True

    def test_backend_rejects_tools_parameter_triggers_capability_failure(self):
        """Backend rejecting tools/tool_choice parameters MUST be classified as capability failure."""
        from quantaalpha.llm.client import _is_tool_call_capability_failure

        # Invalid parameter errors pointing to tools/tool_choice MUST be classified as capability failures
        err_invalid_param_tools = Exception("invalid_parameter_error: tools")
        assert _is_tool_call_capability_failure(err_invalid_param_tools) is True

        err_invalid_param_tool_choice = Exception("invalid_parameter_error: tool_choice")
        assert _is_tool_call_capability_failure(err_invalid_param_tool_choice) is True

        err_unsupported_parameter = Exception("unsupported parameter: tools")
        assert _is_tool_call_capability_failure(err_unsupported_parameter) is True

    def test_response_without_tool_calls_when_requested_is_capability_failure(self):
        """When tool call is requested but response consistently lacks tool_calls, this MUST be treated as capability failure."""
        from quantaalpha.llm.client import _detect_tool_call_capability_failure_from_response

        # Response with finish_reason='stop' but no tool_calls when tools were requested
        response_without_tool_calls = {
            "content": "Some text response",
            "finish_reason": "stop",
            "tool_calls": None,
        }
        assert _detect_tool_call_capability_failure_from_response(response_without_tool_calls) is True

        # Response with empty tool_calls list should NOT trigger capability failure (valid response)
        response_with_empty_tool_calls = {
            "content": None,
            "finish_reason": "stop",
            "tool_calls": [],
        }
        assert _detect_tool_call_capability_failure_from_response(response_with_empty_tool_calls) is False

        # Response with actual tool_calls should NOT trigger capability failure
        response_with_tool_calls = {
            "content": None,
            "finish_reason": "tool_calls",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "test_tool", "arguments": "{}"},
                }
            ],
        }
        assert _detect_tool_call_capability_failure_from_response(response_with_tool_calls) is False

    def test_compatibility_wrapper_returns_dict_by_default(self):
        """The compatibility wrapper must return dict in all cases (backward compatibility)."""
        from quantaalpha.llm.client import call_structured, _MODEL_DEGRADATION_STATE

        # Clear any leftover degradation state from previous tests
        _MODEL_DEGRADATION_STATE.clear()

        backend = self._make_backend()
        backend._try_create_chat_completion_or_embedding = MagicMock(
            return_value={
                "content": '{"result": "test"}',
                "finish_reason": "stop",
                "tool_calls": None,
            }
        )

        with patch("quantaalpha.llm.client.LLM_SETTINGS") as mock_settings:
            mock_settings.log_llm_chat_content = False
            mock_settings.use_tool_calling = True

            result = backend.build_messages_and_create_chat_completion_json(
                user_prompt="test",
                tools=[{"type": "function", "function": {"name": "test_tool"}}],
                tool_choice="required",
            )

        assert isinstance(result, dict), "Compatibility wrapper must always return dict"
        assert result == {"result": "test"}


class TestCompatibilityWrapperDegradation:
    """Tests proving build_messages_and_create_chat_completion_json delegates to call_structured().

    These tests MUST fail before implementation because:
    - The compatibility wrapper does not delegate to call_structured() yet
    - It has its own direct json_mode path
    """

    def _make_backend(self, model_name="gpt-4-turbo"):
        from quantaalpha.llm.client import APIBackend

        backend = object.__new__(APIBackend)
        backend.use_azure = False
        backend.use_llama2 = False
        backend.use_gcr_endpoint = False
        backend.chat_stream = False
        backend.use_chat_cache = False
        backend.chat_model = model_name
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

    def test_compatibility_wrapper_delegates_to_call_structured(self):
        """build_messages_and_create_chat_completion_json must delegate to call_structured, not do its own thing."""
        import inspect
        from quantaalpha.llm.client import APIBackend

        source = inspect.getsource(APIBackend.build_messages_and_create_chat_completion_json)
        assert "call_structured" in source, (
            "build_messages_and_create_chat_completion_json must delegate to call_structured, "
            "not call _try_create_chat_completion_or_embedding directly with json_mode"
        )

    def test_compatibility_wrapper_respects_model_degradation(self):
        """When model is degraded, the compatibility wrapper must go through text-json path."""
        from quantaalpha.llm.client import call_structured, _MODEL_DEGRADATION_STATE

        backend = self._make_backend()
        captured_kwargs_list = []

        def _capture(**kwargs):
            captured_kwargs_list.append(kwargs)
            return {"content": '{"hypothesis": "test"}', "finish_reason": "stop", "tool_calls": None}

        with patch("quantaalpha.llm.client.LLM_SETTINGS") as mock_settings:
            mock_settings.log_llm_chat_content = False
            mock_settings.use_tool_calling = True

            # Degrade the model first
            for i in range(3):
                backend._try_create_chat_completion_or_embedding = MagicMock(
                    return_value={"content": f'{{"fail": {i}}}', "finish_reason": "stop", "tool_calls": None}
                )
                call_structured(
                    backend,
                    [{"role": "user", "content": f"degrade {i}"}],
                    tools=[{"type": "function", "function": {"name": "test_tool"}}],
                    tool_choice="required",
                    allow_text_fallback=True,
                )

            # Now use the compatibility wrapper
            captured_kwargs_list.clear()
            backend._try_create_chat_completion_or_embedding = MagicMock(side_effect=_capture)

            result = backend.build_messages_and_create_chat_completion_json(
                user_prompt="test after degradation",
                tools=[{"type": "function", "function": {"name": "test_tool"}}],
                tool_choice="required",
            )

        # After degradation, the wrapper must call with tools=None and json_mode=True
        assert len(captured_kwargs_list) == 1
        call_kwargs = captured_kwargs_list[0]
        assert call_kwargs["tools"] is None, "Degraded model must not use tools via compatibility wrapper"
        assert call_kwargs["json_mode"] is True, "Degraded model must use json_mode via compatibility wrapper"

    def test_call_structured_default_use_tool_calling_true(self):
        """Default use_tool_calling must be True to match current runtime behavior."""
        from quantaalpha.llm.config import LLMSettings

        # Check the default value in the class definition using Pydantic V2 API
        assert LLMSettings.model_fields["use_tool_calling"].default is True, (
            "use_tool_calling default must be True to match current runtime behavior"
        )

    def test_call_structured_json_mode_false_when_tools_and_use_tool_calling_true(self):
        """When tools are passed and use_tool_calling=True, json_mode must be False internally."""
        from quantaalpha.llm.client import call_structured, _MODEL_DEGRADATION_STATE

        # Clear any leftover degradation state from previous tests
        _MODEL_DEGRADATION_STATE.clear()

        backend = self._make_backend()
        tools = [{"type": "function", "function": {"name": "emit_json"}}]

        captured_kwargs = {}

        def _capture(**kwargs):
            captured_kwargs.update(kwargs)
            return {
                "content": None,
                "finish_reason": "tool_calls",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "emit_json", "arguments": '{"result": 42}'},
                    }
                ],
            }

        backend._try_create_chat_completion_or_embedding = MagicMock(side_effect=_capture)

        with patch("quantaalpha.llm.client.LLM_SETTINGS") as mock_settings:
            mock_settings.log_llm_chat_content = False
            mock_settings.use_tool_calling = True
            call_structured(
                backend,
                [{"role": "user", "content": "test"}],
                tools=tools,
                tool_choice="required",
                json_mode=True,  # caller passes True, but internal should override
            )

        # When tools are actually used, json_mode should be False internally
        assert captured_kwargs["json_mode"] is False
