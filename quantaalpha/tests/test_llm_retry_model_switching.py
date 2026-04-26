"""Tests for retry model switching behavior.

These tests verify:
1. After 3 consecutive failures on the same model, ProviderPool switching is attempted.
2. ProviderPool switching applies the provider_config.model to the request.
3. Structured parse failures count toward the switch threshold.
4. Without ProviderPool, retry still works but no switching occurs.
"""
# ruff: noqa: D205

from unittest.mock import MagicMock, patch

import pytest


def _make_minimal_backend():
    """Create a minimal APIBackend with mocked OpenAI client."""
    from quantaalpha.llm.client import APIBackend

    backend = object.__new__(APIBackend)
    backend.use_azure = False
    backend.use_llama2 = False
    backend.use_gcr_endpoint = False
    backend.chat_stream = False
    backend.use_chat_cache = False
    backend.dump_chat_cache = False
    backend.chat_model = "gpt-4-turbo"
    backend.reasoning_model = ""
    backend.chat_client = MagicMock()
    backend.cache = MagicMock()
    backend.cache.chat_get.return_value = None
    backend.task_model_map = {}
    backend.routing_default = ""
    backend.chat_model_map = {}
    backend.chat_api_key = "test-key"
    backend.base_url = "https://api.test.com"
    backend.embedding_api_key = ""
    backend.embedding_base_url = None
    backend.encoder = None
    backend.chat_seed = None
    backend.retry_wait_seconds = 0  # No sleep in tests
    backend._provider_pool = None
    backend.get_model_for_task = APIBackend.get_model_for_task.__get__(backend, APIBackend)
    return backend


def _mock_create_fn(call_count_holder, fail_until=3, success_response=None):
    """Create a mock function that fails N times then succeeds."""
    def mock_create(**kwargs):
        call_count_holder["count"] += 1
        if call_count_holder["count"] < fail_until:
            raise RuntimeError(f"Simulated failure {call_count_holder['count']}")
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = success_response or "success"
        mock_resp.choices[0].finish_reason = "stop"
        return mock_resp
    return mock_create


