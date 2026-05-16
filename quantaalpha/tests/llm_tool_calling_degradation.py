"""Tests for Tool Calling support in APIBackend."""

from unittest.mock import MagicMock, patch

import pytest


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

        # Use a real capability failure pattern (exception-based)
        call_count = [0]

        def _fail_on_first_call(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call: raise a real capability failure exception
                raise Exception("tools parameter is not supported")
            # Subsequent calls succeed
            return {"content": '{"fallback": "no_tools"}', "finish_reason": "stop", "tool_calls": None}

        backend._try_create_chat_completion_or_embedding = MagicMock(side_effect=_fail_on_first_call)

        with patch("quantaalpha.llm.client.LLM_SETTINGS") as mock_settings:
            mock_settings.log_llm_chat_content = False
            mock_settings.use_tool_calling = True
            # First failure: should still attempt tool call, not yet degraded
            with pytest.raises(Exception, match="tools parameter is not supported"):
                call_structured(
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

    def test_successful_structured_call_resets_prior_capability_failure_count(self):
        """The degradation counter is consecutive: a later success clears prior strikes."""
        from quantaalpha.llm.client import call_structured, _MODEL_DEGRADATION_STATE

        _MODEL_DEGRADATION_STATE.clear()
        backend = self._make_backend()

        with patch("quantaalpha.llm.client.LLM_SETTINGS") as mock_settings:
            mock_settings.log_llm_chat_content = False
            mock_settings.use_tool_calling = True
            backend._try_create_chat_completion_or_embedding = MagicMock(side_effect=Exception("tools parameter is not supported"))
            with pytest.raises(Exception, match="tools parameter is not supported"):
                call_structured(
                    backend,
                    [{"role": "user", "content": "first failure"}],
                    tools=[{"type": "function", "function": {"name": "test_tool"}}],
                    tool_choice="required",
                )

            backend._try_create_chat_completion_or_embedding = MagicMock(
                return_value={
                    "content": None,
                    "finish_reason": "tool_calls",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "test_tool", "arguments": '{"ok": true}'},
                        }
                    ],
                }
            )
            result = call_structured(
                backend,
                [{"role": "user", "content": "success"}],
                tools=[{"type": "function", "function": {"name": "test_tool"}}],
                tool_choice="required",
            )

        assert result == {"ok": True}
        state = _MODEL_DEGRADATION_STATE.get(backend.chat_model, {})
        assert state.get("tool_call_failure_count", 0) == 0
        assert state.get("force_text_json_fallback", False) is False

    def test_third_tool_call_capability_failure_triggers_degradation(self):
        """Third consecutive tool-call capability failure MUST mark the model as degraded."""
        from quantaalpha.llm.client import call_structured, _MODEL_DEGRADATION_STATE

        backend = self._make_backend()

        # Simulate 3 consecutive capability failures via exceptions
        for i in range(3):
            backend._try_create_chat_completion_or_embedding = MagicMock(side_effect=Exception("tools parameter is not supported"))
            with patch("quantaalpha.llm.client.LLM_SETTINGS") as mock_settings:
                mock_settings.log_llm_chat_content = False
                mock_settings.use_tool_calling = True
                with pytest.raises(Exception, match="tools parameter is not supported"):
                    call_structured(
                        backend,
                        [{"role": "user", "content": f"test attempt {i}"}],
                        tools=[{"type": "function", "function": {"name": "test_tool"}}],
                        tool_choice="required",
                        allow_text_fallback=True,
                    )

        model_name = backend.chat_model
        state = _MODEL_DEGRADATION_STATE.get(model_name, {})
        assert state.get("force_text_json_fallback", False) is True, "Model MUST be flagged as degraded after 3 consecutive tool-call capability failures"
        assert state.get("tool_call_failure_count", 0) >= 3, "Failure count must be at least 3 after triggering degradation"

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
                backend._try_create_chat_completion_or_embedding = MagicMock(side_effect=Exception("tools parameter is not supported"))
                with pytest.raises(Exception, match="tools parameter is not supported"):
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

    def test_degraded_structured_call_respects_structured_streaming_mode(self):
        """Degraded structured calls must still obey the unified structured streaming switch."""
        from quantaalpha.llm.client import call_structured, _MODEL_DEGRADATION_STATE

        backend = self._make_backend()
        backend.chat_stream = True
        _MODEL_DEGRADATION_STATE[backend.chat_model] = {
            "tool_call_failure_count": 3,
            "force_text_json_fallback": True,
        }

        def _capture(**kwargs):
            assert backend.chat_stream is False
            return {"content": '{"result": "fallback"}', "finish_reason": "stop", "tool_calls": None}

        backend._try_create_chat_completion_or_embedding = MagicMock(side_effect=_capture)

        with patch("quantaalpha.llm.client.LLM_SETTINGS") as mock_settings:
            mock_settings.log_llm_chat_content = False
            mock_settings.use_tool_calling = True
            mock_settings.structured_streaming_mode = False

            result = call_structured(
                backend,
                [{"role": "user", "content": "post-degradation call"}],
                tools=[{"type": "function", "function": {"name": "test_tool"}}],
                tool_choice="required",
                allow_text_fallback=True,
            )

        assert result == {"result": "fallback"}
        assert backend.chat_stream is True

    def test_different_models_have_independent_degradation(self):
        """Degradation state must be isolated per model — degrading one model must not affect another."""
        from quantaalpha.llm.client import call_structured, _MODEL_DEGRADATION_STATE

        backend_a = self._make_backend(model_name="model-a")
        backend_b = self._make_backend(model_name="model-b")

        # Degrade model-a with 3 failures
        for backend in [backend_a]:
            for i in range(3):
                backend._try_create_chat_completion_or_embedding = MagicMock(side_effect=Exception("tools parameter is not supported"))
                with patch("quantaalpha.llm.client.LLM_SETTINGS") as mock_settings:
                    mock_settings.log_llm_chat_content = False
                    mock_settings.use_tool_calling = True
                    with pytest.raises(Exception, match="tools parameter is not supported"):
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
        """When tool call is requested but response lacks tool_calls, this must NOT auto-count as capability failure.

        The new normalized path treats finish_reason="stop" with missing tool_calls as valid
        when structured text content is present. Only explicit protocol-level unsupported-tool
        errors count as capability failures.
        """
        from quantaalpha.llm.client import _detect_tool_call_capability_failure_from_response

        # Response with finish_reason='stop' but no tool_calls should NOT be capability failure
        # when valid structured text may still be present
        response_without_tool_calls = {
            "content": "Some text response",
            "finish_reason": "stop",
            "tool_calls": None,
        }
        assert _detect_tool_call_capability_failure_from_response(response_without_tool_calls) is False

        # Response with empty tool_calls list should NOT trigger capability failure
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
        assert "call_structured" in source, "build_messages_and_create_chat_completion_json must delegate to call_structured, not call _try_create_chat_completion_or_embedding directly with json_mode"

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
                backend._try_create_chat_completion_or_embedding = MagicMock(side_effect=Exception("tools parameter is not supported"))
                with pytest.raises(Exception, match="tools parameter is not supported"):
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
        assert LLMSettings.model_fields["use_tool_calling"].default is True, "use_tool_calling default must be True to match current runtime behavior"

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


