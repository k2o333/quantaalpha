"""Structured LLM retry hardening regressions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def _make_backend():
    """Create a minimal APIBackend instance for structured retry tests."""
    from quantaalpha.llm.client import APIBackend

    backend = object.__new__(APIBackend)
    backend.use_azure = False
    backend.use_llama2 = False
    backend.use_gcr_endpoint = False
    backend.chat_stream = True
    backend.use_chat_cache = False
    backend.dump_chat_cache = False
    backend.chat_model = "model-a"
    backend.reasoning_model = ""
    backend.chat_client = MagicMock()
    backend.cache = MagicMock()
    backend.cache.chat_get.return_value = None
    backend.task_model_map = {}
    backend.routing_default = ""
    backend.chat_model_map = {}
    backend.chat_api_key = "test-key"
    backend.base_url = "https://api.test/v1"
    backend.embedding_api_key = ""
    backend.embedding_base_url = None
    backend.encoder = None
    backend.chat_seed = None
    backend.retry_wait_seconds = 0
    backend._provider_pool = None
    backend._request_timeout_seconds = None
    backend._max_retry_override = None
    backend.get_model_for_task = APIBackend.get_model_for_task.__get__(backend, APIBackend)
    backend._get_retry_provider_key = APIBackend._get_retry_provider_key.__get__(backend, APIBackend)
    backend._switch_to_next_provider_for_retry = APIBackend._switch_to_next_provider_for_retry.__get__(backend, APIBackend)
    return backend


def _patch_structured_settings(max_retry: int = 2):
    from quantaalpha.llm.client import LLM_SETTINGS

    return patch.multiple(
        LLM_SETTINGS,
        use_tool_calling=True,
        structured_streaming_mode=False,
        max_retry=max_retry,
        model_switch_threshold=10,
        max_attempts_per_provider=None,
        log_llm_chat_content=False,
    )


def test_list_shaped_content_is_retryable_or_normalized_before_return():
    """A top-level list parsed from content must not escape call_structured."""
    from quantaalpha.llm.client import call_structured

    backend = _make_backend()
    backend._create_chat_completion_or_embedding_once = MagicMock(
        side_effect=[
            {
                "content": (
                    '[{"name":"propose_hypothesis",'
                    '"parameters":{"hypothesis":"bad-list-wrapper"}}]'
                ),
                "finish_reason": "stop",
                "tool_calls": None,
            },
            {
                "content": (
                    '{"hypothesis":"x","concise_observation":"o",'
                    '"concise_knowledge":"k","concise_justification":"j",'
                    '"concise_specification":"s"}'
                ),
                "finish_reason": "stop",
                "tool_calls": None,
            },
        ]
    )

    with _patch_structured_settings(max_retry=2):
        result = call_structured(
            backend,
            [{"role": "user", "content": "return hypothesis JSON"}],
            tools=[{"type": "function", "function": {"name": "propose_hypothesis"}}],
            tool_choice="required",
            allow_text_fallback=True,
        )

    assert result == {
        "hypothesis": "x",
        "concise_observation": "o",
        "concise_knowledge": "k",
        "concise_justification": "j",
        "concise_specification": "s",
    }
    assert backend._create_chat_completion_or_embedding_once.call_count == 2


def test_call_structured_keeps_tool_requests_non_streaming_by_default():
    """Structured tool-call requests must use the non-streaming policy for now."""
    from quantaalpha.llm.client import call_structured

    backend = _make_backend()

    def _capture(**kwargs):
        assert backend.chat_stream is False
        assert kwargs["tools"] is not None
        return {
            "content": None,
            "finish_reason": "tool_calls",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "emit_json", "arguments": '{"result":"ok"}'},
                }
            ],
        }

    backend._create_chat_completion_or_embedding_once = MagicMock(side_effect=_capture)

    with _patch_structured_settings(max_retry=1):
        result = call_structured(
            backend,
            [{"role": "user", "content": "return JSON"}],
            tools=[{"type": "function", "function": {"name": "emit_json"}}],
            tool_choice="required",
        )

    assert result == {"result": "ok"}
    assert backend.chat_stream is True


def test_invalid_tool_arguments_switches_model_before_retrying():
    """Malformed tool-call arguments consume the current model and switch to another one."""
    from quantaalpha.llm.client import call_structured
    from quantaalpha.llm.provider_pool import ProviderPool

    pool = ProviderPool(routing="round_robin")
    pool.add_provider("provider-a", api_keys=["key-a"], base_url="https://a.test/v1", model="model-a")
    pool.add_provider("provider-b", api_keys=["key-b"], base_url="https://b.test/v1", model="model-b")

    backend = _make_backend()
    backend._provider_pool = pool
    backend._create_openai_client = MagicMock(return_value=backend.chat_client)
    attempted_models = []

    def _capture(**kwargs):
        attempted_models.append(backend.get_model_for_task())
        if len(attempted_models) == 1:
            return {
                "content": "",
                "finish_reason": "tool_calls",
                "tool_calls": [
                    {
                        "id": "call_bad",
                        "type": "function",
                        "function": {"name": "emit_json", "arguments": "NOT_JSON{{"},
                    }
                ],
            }
        return {
            "content": None,
            "finish_reason": "tool_calls",
            "tool_calls": [
                {
                    "id": "call_ok",
                    "type": "function",
                    "function": {"name": "emit_json", "arguments": '{"result":"ok"}'},
                }
            ],
        }

    backend._create_chat_completion_or_embedding_once = MagicMock(side_effect=_capture)

    with _patch_structured_settings(max_retry=3):
        result = call_structured(
            backend,
            [{"role": "user", "content": "return JSON"}],
            tools=[{"type": "function", "function": {"name": "emit_json"}}],
            tool_choice="required",
            allow_text_fallback=False,
        )

    assert result == {"result": "ok"}
    assert attempted_models == ["model-a", "model-b"]


def test_missing_tool_call_with_valid_content_json_does_not_switch_model():
    """A valid text-JSON payload in the same response satisfies the structured call."""
    from quantaalpha.llm.client import call_structured
    from quantaalpha.llm.provider_pool import ProviderPool

    pool = ProviderPool(routing="round_robin")
    pool.add_provider("provider-a", api_keys=["key-a"], base_url="https://a.test/v1", model="model-a")
    pool.add_provider("provider-b", api_keys=["key-b"], base_url="https://b.test/v1", model="model-b")

    backend = _make_backend()
    backend._provider_pool = pool
    backend._create_openai_client = MagicMock(return_value=backend.chat_client)
    attempted_models = []

    def _capture(**kwargs):
        attempted_models.append(backend.get_model_for_task())
        return {
            "content": '{"result":"content-json"}',
            "finish_reason": "stop",
            "tool_calls": None,
        }

    backend._create_chat_completion_or_embedding_once = MagicMock(side_effect=_capture)

    with _patch_structured_settings(max_retry=3):
        result = call_structured(
            backend,
            [{"role": "user", "content": "return JSON"}],
            tools=[{"type": "function", "function": {"name": "emit_json"}}],
            tool_choice="required",
            allow_text_fallback=True,
        )

    assert result == {"result": "content-json"}
    assert attempted_models == ["model-a"]


def test_tool_call_capability_failure_switches_model():
    """Tool-call capability failures must switch model instead of terminating the request."""
    from quantaalpha.llm.client import call_structured
    from quantaalpha.llm.provider_pool import ProviderPool

    pool = ProviderPool(routing="round_robin")
    pool.add_provider("provider-a", api_keys=["key-a"], base_url="https://a.test/v1", model="model-a")
    pool.add_provider("provider-b", api_keys=["key-b"], base_url="https://b.test/v1", model="model-b")

    backend = _make_backend()
    backend._provider_pool = pool
    backend._create_openai_client = MagicMock(return_value=backend.chat_client)
    attempted_models = []

    def _capture(**kwargs):
        attempted_models.append(backend.get_model_for_task())
        if len(attempted_models) == 1:
            raise RuntimeError("tools parameter is not supported by this model")
        return {
            "content": None,
            "finish_reason": "tool_calls",
            "tool_calls": [
                {
                    "id": "call_ok",
                    "type": "function",
                    "function": {"name": "emit_json", "arguments": '{"result":"ok"}'},
                }
            ],
        }

    backend._create_chat_completion_or_embedding_once = MagicMock(side_effect=_capture)

    with _patch_structured_settings(max_retry=3):
        result = call_structured(
            backend,
            [{"role": "user", "content": "return JSON"}],
            tools=[{"type": "function", "function": {"name": "emit_json"}}],
            tool_choice="required",
            allow_text_fallback=True,
        )

    assert result == {"result": "ok"}
    assert attempted_models == ["model-a", "model-b"]