class TestOpenAIClientRetryBoundary:
    """Test the boundary between our retry logic and the OpenAI SDK retry logic."""

    def test_openai_client_uses_our_timeout_and_disables_sdk_retries(self):
        """OpenAI SDK retries must be disabled so failures return to our model-switch retry loop."""
        from quantaalpha.llm.client import LLM_SETTINGS, openai

        backend = _make_minimal_backend()

        with patch.object(LLM_SETTINGS, "openai_request_timeout_seconds", 17, create=True), \
             patch.object(LLM_SETTINGS, "openai_sdk_max_retries", 0, create=True), \
             patch.object(openai, "OpenAI") as openai_client:
            backend._create_openai_client(api_key="key-a", base_url="https://a.test/v1")

        openai_client.assert_called_once_with(
            api_key="key-a",
            base_url="https://a.test/v1",
            timeout=17,
            max_retries=0,
        )

    def test_chat_completion_logs_request_boundary_with_model_and_provider(self):
        """The HTTP boundary log should identify the model/provider before SDK execution."""
        from quantaalpha.llm.client import LLM_SETTINGS

        backend = _make_minimal_backend()
        backend._current_retry_provider_name = "provider-a"

        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "ok"
        mock_resp.choices[0].finish_reason = "stop"
        backend.chat_client.chat.completions.create.return_value = mock_resp

        with patch.object(LLM_SETTINGS, "log_llm_chat_content", False), \
             patch.object(LLM_SETTINGS, "use_auto_chat_cache_seed_gen", False), \
             patch.object(LLM_SETTINGS, "max_retry", 1), \
             patch.object(LLM_SETTINGS, "chat_temperature", 0.7), \
             patch.object(LLM_SETTINGS, "chat_max_tokens", 1000), \
             patch.object(LLM_SETTINGS, "chat_frequency_penalty", 0.0), \
             patch.object(LLM_SETTINGS, "chat_presence_penalty", 0.0), \
             patch("quantaalpha.llm.client.logger") as mock_logger:

            backend._try_create_chat_completion_or_embedding(
                messages=[{"role": "user", "content": "test"}],
                chat_completion=True,
                max_retry=1,
                reasoning_flag=False,
            )

        log_messages = [str(call.args[0]) for call in mock_logger.info.call_args_list if call.args]
        assert any(
            "[llm-request] start" in message
            and "model=gpt-4-turbo" in message
            and "provider=provider-a" in message
            for message in log_messages
        )

    def test_provider_pool_request_uses_provider_matching_current_model_before_switch_threshold(self):
        """Normal retries must not round-robin to a provider whose model differs from the current model."""
        from quantaalpha.llm.client import LLM_SETTINGS, openai
        from quantaalpha.llm.provider_pool import ProviderPool

        pool = ProviderPool(routing="round_robin")
        pool.add_provider("litellm_Kimi-K2.5", api_keys=["key-kimi"], base_url="https://kimi.test/v1", model="Kimi-K2.5")
        pool.add_provider("litellm_glm47f", api_keys=["key-glm"], base_url="https://glm.test/v1", model="glm-4.7-flash")

        backend = _make_minimal_backend()
        backend.chat_model = "glm-4.7-flash"
        backend._provider_pool = pool

        client_base_urls = []
        requested_models = []
        call_count_holder = {"count": 0}

        def track_create(**kwargs):
            requested_models.append(kwargs.get("model"))
            call_count_holder["count"] += 1
            if call_count_holder["count"] < 3:
                raise RuntimeError(f"Failure {call_count_holder['count']}")
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            mock_resp.choices[0].message.content = "ok"
            mock_resp.choices[0].finish_reason = "stop"
            return mock_resp

        mock_client = MagicMock()
        mock_client.chat.completions.create = track_create

        def capture_openai_client(**kwargs):
            client_base_urls.append(kwargs.get("base_url"))
            return mock_client

        with patch.object(LLM_SETTINGS, "log_llm_chat_content", False), \
             patch.object(LLM_SETTINGS, "use_auto_chat_cache_seed_gen", False), \
             patch.object(LLM_SETTINGS, "max_retry", 3), \
             patch.object(LLM_SETTINGS, "chat_temperature", 0.7), \
             patch.object(LLM_SETTINGS, "chat_max_tokens", 1000), \
             patch.object(LLM_SETTINGS, "chat_frequency_penalty", 0.0), \
             patch.object(LLM_SETTINGS, "chat_presence_penalty", 0.0), \
             patch.object(LLM_SETTINGS, "model_switch_threshold", 3), \
             patch.object(openai, "OpenAI", side_effect=capture_openai_client):

            backend._try_create_chat_completion_or_embedding(
                messages=[{"role": "user", "content": "test"}],
                chat_completion=True,
                max_retry=3,
                reasoning_flag=False,
            )

        assert requested_models == ["glm-4.7-flash", "glm-4.7-flash", "glm-4.7-flash"]
        assert client_base_urls == ["https://glm.test/v1", "https://glm.test/v1", "https://glm.test/v1"]


class TestProviderSwitchAfterThreeFailures:
    """Test that after 3 consecutive API failures, ProviderPool switching is attempted."""

    def test_switches_provider_after_three_api_failures(self):
        """After 3 failures on the same model, the next retry must attempt ProviderPool switching."""
        from quantaalpha.llm.client import LLM_SETTINGS, openai
        from quantaalpha.llm.provider_pool import ProviderPool

        pool = ProviderPool(routing="round_robin")
        pool.add_provider("provider-a", api_keys=["key-a"], base_url="https://a.com", model="model-a")
        pool.add_provider("provider-b", api_keys=["key-b"], base_url="https://b.com", model="model-b")

        backend = _make_minimal_backend()
        backend._provider_pool = pool

        call_count_holder = {"count": 0}
        mock_client = MagicMock()
        mock_client.chat.completions.create = _mock_create_fn(call_count_holder, fail_until=4)

        backend.chat_client = mock_client

        with patch.object(LLM_SETTINGS, "log_llm_chat_content", False), \
             patch.object(LLM_SETTINGS, "use_auto_chat_cache_seed_gen", False), \
             patch.object(LLM_SETTINGS, "max_retry", 10), \
             patch.object(LLM_SETTINGS, "chat_temperature", 0.7), \
             patch.object(LLM_SETTINGS, "chat_max_tokens", 1000), \
             patch.object(LLM_SETTINGS, "chat_frequency_penalty", 0.0), \
             patch.object(LLM_SETTINGS, "chat_presence_penalty", 0.0), \
             patch.object(LLM_SETTINGS, "model_switch_threshold", 3), \
             patch.object(openai, "OpenAI", return_value=mock_client):

            result = backend._try_create_chat_completion_or_embedding(
                messages=[{"role": "user", "content": "test"}],
                chat_completion=True,
                max_retry=10,
                reasoning_flag=False,  # Disable JSON extraction
            )

        # After implementation: should succeed after switch
        # Result can be a string or a dict with "content" key
        if isinstance(result, dict):
            assert result.get("content") == "success"
        else:
            assert result == "success"
        # Should have made at least 4 calls (3 failures + 1 success after switch)
        assert call_count_holder["count"] >= 4