class TestFinishReasonStopNotCapabilityFailure:
    """Regression tests: finish_reason="stop" + missing tool_calls must NOT auto-count as capability failure.

    These tests MUST FAIL before the fix because the current code treats
    finish_reason="stop" with absent tool_calls as a soft capability failure signal.
    After the fix, valid structured text/content should parse successfully without
    incrementing the degradation counter.
    """

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

    def test_finish_reason_stop_with_valid_content_not_counted_as_capability_failure(self):
        """finish_reason="stop" with valid JSON content must not increment capability failure count."""
        from quantaalpha.llm.client import call_structured, _MODEL_DEGRADATION_STATE

        _MODEL_DEGRADATION_STATE.clear()

        backend = self._make_backend()
        backend._try_create_chat_completion_or_embedding = MagicMock(
            return_value={
                "content": '{"hypothesis": "valid_hypothesis"}',
                "finish_reason": "stop",
                "tool_calls": None,
            }
        )

        with patch("quantaalpha.llm.client.LLM_SETTINGS") as mock_settings:
            mock_settings.log_llm_chat_content = False
            mock_settings.use_tool_calling = True
            result = call_structured(
                backend,
                [{"role": "user", "content": "test"}],
                tools=[{"type": "function", "function": {"name": "emit_json"}}],
                tool_choice="required",
                allow_text_fallback=True,
            )

        assert result["hypothesis"] == "valid_hypothesis"
        # The model must NOT be marked as degraded
        model_name = backend.chat_model
        state = _MODEL_DEGRADATION_STATE.get(model_name, {})
        assert state.get("tool_call_failure_count", 0) == 0, "finish_reason=stop with valid content must not count as capability failure"
        assert state.get("force_text_json_fallback", False) is False

    def test_finish_reason_stop_with_valid_reasoning_content_not_counted_as_capability_failure(self):
        """finish_reason="stop" with valid reasoning_content JSON must not increment capability failure count."""
        from quantaalpha.llm.client import call_structured, _MODEL_DEGRADATION_STATE

        _MODEL_DEGRADATION_STATE.clear()

        backend = self._make_backend()
        backend._try_create_chat_completion_or_embedding = MagicMock(
            return_value={
                "content": "",
                "reasoning_content": '{"result": "from_reasoning"}',
                "finish_reason": "stop",
                "tool_calls": None,
            }
        )

        with patch("quantaalpha.llm.client.LLM_SETTINGS") as mock_settings:
            mock_settings.log_llm_chat_content = False
            mock_settings.use_tool_calling = True
            result = call_structured(
                backend,
                [{"role": "user", "content": "test"}],
                tools=[{"type": "function", "function": {"name": "emit_json"}}],
                tool_choice="required",
                allow_text_fallback=True,
            )

        assert result["result"] == "from_reasoning"
        model_name = backend.chat_model
        state = _MODEL_DEGRADATION_STATE.get(model_name, {})
        assert state.get("tool_call_failure_count", 0) == 0, "finish_reason=stop with valid reasoning_content must not count as capability failure"
