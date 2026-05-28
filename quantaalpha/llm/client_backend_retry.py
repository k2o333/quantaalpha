from __future__ import annotations

from .client_shared import *
from .client_shared import (
    _ProviderAttempt,
    _coerce_int_setting,
    _escape_common_json_sequences,
    _is_tool_call_capability_failure,
)
from .client_sessions import ChatSession, SQliteLazyCache


class BackendRetryMixin:
    """Responsibility slice for APIBackend."""

    def _select_provider_attempt(
        self,
        *,
        avoid_provider_name: str | None = None,
        avoid_model: str | None = None,
        avoid_provider_names: set[str] | None = None,
        avoid_models: set[str] | None = None,
    ) -> _ProviderAttempt | None:
        """Select a provider from the pool, optionally avoiding a specific provider."""
        pool = getattr(self, "_provider_pool", None)
        if pool is None:
            return None

        providers = pool.get_providers()
        if not providers:
            return None

        # Try to find a different provider
        for provider_name in providers:
            if avoid_provider_name and provider_name == avoid_provider_name:
                continue
            if avoid_provider_names and provider_name in avoid_provider_names:
                continue
            api_key, provider_config = pool.get_key_and_provider(provider_name=provider_name)
            if api_key and provider_config:
                if avoid_model and provider_config.model == avoid_model:
                    continue
                if avoid_models and provider_config.model in avoid_models:
                    continue
                return _ProviderAttempt(
                    provider_name=provider_config.name,
                    api_key=api_key,
                    base_url=provider_config.base_url,
                    model=provider_config.model,
                )

        if avoid_provider_name or avoid_model or avoid_provider_names or avoid_models:
            return None

        # Fall back to any provider if no constraints were requested.
        api_key, provider_config = pool.get_key_and_provider()
        if api_key and provider_config:
            return _ProviderAttempt(
                provider_name=provider_config.name,
                api_key=api_key,
                base_url=provider_config.base_url,
                model=provider_config.model,
            )
        return None

    def _apply_provider_attempt_to_chat_kwargs(
        self,
        attempt: _ProviderAttempt,
    ) -> None:
        """Apply a provider attempt to the backend state and recreate the client."""
        if attempt.model:
            # Override the chat_model for subsequent calls
            self.chat_model = attempt.model
            # CRITICAL: Also set the retry model override so get_model_for_task
            # returns this model even when task_type or tag-based routing is used.
            self._current_retry_model = attempt.model
        if attempt.provider_name:
            self._current_retry_provider_name = attempt.provider_name
        if attempt.api_key:
            self.chat_client = self._create_openai_client(
                api_key=attempt.api_key,
                base_url=attempt.base_url or self.base_url,
            )

    def _switch_to_next_provider_for_retry(
        self,
        *,
        current_provider_name: str | None = None,
        current_model: str | None = None,
        exhausted_provider_names: set[str] | None = None,
        exhausted_models: set[str] | None = None,
    ) -> str | None:
        """Attempt to switch to a different provider for retry.

        Returns the new provider name if switched, None otherwise.
        """
        pool = getattr(self, "_provider_pool", None)
        if pool is None:
            logger.warning("No ProviderPool configured; continue retrying current model.")
            return None

        attempt = self._select_provider_attempt(
            avoid_provider_name=current_provider_name,
            avoid_model=current_model,
            avoid_provider_names=exhausted_provider_names,
            avoid_models=exhausted_models,
        )
        if attempt is None:
            logger.warning("ProviderPool cannot produce another provider; continue retrying current model.")
            return None

        # Apply the new provider
        self._apply_provider_attempt_to_chat_kwargs(attempt)
        logger.info(f"[retry] Switched provider for retry: from={current_provider_name} to={attempt.provider_name} model={attempt.model}")
        return attempt.provider_name

    def _get_retry_provider_key(
        self,
        *,
        task_type: str | None = None,
        tag: str | None = None,
    ) -> tuple[str, str | None]:
        """Return the provider/model identity for per-request retry accounting."""
        provider_name = getattr(self, "_current_retry_provider_name", None)
        model = self.get_model_for_task(task_type=task_type, tag=tag)
        if provider_name:
            return provider_name, model
        resolved_provider = self._get_provider_name_for_model(model)
        return resolved_provider or model or "<unknown>", model

    def _run_with_retry_and_model_switch(
        self,
        operation: Callable[[], Any],
        *,
        max_retry: int,
        retry_label: str,
        chat_completion: bool = False,
        embedding: bool = False,
        retry_kwargs: dict[str, Any] | None = None,
        switch_model_on_failure: bool = False,
        **kwargs: Any,
    ) -> Any:
        """Execute an operation with retry logic and model switching.

        This is the unified retry helper that handles both API failures
        and structured parse failures through the same counter.
        """
        retry_call_id = uuid.uuid4().hex[:8]
        threshold = _coerce_int_setting(getattr(LLM_SETTINGS, "model_switch_threshold", 3), 3, minimum=1)
        if switch_model_on_failure:
            threshold = 1
        current_provider_name: str | None = None
        attempt_count = 0
        provider_pool_available = getattr(self, "_provider_pool", None) is not None
        max_attempts_per_provider = _coerce_int_setting(
            getattr(LLM_SETTINGS, "max_attempts_per_provider", None),
            None,
            minimum=1,
        )
        if switch_model_on_failure and provider_pool_available:
            max_attempts_per_provider = 1
        attempts_by_provider: dict[str, int] = {}
        exhausted_provider_names: set[str] = set()
        exhausted_models: set[str] = set()
        previous_retry_model = getattr(self, "_current_retry_model", None)
        previous_retry_provider_name = getattr(self, "_current_retry_provider_name", None)
        mutable_retry_kwargs = retry_kwargs if retry_kwargs is not None else kwargs

        def _provider_exhaustion_error() -> RuntimeError:
            return RuntimeError(f"Failed to create {retry_label}: all retry providers exhausted retry_call_id={retry_call_id} before {max_retry} total retries. max_attempts_per_provider={max_attempts_per_provider}, provider_attempts={attempts_by_provider}")

        def _mark_provider_exhausted(provider_key: str, model: str | None) -> None:
            if not provider_pool_available or not max_attempts_per_provider:
                return
            if attempts_by_provider.get(provider_key, 0) < max_attempts_per_provider:
                return
            exhausted_provider_names.add(provider_key)
            if model:
                exhausted_models.add(model)
            logger.warning(f"[retry] Provider exhausted for this request: retry_call_id={retry_call_id} provider={provider_key} model={model} attempts={attempts_by_provider.get(provider_key)} max_attempts_per_provider={max_attempts_per_provider}")

        try:
            for i in range(max_retry):
                provider_key, provider_model = self._get_retry_provider_key(
                    task_type=mutable_retry_kwargs.get("task_type"),
                    tag=mutable_retry_kwargs.get("tag"),
                )
                if provider_pool_available and max_attempts_per_provider and provider_key in exhausted_provider_names:
                    new_provider_name = self._switch_to_next_provider_for_retry(
                        current_provider_name=current_provider_name,
                        current_model=provider_model,
                        exhausted_provider_names=exhausted_provider_names,
                        exhausted_models=exhausted_models,
                    )
                    if new_provider_name is None:
                        raise _provider_exhaustion_error()
                    attempt_count = 0
                    current_provider_name = new_provider_name
                    provider_key, provider_model = self._get_retry_provider_key(
                        task_type=mutable_retry_kwargs.get("task_type"),
                        tag=mutable_retry_kwargs.get("tag"),
                    )

                try:
                    attempt_count += 1
                    attempts_by_provider[provider_key] = attempts_by_provider.get(provider_key, 0) + 1
                    return operation()
                except openai.BadRequestError as e:  # noqa: PERF203
                    error_str = str(e)
                    logger.warning(e)
                    # Unrecoverable: invalid model name — fail fast, no retry
                    if "Invalid model" in error_str:
                        failing_model = self.embedding_model if embedding else self.chat_model
                        logger.error(f"Unrecoverable BadRequest: invalid model '{failing_model}'. Check model configuration.")
                        raise
                    logger.warning(f"[retry] Retrying {i + 1}th time... retry_call_id={retry_call_id} provider={provider_key} model={provider_model}")
                    if "'messages' must contain the word 'json' in some form" in error_str:
                        mutable_retry_kwargs["add_json_in_prompt"] = True
                    elif embedding and "maximum context length" in error_str:
                        mutable_retry_kwargs["input_content_list"] = [content[: len(content) // 2] for content in mutable_retry_kwargs.get("input_content_list", [])]
                except StructuredSchemaError as e:
                    logger.warning(f"[retry] Structured schema failure: retry_call_id={retry_call_id} provider={provider_key} model={provider_model} top_level_type={e.top_level_type}; retrying {i + 1}th time...")
                except Exception as e:  # noqa: BLE001
                    if _is_tool_call_capability_failure(e) and (not switch_model_on_failure or not provider_pool_available):
                        logger.warning(f"[retry] Tool-call capability failure is not retried in this call: retry_call_id={retry_call_id} provider={provider_key} model={provider_model}")
                        raise
                    logger.warning(e)
                    logger.warning(f"[retry] Retrying {i + 1}th time... retry_call_id={retry_call_id} provider={provider_key} model={provider_model}")

                _mark_provider_exhausted(provider_key, provider_model)

                # Check if we should switch providers
                provider_exhausted = provider_pool_available and max_attempts_per_provider and provider_key in exhausted_provider_names
                if (attempt_count >= threshold or provider_exhausted) and i < max_retry - 1:
                    current_model = self.get_model_for_task(
                        task_type=mutable_retry_kwargs.get("task_type"),
                        tag=mutable_retry_kwargs.get("tag"),
                    )
                    new_provider_name = self._switch_to_next_provider_for_retry(
                        current_provider_name=current_provider_name,
                        current_model=current_model,
                        exhausted_provider_names=exhausted_provider_names,
                        exhausted_models=exhausted_models,
                    )
                    if new_provider_name is not None:
                        # Reset counter after successful switch
                        attempt_count = 0
                        current_provider_name = new_provider_name
                    elif provider_exhausted:
                        raise _provider_exhaustion_error()

                # Wait before retry
                if i < max_retry - 1:
                    time.sleep(getattr(self, "retry_wait_seconds", 15))

            error_message = f"Failed to create {retry_label} after {max_retry} retries. retry_call_id={retry_call_id}"
            raise RuntimeError(error_message)
        finally:
            if previous_retry_model is None:
                if hasattr(self, "_current_retry_model"):
                    delattr(self, "_current_retry_model")
            else:
                self._current_retry_model = previous_retry_model
            if previous_retry_provider_name is None:
                if hasattr(self, "_current_retry_provider_name"):
                    delattr(self, "_current_retry_provider_name")
            else:
                self._current_retry_provider_name = previous_retry_provider_name

    def _try_create_chat_completion_or_embedding(
        self,
        max_retry: int = 10,
        *,
        chat_completion: bool = False,
        embedding: bool = False,
        **kwargs: Any,
    ) -> Any:
        assert not (chat_completion and embedding), "chat_completion and embedding cannot be True at the same time"
        max_retry_setting = getattr(self, "_max_retry_override", None)
        if max_retry_setting is None:
            max_retry_setting = getattr(LLM_SETTINGS, "max_retry", None)
        max_retry = _coerce_int_setting(max_retry_setting, max_retry, minimum=1)

        def operation() -> Any:
            return self._create_chat_completion_or_embedding_once(
                chat_completion=chat_completion,
                embedding=embedding,
                **kwargs,
            )

        return self._run_with_retry_and_model_switch(
            operation,
            max_retry=max_retry,
            retry_label="chat completion" if chat_completion else "embedding",
            chat_completion=chat_completion,
            embedding=embedding,
            retry_kwargs=kwargs,
            **kwargs,
        )