class TestProviderSwitchAppliesModel:
    """Test that ProviderPool switching applies provider_config.model to the request."""

    def test_provider_switch_applies_provider_model_to_request(self):
        """When ProviderPool switches to a provider with model='m2', the actual request must use model='m2'."""
        from quantaalpha.llm.client import LLM_SETTINGS, openai
        from quantaalpha.llm.provider_pool import ProviderPool

        pool = ProviderPool(routing="round_robin")
        pool.add_provider("provider-a", api_keys=["key-a"], base_url="https://a.com", model="model-a")
        pool.add_provider("provider-b", api_keys=["key-b"], base_url="https://b.com", model="model-b")

        backend = _make_minimal_backend()
        backend._provider_pool = pool

        # Track what model was used in actual requests
        requested_models = []
        call_count_holder = {"count": 0}

        def track_create(**kwargs):
            requested_models.append(kwargs.get("model"))
            call_count_holder["count"] += 1
            # Fail first 3 times, then succeed
            if call_count_holder["count"] < 4:
                raise RuntimeError(f"Failure {call_count_holder['count']}")
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            mock_resp.choices[0].message.content = "ok"
            mock_resp.choices[0].finish_reason = "stop"
            return mock_resp

        mock_client = MagicMock()
        mock_client.chat.completions.create = track_create
        backend.chat_client = mock_client

        with patch.object(LLM_SETTINGS, "log_llm_chat_content", False), \
             patch.object(LLM_SETTINGS, "use_auto_chat_cache_seed_gen", False), \
             patch.object(LLM_SETTINGS, "max_retry", 10), \
             patch.object(LLM_SETTINGS, "chat_temperature", 0.7), \
             patch.object(LLM_SETTINGS, "chat_max_tokens", 1000), \
             patch.object(LLM_SETTINGS, "chat_frequency_penalty", 0.0), \
             patch.object(LLM_SETTINGS, "chat_presence_penalty", 0.0), \
             patch.object(LLM_SETTINGS, "model_switch_threshold", 3), \
             patch.object(openai, "OpenAI", return_value=mock_client):

            backend._try_create_chat_completion_or_embedding(
                messages=[{"role": "user", "content": "test"}],
                chat_completion=True,
                max_retry=10,
                reasoning_flag=False,
            )

        # After implementation: should have switched provider and used provider's model
        assert len(requested_models) >= 4, f"Expected at least 4 requests, got {len(requested_models)}"
        # After switch, should use provider-a's model (model-a), not the original chat_model
        assert "model-a" in requested_models[3:], (
            f"After provider switch, model-a should be used, got: {requested_models}"
        )

    def test_provider_switch_skips_same_model_when_first_provider_matches_current_model(self):
        """When current model is the first provider model, retry switch must choose another model."""
        from quantaalpha.llm.client import LLM_SETTINGS, openai
        from quantaalpha.llm.provider_pool import ProviderPool

        pool = ProviderPool(routing="round_robin")
        pool.add_provider("provider-current", api_keys=["key-a"], base_url="https://a.com", model="minimax-m2.7")
        pool.add_provider("provider-next", api_keys=["key-b"], base_url="https://b.com", model="codestral-latest")

        backend = _make_minimal_backend()
        backend.chat_model = "minimax-m2.7"
        backend._provider_pool = pool

        requested_models = []
        call_count_holder = {"count": 0}

        def track_create(**kwargs):
            requested_models.append(kwargs.get("model"))
            call_count_holder["count"] += 1
            if call_count_holder["count"] < 4:
                raise RuntimeError(f"Failure {call_count_holder['count']}")
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            mock_resp.choices[0].message.content = "ok"
            mock_resp.choices[0].finish_reason = "stop"
            return mock_resp

        mock_client = MagicMock()
        mock_client.chat.completions.create = track_create
        backend.chat_client = mock_client

        with patch.object(LLM_SETTINGS, "log_llm_chat_content", False), \
             patch.object(LLM_SETTINGS, "use_auto_chat_cache_seed_gen", False), \
             patch.object(LLM_SETTINGS, "max_retry", 10), \
             patch.object(LLM_SETTINGS, "chat_temperature", 0.7), \
             patch.object(LLM_SETTINGS, "chat_max_tokens", 1000), \
             patch.object(LLM_SETTINGS, "chat_frequency_penalty", 0.0), \
             patch.object(LLM_SETTINGS, "chat_presence_penalty", 0.0), \
             patch.object(LLM_SETTINGS, "model_switch_threshold", 3), \
             patch.object(openai, "OpenAI", return_value=mock_client):

            backend._try_create_chat_completion_or_embedding(
                messages=[{"role": "user", "content": "test"}],
                chat_completion=True,
                max_retry=10,
                reasoning_flag=False,
            )

        assert requested_models[:3] == ["minimax-m2.7", "minimax-m2.7", "minimax-m2.7"]
        assert requested_models[3] == "codestral-latest"

