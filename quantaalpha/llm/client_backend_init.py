from __future__ import annotations

from .client_shared import *
from .client_shared import (
    _ProviderAttempt,
    _coerce_int_setting,
    _escape_common_json_sequences,
    _is_tool_call_capability_failure,
)
from .client_sessions import ChatSession, SQliteLazyCache


class BackendInitMixin:
    """Responsibility slice for APIBackend."""

    def __init__(  # noqa: C901, PLR0912, PLR0915
        self,
        *,
        chat_api_key: str | None = None,
        chat_model: str | None = None,
        reasoning_model: str | None = None,
        chat_api_base: str | None = None,
        chat_api_version: str | None = None,
        embedding_api_key: str | None = None,
        embedding_model: str | None = None,
        embedding_api_base: str | None = None,
        embedding_api_version: str | None = None,
        use_chat_cache: bool | None = None,
        dump_chat_cache: bool | None = None,
        use_embedding_cache: bool | None = None,
        dump_embedding_cache: bool | None = None,
        provider_pool: "ProviderPool | None" = None,
    ) -> None:
        if LLM_SETTINGS.use_llama2:
            self.generator = Llama.build(
                ckpt_dir=LLM_SETTINGS.llama2_ckpt_dir,
                tokenizer_path=LLM_SETTINGS.llama2_tokenizer_path,
                max_seq_len=LLM_SETTINGS.max_tokens,
                max_batch_size=LLM_SETTINGS.llams2_max_batch_size,
            )
            self.encoder = None
        elif LLM_SETTINGS.use_gcr_endpoint:
            gcr_endpoint_type = LLM_SETTINGS.gcr_endpoint_type
            if gcr_endpoint_type == "llama2_70b":
                self.gcr_endpoint_key = LLM_SETTINGS.llama2_70b_endpoint_key
                self.gcr_endpoint_deployment = LLM_SETTINGS.llama2_70b_endpoint_deployment
                self.gcr_endpoint = LLM_SETTINGS.llama2_70b_endpoint
            elif gcr_endpoint_type == "llama3_70b":
                self.gcr_endpoint_key = LLM_SETTINGS.llama3_70b_endpoint_key
                self.gcr_endpoint_deployment = LLM_SETTINGS.llama3_70b_endpoint_deployment
                self.gcr_endpoint = LLM_SETTINGS.llama3_70b_endpoint
            elif gcr_endpoint_type == "phi2":
                self.gcr_endpoint_key = LLM_SETTINGS.phi2_endpoint_key
                self.gcr_endpoint_deployment = LLM_SETTINGS.phi2_endpoint_deployment
                self.gcr_endpoint = LLM_SETTINGS.phi2_endpoint
            elif gcr_endpoint_type == "phi3_4k":
                self.gcr_endpoint_key = LLM_SETTINGS.phi3_4k_endpoint_key
                self.gcr_endpoint_deployment = LLM_SETTINGS.phi3_4k_endpoint_deployment
                self.gcr_endpoint = LLM_SETTINGS.phi3_4k_endpoint
            elif gcr_endpoint_type == "phi3_128k":
                self.gcr_endpoint_key = LLM_SETTINGS.phi3_128k_endpoint_key
                self.gcr_endpoint_deployment = LLM_SETTINGS.phi3_128k_endpoint_deployment
                self.gcr_endpoint = LLM_SETTINGS.phi3_128k_endpoint
            else:
                error_message = f"Invalid gcr_endpoint_type: {gcr_endpoint_type}"
                raise ValueError(error_message)
            self.headers = {
                "Content-Type": "application/json",
                "Authorization": ("Bearer " + self.gcr_endpoint_key),
            }
            self.gcr_endpoint_temperature = LLM_SETTINGS.gcr_endpoint_temperature
            self.gcr_endpoint_top_p = LLM_SETTINGS.gcr_endpoint_top_p
            self.gcr_endpoint_do_sample = LLM_SETTINGS.gcr_endpoint_do_sample
            self.gcr_endpoint_max_token = LLM_SETTINGS.gcr_endpoint_max_token
            if not os.environ.get("PYTHONHTTPSVERIFY", "") and hasattr(ssl, "_create_unverified_context"):
                ssl._create_default_https_context = ssl._create_unverified_context  # noqa: SLF001
            self.chat_model_map = json.loads(LLM_SETTINGS.chat_model_map)
            self.chat_model = LLM_SETTINGS.chat_model if chat_model is None else chat_model
            self.task_model_map = parse_routing_tasks(LLM_SETTINGS.routing_tasks)
            self.routing_default = LLM_SETTINGS.routing_default or self.chat_model
            self.encoder = None
        else:
            self.use_azure = LLM_SETTINGS.use_azure
            self.chat_use_azure_token_provider = LLM_SETTINGS.chat_use_azure_token_provider
            self.embedding_use_azure_token_provider = LLM_SETTINGS.embedding_use_azure_token_provider
            self.managed_identity_client_id = LLM_SETTINGS.managed_identity_client_id

            # Priority: chat_api_key/embedding_api_key > openai_api_key > os.environ.get("OPENAI_API_KEY")
            # TODO: Simplify the key design. Consider Pandatic's field alias & priority.
            self.chat_api_key = chat_api_key or LLM_SETTINGS.chat_openai_api_key or LLM_SETTINGS.openai_api_key or os.environ.get("OPENAI_API_KEY")
            self.embedding_api_key = embedding_api_key or LLM_SETTINGS.embedding_openai_api_key or LLM_SETTINGS.openai_api_key or os.environ.get("OPENAI_API_KEY")

            self.base_url = LLM_SETTINGS.openai_base_url or os.environ.get("OPENAI_BASE_URL")

            self.embedding_base_url = LLM_SETTINGS.embedding_base_url or os.environ.get("EMBEDDING_BASE_URL")

            self.embedding_api_key = LLM_SETTINGS.embedding_api_key or os.environ.get("EMBEDDING_API_KEY")

            self.chat_model = LLM_SETTINGS.chat_model if chat_model is None else chat_model
            self.reasoning_model = LLM_SETTINGS.reasoning_model if reasoning_model is None else reasoning_model
            self.chat_model_map = json.loads(LLM_SETTINGS.chat_model_map)
            self.task_model_map = parse_routing_tasks(LLM_SETTINGS.routing_tasks)
            self.routing_default = LLM_SETTINGS.routing_default or self.chat_model
            if should_skip_tokenizer_lookup(self.chat_model):
                log_tokenizer_fallback_once(
                    self.chat_model,
                    "configured to skip model-specific tokenizer lookup",
                )
                self.encoder = tiktoken.get_encoding(DEFAULT_FALLBACK_TOKENIZER)
            else:
                try:
                    self.encoder = self._get_encoder()
                except Exception as exc:  # noqa: BLE001
                    log_tokenizer_fallback_once(self.chat_model, str(exc))
                    self.encoder = tiktoken.get_encoding(DEFAULT_FALLBACK_TOKENIZER)

            self.chat_api_base = LLM_SETTINGS.chat_azure_api_base if chat_api_base is None else chat_api_base
            self.chat_api_version = LLM_SETTINGS.chat_azure_api_version if chat_api_version is None else chat_api_version
            self.chat_stream = LLM_SETTINGS.chat_stream
            self.chat_seed = LLM_SETTINGS.chat_seed

            self.embedding_model = LLM_SETTINGS.embedding_model if embedding_model is None else embedding_model
            self.embedding_api_base = LLM_SETTINGS.embedding_azure_api_base if embedding_api_base is None else embedding_api_base
            self.embedding_api_version = LLM_SETTINGS.embedding_azure_api_version if embedding_api_version is None else embedding_api_version

            if self.use_azure:
                if self.chat_use_azure_token_provider or self.embedding_use_azure_token_provider:
                    dac_kwargs = {}
                    if self.managed_identity_client_id is not None:
                        dac_kwargs["managed_identity_client_id"] = self.managed_identity_client_id
                    credential = DefaultAzureCredential(**dac_kwargs)
                    token_provider = get_bearer_token_provider(
                        credential,
                        "https://cognitiveservices.azure.com/.default",
                    )
                if self.chat_use_azure_token_provider:
                    self.chat_client = openai.AzureOpenAI(
                        azure_ad_token_provider=token_provider,
                        api_version=self.chat_api_version,
                        azure_endpoint=self.chat_api_base,
                    )
                else:
                    self.chat_client = openai.AzureOpenAI(
                        api_key=self.chat_api_key,
                        api_version=self.chat_api_version,
                        azure_endpoint=self.chat_api_base,
                    )

                if self.embedding_use_azure_token_provider:
                    self.embedding_client = openai.AzureOpenAI(
                        azure_ad_token_provider=token_provider,
                        api_version=self.embedding_api_version,
                        azure_endpoint=self.embedding_api_base,
                    )
                else:
                    self.embedding_client = openai.AzureOpenAI(
                        api_key=self.embedding_api_key,
                        api_version=self.embedding_api_version,
                        azure_endpoint=self.embedding_api_base,
                    )
            else:
                self.chat_client = self._create_openai_client(api_key=self.chat_api_key, base_url=self.base_url)
                self.embedding_client = self._create_openai_client(api_key=self.embedding_api_key, base_url=self.embedding_base_url)

        self.dump_chat_cache = LLM_SETTINGS.dump_chat_cache if dump_chat_cache is None else dump_chat_cache
        self.use_chat_cache = LLM_SETTINGS.use_chat_cache if use_chat_cache is None else use_chat_cache
        self.dump_embedding_cache = LLM_SETTINGS.dump_embedding_cache if dump_embedding_cache is None else dump_embedding_cache
        self.use_embedding_cache = LLM_SETTINGS.use_embedding_cache if use_embedding_cache is None else use_embedding_cache
        if self.dump_chat_cache or self.use_chat_cache or self.dump_embedding_cache or self.use_embedding_cache:
            self.cache_file_location = LLM_SETTINGS.prompt_cache_path
            self.cache = SQliteLazyCache(cache_location=self.cache_file_location)

        # transfer the config to the class if the config is not supposed to change during the runtime
        self.use_llama2 = LLM_SETTINGS.use_llama2
        self.use_gcr_endpoint = LLM_SETTINGS.use_gcr_endpoint
        self.retry_wait_seconds = LLM_SETTINGS.retry_wait_seconds
        # Use explicit pool, or fall back to default ProviderPool
        self._provider_pool = provider_pool if provider_pool is not None else get_default_provider_pool()

    def _create_openai_client(self, *, api_key: str | None, base_url: str | None):
        """Create an OpenAI-compatible client governed by our retry loop."""
        timeout_value = LLM_SETTINGS.openai_request_timeout_seconds
        logger.info(f"[_create_openai_client] Creating client with timeout={timeout_value}s, model={getattr(self, 'chat_model', 'N/A')}")
        return openai.OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_value,
            max_retries=LLM_SETTINGS.openai_sdk_max_retries,
        )

    def _get_provider_name_for_model(self, model: str | None) -> str | None:
        """Return the first provider whose configured model matches the request model."""
        pool = getattr(self, "_provider_pool", None)
        if pool is None or not model:
            return None

        for provider_name in pool.get_providers():
            provider_config = pool.get_provider(provider_name)
            if provider_config and provider_config.model == model:
                return provider_name
        return None

    def _get_encoder(self):
        """tiktoken.encoding_for_model(self.chat_model) does not cover all cases it should consider.

        This function attempts to handle several edge cases.
        """

        # 1) cases
        def _azure_patch(model: str) -> str:
            """When using Azure API, self.chat_model is the deployment name that can be any string.
            For example, it may be `gpt-4o_2024-08-06`. But tiktoken.encoding_for_model can't handle this.
            """
            return model.replace("_", "-")

        model = self.chat_model
        try:
            return tiktoken.encoding_for_model(model)
        except KeyError:
            for patch_func in [_azure_patch]:
                try:
                    return tiktoken.encoding_for_model(patch_func(model))
                except KeyError:
                    continue
            raise KeyError(f"Could not automatically map {model} to a tokeniser.")

    def build_chat_session(
        self,
        conversation_id: str | None = None,
        session_system_prompt: str | None = None,
    ) -> ChatSession:
        """conversation_id is a 256-bit string created by uuid.uuid4() and is also
        the file name under session_cache_folder/ for each conversation
        """
        return ChatSession(self, conversation_id, session_system_prompt)

    def get_model_for_task(
        self,
        task_type: str | None = None,
        tag: str | None = None,
        required_capabilities: list[str] | None = None,
        max_tier: int = 3,
    ) -> str:
        """Get the model for a task, optionally filtering by capabilities.

        Args:
            task_type: Task type for legacy routing
            tag: Tag for legacy routing
            required_capabilities: List of required capability tags (e.g. ["tool_calling"])
            max_tier: Maximum tier level to consider

        Returns:
            Model name string.
        """
        # Retry model switching override: when a provider switch has occurred,
        # use the new provider's model for ALL subsequent calls in this retry cycle.
        retry_model = getattr(self, "_current_retry_model", None)
        if retry_model:
            return retry_model

        # Capability-aware routing
        if required_capabilities and hasattr(self, "_provider_pool") and self._provider_pool is not None:
            matching = self._provider_pool.get_by_capability(
                require_tags=required_capabilities,
                max_tier=max_tier,
            )
            if matching:
                # Return model from the cheapest matching provider
                for provider in matching:
                    if provider.model:
                        return provider.model
            # No matching provider or no model set; fall back to default
            logger.warning(f"No model found for capabilities {required_capabilities}; falling back to default chat_model")

        # Fall back to existing routing logic
        if task_type:
            if task_type not in KNOWN_TASK_TYPES:
                logger.warning(f"Unknown llm task_type={task_type}; falling back to default routing")
            model = self.task_model_map.get(task_type)
            if model:
                return model
            return self.routing_default or self.chat_model_map.get(tag or "", self.chat_model)
        if tag:
            return self.chat_model_map.get(tag, self.chat_model)
        return self.routing_default or self.chat_model

    def build_messages(
        self,
        user_prompt: str,
        system_prompt: str | None = None,
        former_messages: list[dict] | None = None,
        *,
        shrink_multiple_break: bool = False,
        tool_results: list[dict] | None = None,
    ) -> list[dict]:
        """Build the messages to avoid implementing several redundant lines of code

        tool_results: list of {"tool_call_id": str, "name": str, "content": str}
        """
        if former_messages is None:
            former_messages = []
        # shrink multiple break will recursively remove multiple breaks(more than 2)
        if shrink_multiple_break:
            while "\n\n\n" in user_prompt:
                user_prompt = user_prompt.replace("\n\n\n", "\n\n")
            if system_prompt is not None:
                while "\n\n\n" in system_prompt:
                    system_prompt = system_prompt.replace("\n\n\n", "\n\n")
        system_prompt = LLM_SETTINGS.default_system_prompt if system_prompt is None else system_prompt
        messages = [
            {
                "role": "system",
                "content": system_prompt,
            },
        ]
        messages.extend(former_messages[-1 * LLM_SETTINGS.max_past_message_include :])
        messages.append(
            {
                "role": "user",
                "content": user_prompt,
            },
        )

        # Append tool results
        if tool_results:
            for tr in tool_results:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tr["tool_call_id"],
                        "name": tr["name"],
                        "content": tr["content"],
                    }
                )

        return messages

    def build_messages_and_create_chat_completion(
        self,
        user_prompt: str,
        system_prompt: str | None = None,
        former_messages: list | None = None,
        chat_cache_prefix: str = "",
        *,
        shrink_multiple_break: bool = False,
        **kwargs: Any,
    ) -> str:
        if former_messages is None:
            former_messages = []
        messages = self.build_messages(
            user_prompt,
            system_prompt,
            former_messages,
            shrink_multiple_break=shrink_multiple_break,
        )
        return self._try_create_chat_completion_or_embedding(
            messages=messages,
            chat_completion=True,
            chat_cache_prefix=chat_cache_prefix,
            **kwargs,
        )

    def build_messages_and_create_chat_completion_json(
        self,
        user_prompt: str,
        system_prompt: str | None = None,
        former_messages: list | None = None,
        chat_cache_prefix: str = "",
        *,
        shrink_multiple_break: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Compatibility wrapper that delegates to ``call_structured()``.

        This method no longer drives its own ``json_mode`` path directly.
        Instead it builds messages and forwards through the unified structured
        gateway so that tool-call-first behavior and model-level degradation
        apply automatically.
        """
        messages = self.build_messages(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            former_messages=former_messages,
            shrink_multiple_break=shrink_multiple_break,
        )
        return call_structured(self, messages, **kwargs)

    def create_embedding(self, input_content: str | list[str], **kwargs: Any) -> list[Any] | Any:
        input_content_list = [input_content] if isinstance(input_content, str) else input_content
        resp = self._try_create_chat_completion_or_embedding(
            input_content_list=input_content_list,
            embedding=True,
            **kwargs,
        )
        if isinstance(input_content, str):
            return resp[0]
        return resp

    def _create_chat_completion_auto_continue(self, messages: list, **kwargs: dict) -> str | dict:
        """Call the chat completion function and automatically continue the conversation if the finish_reason is length.
        TODO: This function only continues once, maybe need to continue more than once in the future.
        """
        result = self._create_chat_completion_inner_function(messages=messages, **kwargs)
        response = result[0]
        finish_reason = result[1]
        structured_tools_requested = kwargs.get("tools") is not None

        # Tool calls: return structured result immediately (don't discard tool_calls)
        if len(result) >= 3 and result[2] is not None:
            return {"content": response, "finish_reason": finish_reason, "tool_calls": result[2]}

        # Structured tool requests must not fall into text auto-continue.
        # Some providers incorrectly return empty/truncated assistant text instead
        # of tool_calls; preserving the first response lets the structured parser
        # fail fast or fall back deterministically at the caller.
        if structured_tools_requested:
            return {"content": response, "finish_reason": finish_reason, "tool_calls": None}

        if finish_reason == "length":
            new_message = deepcopy(messages)
            new_message.append({"role": "assistant", "content": response})
            new_message.append(
                {
                    "role": "user",
                    "content": "continue the former output with no overlap",
                },
            )
            new_result = self._create_chat_completion_inner_function(messages=new_message, **kwargs)
            new_response = new_result[0]
            return response + new_response
        return response

    def _create_chat_completion_or_embedding_once(
        self,
        *,
        chat_completion: bool = False,
        embedding: bool = False,
        **kwargs: Any,
    ) -> Any:
        """Execute a single chat/embedding attempt without retry logic."""
        if embedding:
            return self._create_embedding_inner_function(**kwargs)
        if chat_completion:
            return self._create_chat_completion_auto_continue(**kwargs)
        raise ValueError("Either chat_completion or embedding must be True")
