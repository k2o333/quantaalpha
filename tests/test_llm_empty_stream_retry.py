from __future__ import annotations

from types import SimpleNamespace

import pytest

from quantaalpha.llm import client as llm_client


@pytest.fixture(autouse=True)
def _disable_chat_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_client.LLM_SETTINGS, "log_llm_chat_content", False)


def _make_backend_with_stream(stream_responses: list[list[SimpleNamespace]]) -> llm_client.APIBackend:
    backend = object.__new__(llm_client.APIBackend)
    backend.use_chat_cache = False
    backend.dump_chat_cache = False
    backend.use_llama2 = False
    backend.use_gcr_endpoint = False
    backend.chat_stream = True
    backend.chat_seed = None
    backend.reasoning_model = "reasoning-model"
    backend.chat_model = "chat-model"
    backend.get_model_for_task = lambda task_type=None, tag=None: "chat-model"
    backend.retry_wait_seconds = 0
    backend.task_model_map = {}
    backend.chat_model_map = {}
    backend.routing_default = "chat-model"
    completions = SimpleNamespace(create=lambda **kwargs: stream_responses.pop(0))
    backend.chat_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return backend


def _stream_chunk(content: str | None = None, finish_reason: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=content), finish_reason=finish_reason)]
    )


def test_empty_stream_response_raises_retryable_error() -> None:
    backend = _make_backend_with_stream([[_stream_chunk(None, "stop")]])

    with pytest.raises(llm_client.EmptyLLMResponseError):
        backend._create_chat_completion_inner_function(
            messages=[{"role": "system", "content": "s"}, {"role": "user", "content": "u"}],
            reasoning_flag=False,
            json_mode=True,
        )


def test_retry_wrapper_retries_on_empty_stream_response() -> None:
    backend = object.__new__(llm_client.APIBackend)
    backend.retry_wait_seconds = 0
    attempts = {"n": 0}

    def _fake_auto_continue(**kwargs):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise llm_client.EmptyLLMResponseError("empty")
        return '{"ok": true}'

    backend._create_chat_completion_auto_continue = _fake_auto_continue

    result = backend._try_create_chat_completion_or_embedding(
        chat_completion=True,
        max_retry=2,
        messages=[{"role": "system", "content": "s"}, {"role": "user", "content": "u"}],
    )

    assert result == '{"ok": true}'
    assert attempts["n"] == 2