class TestProviderSwitchWithTaskTypeRouting:
    """Test that provider switching works even when task_type routing overrides chat_model."""

    def test_provider_switch_overrides_task_type_routing(self):
        """When call_structured uses task_type='factor_construction', the provider switch
        must still apply the provider's model, not the task_model_map or routing_default.
        """
        from quantaalpha.llm.client import LLM_SETTINGS, openai
        from quantaalpha.llm.provider_pool import ProviderPool

        pool = ProviderPool(routing="round_robin")
        pool.add_provider("provider-a", api_keys=["key-a"], base_url="https://a.com", model="model-a")
        pool.add_provider("provider-b", api_keys=["key-b"], base_url="https://b.com", model="model-b")

        backend = _make_minimal_backend()
        backend._provider_pool = pool
        # Simulate task_type routing that would normally override chat_model
        backend.task_model_map = {"factor_construction": "task-specific-model"}
        backend.routing_default = "routing-default-model"

        # Track what model was used in actual requests
        requested_models = []
        call_count_holder = {"count": 0}

        def track_create(**kwargs):
            requested_models.append(kwargs.get("model"))
            call_count_holder["count"] += 1
            if call_count_holder["count"] < 4:
                raise RuntimeError(f"Failure {call_count_holder['count']}")
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            mock_resp.choices[0].message.content = "ok"
            mock_resp.choices[0].finish_reason = "stop"
            return mock_resp

        mock_client = MagicMock()
        mock_client.chat.completions.create = track_create
        backend.chat_client = mock_client

        with patch.object(LLM_SETTINGS, "log_llm_chat_content", False), \
             patch.object(LLM_SETTINGS, "use_auto_chat_cache_seed_gen", False), \
             patch.object(LLM_SETTINGS, "max_retry", 10), \
             patch.object(LLM_SETTINGS, "chat_temperature", 0.7), \
             patch.object(LLM_SETTINGS, "chat_max_tokens", 1000), \
             patch.object(LLM_SETTINGS, "chat_frequency_penalty", 0.0), \
             patch.object(LLM_SETTINGS, "chat_presence_penalty", 0.0), \
             patch.object(LLM_SETTINGS, "model_switch_threshold", 3), \
             patch.object(openai, "OpenAI", return_value=mock_client):

            backend._try_create_chat_completion_or_embedding(
                messages=[{"role": "user", "content": "test"}],
                chat_completion=True,
                max_retry=10,
                reasoning_flag=False,
                task_type="factor_construction",
            )

        # After switch, model-a should be used, NOT task-specific-model or routing-default-model
        assert "model-a" in requested_models[3:], (
            f"After provider switch, 'model-a' should override task_type routing, "
            f"got: {requested_models}"
        )
        assert getattr(backend, "_current_retry_model", None) is None
        assert getattr(backend, "_current_retry_provider_name", None) is None
        assert backend.get_model_for_task(task_type="factor_construction") == "task-specific-model"


class TestRetryContextCleanup:
    """Test retry provider/model override does not leak after a retry cycle."""

    def test_retry_model_override_is_cleared_after_success(self):
        """A successful switched retry must not force later calls onto the retry model."""
        from quantaalpha.llm.client import LLM_SETTINGS, openai
        from quantaalpha.llm.provider_pool import ProviderPool

        pool = ProviderPool(routing="round_robin")
        pool.add_provider("provider-a", api_keys=["key-a"], base_url="https://a.com", model="model-a")
        pool.add_provider("provider-b", api_keys=["key-b"], base_url="https://b.com", model="model-b")

        backend = _make_minimal_backend()
        backend._provider_pool = pool
        backend.task_model_map = {"factor_construction": "task-specific-model"}
        backend.routing_default = "routing-default-model"

        requested_models = []
        call_count_holder = {"count": 0}

        def track_create(**kwargs):
            requested_models.append(kwargs.get("model"))
            call_count_holder["count"] += 1
            if call_count_holder["count"] < 4:
                raise RuntimeError(f"Failure {call_count_holder['count']}")
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            mock_resp.choices[0].message.content = "ok"
            mock_resp.choices[0].finish_reason = "stop"
            return mock_resp

        mock_client = MagicMock()
        mock_client.chat.completions.create = track_create
        backend.chat_client = mock_client

        with patch.object(LLM_SETTINGS, "log_llm_chat_content", False), \
             patch.object(LLM_SETTINGS, "use_auto_chat_cache_seed_gen", False), \
             patch.object(LLM_SETTINGS, "max_retry", 10), \
             patch.object(LLM_SETTINGS, "chat_temperature", 0.7), \
             patch.object(LLM_SETTINGS, "chat_max_tokens", 1000), \
             patch.object(LLM_SETTINGS, "chat_frequency_penalty", 0.0), \
             patch.object(LLM_SETTINGS, "chat_presence_penalty", 0.0), \
             patch.object(LLM_SETTINGS, "model_switch_threshold", 3), \
             patch.object(openai, "OpenAI", return_value=mock_client):

            backend._try_create_chat_completion_or_embedding(
                messages=[{"role": "user", "content": "test"}],
                chat_completion=True,
                max_retry=10,
                reasoning_flag=False,
                task_type="factor_construction",
            )

        assert requested_models[3] == "model-a"
        assert getattr(backend, "_current_retry_model", None) is None
        assert getattr(backend, "_current_retry_provider_name", None) is None
        assert backend.get_model_for_task(task_type="factor_construction") == "task-specific-model"


class TestStructuredParseFailuresCountTowardSwitch:
    """Test that structured parse failures count toward the model switch threshold."""

    def test_structured_parse_failures_count_toward_switch(self):
        """When call_structured JSON/tool-args parse fails repeatedly, provider switching must be attempted."""
        from quantaalpha.llm.client import LLM_SETTINGS, openai
        from quantaalpha.llm.provider_pool import ProviderPool

        pool = ProviderPool(routing="round_robin")
        pool.add_provider("provider-a", api_keys=["key-a"], base_url="https://a.com", model="model-a")
        pool.add_provider("provider-b", api_keys=["key-b"], base_url="https://b.com", model="model-b")

        backend = _make_minimal_backend()
        backend._provider_pool = pool

        # Track raw API calls
        raw_call_count = 0

        def mock_create(**kwargs):
            nonlocal raw_call_count
            raw_call_count += 1
            # Return a response with invalid JSON in tool_calls arguments
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            mock_resp.choices[0].message.content = ""
            mock_resp.choices[0].finish_reason = "tool_calls"
            mock_resp.choices[0].message.tool_calls = [
                MagicMock(
                    id="call_1",
                    function=MagicMock(
                        name="test_tool",
                        arguments="NOT_VALID_JSON{{{{",
                    ),
                )
            ]
            return mock_resp

        mock_client = MagicMock()
        mock_client.chat.completions.create = mock_create
        backend.chat_client = mock_client

        from quantaalpha.llm.client import call_structured

        tools = [{"type": "function", "function": {"name": "test_tool", "parameters": {"type": "object"}}}]
        messages = [{"role": "user", "content": "test"}]

        with patch.object(LLM_SETTINGS, "log_llm_chat_content", False), \
             patch.object(LLM_SETTINGS, "use_auto_chat_cache_seed_gen", False), \
             patch.object(LLM_SETTINGS, "use_tool_calling", True), \
             patch.object(LLM_SETTINGS, "structured_streaming_mode", False), \
             patch.object(LLM_SETTINGS, "max_retry", 5), \
             patch.object(LLM_SETTINGS, "model_switch_threshold", 3), \
             patch.object(openai, "OpenAI", return_value=mock_client):

            # After implementation: should retry multiple times before failing
            with pytest.raises(Exception):
                call_structured(
                    backend,
                    messages,
                    tools=tools,
                    tool_choice="required",
                    allow_text_fallback=False,
                )

        # After implementation: multiple calls should be made (retry + switch)
        assert raw_call_count > 1, f"Multiple calls expected after implementation, got {raw_call_count}"


class TestNoProviderPoolPreservesRetry:
    """Test that without ProviderPool, retry still works but no switching occurs."""

    def test_no_provider_pool_preserves_retry_failure(self):
        """Without ProviderPool, retry continues on the same model and eventually fails."""
        from quantaalpha.llm.client import LLM_SETTINGS

        backend = _make_minimal_backend()
        backend._provider_pool = None

        failure_count = 0

        def mock_create(**kwargs):
            nonlocal failure_count
            failure_count += 1
            raise RuntimeError(f"Simulated failure {failure_count}")

        backend.chat_client.chat.completions.create = mock_create

        with patch.object(LLM_SETTINGS, "log_llm_chat_content", False), \
             patch.object(LLM_SETTINGS, "use_auto_chat_cache_seed_gen", False), \
             patch.object(LLM_SETTINGS, "max_retry", 5), \
             patch.object(LLM_SETTINGS, "chat_temperature", 0.7), \
             patch.object(LLM_SETTINGS, "chat_max_tokens", 1000), \
             patch.object(LLM_SETTINGS, "chat_frequency_penalty", 0.0), \
             patch.object(LLM_SETTINGS, "chat_presence_penalty", 0.0), \
             patch.object(LLM_SETTINGS, "model_switch_threshold", 3):

            with pytest.raises(RuntimeError, match="Failed to create chat completion after 5 retries"):
                backend._try_create_chat_completion_or_embedding(
                    messages=[{"role": "user", "content": "test"}],
                    chat_completion=True,
                    max_retry=5,
                )

        # Should have tried exactly max_retry times
        assert failure_count == 5


class TestProviderAttemptLimit:
    """Test per-provider attempt caps within one retry operation."""

    def test_provider_attempt_limit_prevents_reusing_exhausted_provider(self):
        """A provider must not be used more than max_attempts_per_provider times in one request."""
        from quantaalpha.llm.client import LLM_SETTINGS, openai
        from quantaalpha.llm.provider_pool import ProviderPool

        pool = ProviderPool(routing="round_robin")
        pool.add_provider("provider-a", api_keys=["key-a"], base_url="https://a.com", model="model-a")
        pool.add_provider("provider-b", api_keys=["key-b"], base_url="https://b.com", model="model-b")
        pool.add_provider("provider-c", api_keys=["key-c"], base_url="https://c.com", model="model-c")

        backend = _make_minimal_backend()
        backend.chat_model = "model-a"
        backend._provider_pool = pool

        requested_models = []

        def track_create(**kwargs):
            requested_models.append(kwargs.get("model"))
            raise RuntimeError(f"Failure on {kwargs.get('model')}")

        mock_client = MagicMock()
        mock_client.chat.completions.create = track_create
        backend.chat_client = mock_client

        with patch.object(LLM_SETTINGS, "log_llm_chat_content", False), \
             patch.object(LLM_SETTINGS, "use_auto_chat_cache_seed_gen", False), \
             patch.object(LLM_SETTINGS, "max_retry", 10), \
             patch.object(LLM_SETTINGS, "chat_temperature", 0.7), \
             patch.object(LLM_SETTINGS, "chat_max_tokens", 1000), \
             patch.object(LLM_SETTINGS, "chat_frequency_penalty", 0.0), \
             patch.object(LLM_SETTINGS, "chat_presence_penalty", 0.0), \
             patch.object(LLM_SETTINGS, "model_switch_threshold", 3), \
             patch.object(LLM_SETTINGS, "max_attempts_per_provider", 3, create=True), \
             patch.object(openai, "OpenAI", return_value=mock_client):

            with pytest.raises(RuntimeError, match="all retry providers exhausted"):
                backend._try_create_chat_completion_or_embedding(
                    messages=[{"role": "user", "content": "test"}],
                    chat_completion=True,
                    max_retry=10,
                    reasoning_flag=False,
                )

        assert requested_models.count("model-a") <= 3
        assert requested_models.count("model-b") <= 3
        assert requested_models.count("model-c") <= 3

    def test_exhausted_providers_are_skipped_when_another_provider_remains(self):
        """Retry switching should move to an unexhausted provider instead of cycling back."""
        from quantaalpha.llm.client import LLM_SETTINGS, openai
        from quantaalpha.llm.provider_pool import ProviderPool

        pool = ProviderPool(routing="round_robin")
        pool.add_provider("provider-a", api_keys=["key-a"], base_url="https://a.com", model="model-a")
        pool.add_provider("provider-b", api_keys=["key-b"], base_url="https://b.com", model="model-b")
        pool.add_provider("provider-c", api_keys=["key-c"], base_url="https://c.com", model="model-c")

        backend = _make_minimal_backend()
        backend.chat_model = "model-a"
        backend._provider_pool = pool

        requested_models = []

        def track_create(**kwargs):
            requested_models.append(kwargs.get("model"))
            raise RuntimeError(f"Failure on {kwargs.get('model')}")

        mock_client = MagicMock()
        mock_client.chat.completions.create = track_create
        backend.chat_client = mock_client

        with patch.object(LLM_SETTINGS, "log_llm_chat_content", False), \
             patch.object(LLM_SETTINGS, "use_auto_chat_cache_seed_gen", False), \
             patch.object(LLM_SETTINGS, "max_retry", 7), \
             patch.object(LLM_SETTINGS, "chat_temperature", 0.7), \
             patch.object(LLM_SETTINGS, "chat_max_tokens", 1000), \
             patch.object(LLM_SETTINGS, "chat_frequency_penalty", 0.0), \
             patch.object(LLM_SETTINGS, "chat_presence_penalty", 0.0), \
             patch.object(LLM_SETTINGS, "model_switch_threshold", 3), \
             patch.object(LLM_SETTINGS, "max_attempts_per_provider", 3, create=True), \
             patch.object(openai, "OpenAI", return_value=mock_client):

            with pytest.raises(RuntimeError):
                backend._try_create_chat_completion_or_embedding(
                    messages=[{"role": "user", "content": "test"}],
                    chat_completion=True,
                    max_retry=7,
                    reasoning_flag=False,
                )

        assert requested_models == [
            "model-a",
            "model-a",
            "model-a",
            "model-b",
            "model-b",
            "model-b",
            "model-c",
        ]

    def test_all_providers_exhausted_fails_before_total_retry_budget(self):
        """When every provider is exhausted, retry should fail with provider counts."""
        from quantaalpha.llm.client import LLM_SETTINGS, openai
        from quantaalpha.llm.provider_pool import ProviderPool

        pool = ProviderPool(routing="round_robin")
        pool.add_provider("litellm_minimax", api_keys=["key-a"], base_url="https://a.com", model="minimax-m2.7")
        pool.add_provider("litellm_glm47f", api_keys=["key-b"], base_url="https://b.com", model="glm-4.7-flash")

        backend = _make_minimal_backend()
        backend.chat_model = "minimax-m2.7"
        backend._provider_pool = pool

        requested_models = []

        def track_create(**kwargs):
            requested_models.append(kwargs.get("model"))
            raise RuntimeError(f"Failure on {kwargs.get('model')}")

        mock_client = MagicMock()
        mock_client.chat.completions.create = track_create
        backend.chat_client = mock_client

        with patch.object(LLM_SETTINGS, "log_llm_chat_content", False), \
             patch.object(LLM_SETTINGS, "use_auto_chat_cache_seed_gen", False), \
             patch.object(LLM_SETTINGS, "max_retry", 18), \
             patch.object(LLM_SETTINGS, "chat_temperature", 0.7), \
             patch.object(LLM_SETTINGS, "chat_max_tokens", 1000), \
             patch.object(LLM_SETTINGS, "chat_frequency_penalty", 0.0), \
             patch.object(LLM_SETTINGS, "chat_presence_penalty", 0.0), \
             patch.object(LLM_SETTINGS, "model_switch_threshold", 3), \
             patch.object(LLM_SETTINGS, "max_attempts_per_provider", 3, create=True), \
             patch.object(openai, "OpenAI", return_value=mock_client):

            with pytest.raises(RuntimeError) as exc_info:
                backend._try_create_chat_completion_or_embedding(
                    messages=[{"role": "user", "content": "test"}],
                    chat_completion=True,
                    max_retry=18,
                    reasoning_flag=False,
                )

        assert requested_models == [
            "minimax-m2.7",
            "minimax-m2.7",
            "minimax-m2.7",
            "glm-4.7-flash",
            "glm-4.7-flash",
            "glm-4.7-flash",
        ]
        error_message = str(exc_info.value)
        assert "all retry providers exhausted" in error_message
        assert "max_attempts_per_provider=3" in error_message
        assert "'litellm_minimax': 3" in error_message
        assert "'litellm_glm47f': 3" in error_message

    def test_unset_provider_attempt_limit_preserves_existing_retry_behavior(self):
        """Without max_attempts_per_provider, retry may revisit a provider after switching."""
        from quantaalpha.llm.client import LLM_SETTINGS, openai
        from quantaalpha.llm.provider_pool import ProviderPool

        pool = ProviderPool(routing="round_robin")
        pool.add_provider("provider-a", api_keys=["key-a"], base_url="https://a.com", model="model-a")
        pool.add_provider("provider-b", api_keys=["key-b"], base_url="https://b.com", model="model-b")

        backend = _make_minimal_backend()
        backend.chat_model = "model-a"
        backend._provider_pool = pool

        requested_models = []

        def track_create(**kwargs):
            requested_models.append(kwargs.get("model"))
            raise RuntimeError(f"Failure on {kwargs.get('model')}")

        mock_client = MagicMock()
        mock_client.chat.completions.create = track_create
        backend.chat_client = mock_client

        with patch.object(LLM_SETTINGS, "log_llm_chat_content", False), \
             patch.object(LLM_SETTINGS, "use_auto_chat_cache_seed_gen", False), \
             patch.object(LLM_SETTINGS, "max_retry", 7), \
             patch.object(LLM_SETTINGS, "chat_temperature", 0.7), \
             patch.object(LLM_SETTINGS, "chat_max_tokens", 1000), \
             patch.object(LLM_SETTINGS, "chat_frequency_penalty", 0.0), \
             patch.object(LLM_SETTINGS, "chat_presence_penalty", 0.0), \
             patch.object(LLM_SETTINGS, "model_switch_threshold", 3), \
             patch.object(LLM_SETTINGS, "max_attempts_per_provider", None, create=True), \
             patch.object(openai, "OpenAI", return_value=mock_client):

            with pytest.raises(RuntimeError, match="Failed to create chat completion after 7 retries"):
                backend._try_create_chat_completion_or_embedding(
                    messages=[{"role": "user", "content": "test"}],
                    chat_completion=True,
                    max_retry=7,
                    reasoning_flag=False,
                )

        assert requested_models.count("model-a") > 3


class TestDefaultProviderPoolInjection:
    """Test that default ProviderPool is used when not explicitly passed."""

    def test_default_pool_used_by_new_backend(self):
        """After set_default_provider_pool, new APIBackend instances use the default pool."""
        from quantaalpha.llm.client import APIBackend, get_default_provider_pool, set_default_provider_pool
        from quantaalpha.llm.provider_pool import ProviderPool

        pool = ProviderPool()
        set_default_provider_pool(pool)
        try:
            assert get_default_provider_pool() is pool
            # New backend without explicit pool should use default
            with patch("quantaalpha.llm.client.openai.OpenAI", return_value=MagicMock()):
                backend = APIBackend()
                assert backend._provider_pool is pool
        finally:
            set_default_provider_pool(None)

    def test_explicit_pool_overrides_default(self):
        """Explicit provider_pool parameter overrides the default pool."""
        from quantaalpha.llm.client import APIBackend, set_default_provider_pool
        from quantaalpha.llm.provider_pool import ProviderPool

        pool1 = ProviderPool()
        pool2 = ProviderPool()

        set_default_provider_pool(pool1)
        try:
            with patch("quantaalpha.llm.client.openai.OpenAI", return_value=MagicMock()):
                backend = APIBackend(provider_pool=pool2)
                assert backend._provider_pool is pool2
                assert backend._provider_pool is not pool1
        finally:
            set_default_provider_pool(None)
