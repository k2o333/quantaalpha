from __future__ import annotations

from .client_shared import *
from .client_shared import (
    _ProviderAttempt,
    _coerce_int_setting,
    _escape_common_json_sequences,
    _is_tool_call_capability_failure,
)
from .client_sessions import ChatSession, SQliteLazyCache


class BackendCompletionMixin:
    """Responsibility slice for APIBackend."""

    def _create_embedding_inner_function(self, input_content_list: list[str], **kwargs: Any) -> list[Any]:  # noqa: ARG002
        content_to_embedding_dict = {}
        filtered_input_content_list = []
        if self.use_embedding_cache:
            for content in input_content_list:
                cache_result = self.cache.embedding_get(content)
                if cache_result is not None:
                    content_to_embedding_dict[content] = cache_result
                else:
                    filtered_input_content_list.append(content)
        else:
            filtered_input_content_list = input_content_list

        if len(filtered_input_content_list) > 0:
            # Adjust batch size by model (DashScope text-embedding-v4 is slower)
            batch_size = LLM_SETTINGS.embedding_max_str_num
            if self.embedding_model and ("qwen" in self.embedding_model.lower() or "text-embedding-v4" in self.embedding_model.lower()):
                # DashScope embedding: use smaller batch to avoid overload
                batch_size = min(batch_size, 3)
                # DashScope embedding: smaller batch (silent)

            batch_wait_seconds = LLM_SETTINGS.embedding_batch_wait_seconds
            batches = [filtered_input_content_list[i : i + batch_size] for i in range(0, len(filtered_input_content_list), batch_size)]

            for batch_idx, sliced_filtered_input_content_list in enumerate(batches):
                if self.use_azure:
                    response = self.embedding_client.embeddings.create(
                        model=self.embedding_model,
                        input=sliced_filtered_input_content_list,
                    )
                else:
                    response = self.embedding_client.embeddings.create(
                        model=self.embedding_model,
                        input=sliced_filtered_input_content_list,
                    )
                for index, data in enumerate(response.data):
                    content_to_embedding_dict[sliced_filtered_input_content_list[index]] = data.embedding

                if self.dump_embedding_cache:
                    self.cache.embedding_set(content_to_embedding_dict)

                # Wait between batches to avoid API overload
                if batch_idx < len(batches) - 1 and batch_wait_seconds > 0:
                    time.sleep(batch_wait_seconds)
        return [content_to_embedding_dict[content] for content in input_content_list]

    def _build_log_messages(self, messages: list[dict], max_prompt_length: int = 100) -> str:
        """Build log string from messages (content truncated to max_prompt_length)."""
        log_messages = ""
        for m in messages:
            role = m["role"]
            content = m["content"]
            if len(content) > max_prompt_length:
                display_content = content[:max_prompt_length] + f"... [{len(content)} chars]"
            else:
                display_content = content

            log_messages += f"\n{LogColors.MAGENTA}{LogColors.BOLD}Role:{LogColors.END}{LogColors.CYAN}{role}{LogColors.END}\n{LogColors.MAGENTA}{LogColors.BOLD}Content:{LogColors.END} {LogColors.CYAN}{display_content}{LogColors.END}\n"
        return log_messages

    def _create_chat_completion_inner_function(  # noqa: C901, PLR0912, PLR0915
        self,
        messages: list[dict],
        reasoning_flag=True,
        temperature: float | None = None,
        max_tokens: int | None = None,
        chat_cache_prefix: str = "",
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
        *,
        json_mode: bool = False,
        add_json_in_prompt: bool = False,
        seed: Optional[int] = None,
        task_type: str | None = None,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        stream: bool | None = None,
        llm_call_site: str | None = None,
    ) -> tuple[str, str | None] | tuple[str, str | None, list[dict] | None]:
        """Seed : Optional[int]
        When retrying with cache enabled, it will keep returning the same results.
        To make retries useful, we need to enable a seed.
        This seed is different from `self.chat_seed` for GPT. It is for the local cache mechanism enabled by QuantaAlpha locally.
        """
        if seed is None and LLM_SETTINGS.use_auto_chat_cache_seed_gen:
            seed = LLM_CACHE_SEED_GEN.get_next_seed()

        # TODO: we can add this function back to avoid so much `self.cfg.log_llm_chat_content`
        if LLM_SETTINGS.log_llm_chat_content:
            logger.info(self._build_log_messages(messages), tag="llm_messages")
        # TODO: fail to use loguru adaptor due to stream response
        input_content_json = json.dumps(messages)
        input_content_json = chat_cache_prefix + input_content_json + f"<seed={seed}/>"  # FIXME this is a hack to make sure the cache represents the round index
        if self.use_chat_cache:
            cache_result = self.cache.chat_get(input_content_json)
            if cache_result is not None:
                if LLM_SETTINGS.log_llm_chat_content:
                    display_cr = cache_result[:200] + f"... [{len(cache_result)} chars]" if len(cache_result) > 200 else cache_result
                    logger.info(f"{LogColors.CYAN}Response(cached):{display_cr}{LogColors.END}", tag="llm_messages")
                return cache_result, None

        if temperature is None:
            temperature = LLM_SETTINGS.chat_temperature
        if max_tokens is None:
            max_tokens = LLM_SETTINGS.chat_max_tokens
        if frequency_penalty is None:
            frequency_penalty = LLM_SETTINGS.chat_frequency_penalty
        if presence_penalty is None:
            presence_penalty = LLM_SETTINGS.chat_presence_penalty

        # Use index 4 to skip the current function and intermediate calls,
        # and get the locals of the caller's frame.
        caller_locals = inspect.stack()[4].frame.f_locals
        if "self" in caller_locals:
            tag = caller_locals["self"].__class__.__name__
        else:
            tag = inspect.stack()[4].function

        if reasoning_flag:
            model = self.reasoning_model
            json_mode = None
        else:
            model = self.get_model_for_task(task_type=task_type, tag=tag)

        finish_reason = None
        tool_calls_result = None
        effective_stream = self.chat_stream if stream is None else stream
        if self.use_llama2:
            response = self.generator.chat_completion(
                messages,  # type: ignore
                max_gen_len=max_tokens,
                temperature=temperature,
            )
            resp = response[0]["generation"]["content"]
            if LLM_SETTINGS.log_llm_chat_content:
                logger.info(f"{LogColors.CYAN}Response:{resp}{LogColors.END}", tag="llm_messages")
        elif self.use_gcr_endpoint:
            body = str.encode(
                json.dumps(
                    {
                        "input_data": {
                            "input_string": messages,
                            "parameters": {
                                "temperature": self.gcr_endpoint_temperature,
                                "top_p": self.gcr_endpoint_top_p,
                                "max_new_tokens": self.gcr_endpoint_max_token,
                            },
                        },
                    },
                ),
            )

            req = urllib.request.Request(self.gcr_endpoint, body, self.headers)  # noqa: S310
            response = urllib.request.urlopen(req)  # noqa: S310
            resp = json.loads(response.read().decode())["output"]
            if LLM_SETTINGS.log_llm_chat_content:
                logger.info(f"{LogColors.CYAN}Response:{resp}{LogColors.END}", tag="llm_messages")
        else:
            kwargs = dict(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=effective_stream,
                seed=self.chat_seed,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
            )

            if json_mode:
                if add_json_in_prompt:
                    for message in messages[::-1]:
                        message["content"] = message["content"] + "\nReturn a valid JSON object only."
                        if message["role"] == "system":
                            break
                kwargs["response_format"] = {"type": "json_object"}
            if tools is not None:
                kwargs["tools"] = tools
                if tool_choice is not None:
                    kwargs["tool_choice"] = tool_choice

            # ProviderPool integration: get key and provider if pool is available
            start_time = None
            pool_provider = None
            pool_api_key = None
            if getattr(self, "_provider_pool", None) is not None:
                try:
                    provider_name = getattr(self, "_current_retry_provider_name", None)
                    if provider_name is None:
                        provider_name = self._get_provider_name_for_model(model)
                    api_key, provider_config = self._provider_pool.get_key_and_provider(provider_name=provider_name)
                    if api_key:
                        pool_provider = provider_config.name
                        pool_api_key = api_key
                        pool_base_url = provider_config.base_url or self.base_url
                        self.chat_client = self._create_openai_client(
                            api_key=api_key,
                            base_url=pool_base_url,
                        )
                except Exception as e:
                    logger.warning(f"ProviderPool get_key_and_provider failed: {e}, using default key")
                start_time = time.time()
            else:
                start_time = time.time()

            logger.info(
                f"[llm-request] start model={model} "
                f"provider={pool_provider or getattr(self, '_current_retry_provider_name', None)} "
                f"thread={threading.get_ident()} stream={effective_stream} call_site={llm_call_site or tag}"
            )
            response = self.chat_client.chat.completions.create(**kwargs)

            if effective_stream:
                resp = ""
                for chunk in response:
                    content = chunk.choices[0].delta.content if len(chunk.choices) > 0 and chunk.choices[0].delta.content is not None else ""
                    resp += content
                    if len(chunk.choices) > 0 and chunk.choices[0].finish_reason is not None:
                        finish_reason = chunk.choices[0].finish_reason

                # Check for empty response after streaming
                if not resp or not resp.strip():
                    logger.warning(f"Empty LLM response for model {model} after streaming; raising retryable error")
                    raise EmptyLLMResponseError(f"Model {model} returned empty content after streaming completion")

                if LLM_SETTINGS.log_llm_chat_content:
                    display_resp = resp[:200] + f"... [{len(resp)} chars]" if len(resp) > 200 else resp
                    logger.info(f"{LogColors.CYAN}Response:{display_resp}{LogColors.END}", tag="llm_messages")

            else:
                resp = response.choices[0].message.content
                finish_reason = response.choices[0].finish_reason

                # Extract tool_calls if present
                tool_calls_result = None
                if finish_reason == "tool_calls":
                    message = response.choices[0].message
                    if hasattr(message, "tool_calls") and message.tool_calls:
                        tool_calls_result = []
                        for tc in message.tool_calls:
                            tool_calls_result.append(
                                {
                                    "id": tc.id,
                                    "type": "function",
                                    "function": {
                                        "name": tc.function.name,
                                        "arguments": tc.function.arguments,
                                    },
                                }
                            )

                # Check for None response
                if resp is None:
                    if tool_calls_result:
                        logger.info(f"[llm] Tool-call response has empty content; using tool_calls arguments. model={model}, tool_calls_count={len(tool_calls_result)}")
                    else:
                        logger.warning(f"Empty LLM response for model {model} (non-streaming), returning empty string")
                    resp = ""

                if LLM_SETTINGS.log_llm_chat_content:
                    display_resp = resp[:200] + f"... [{len(resp)} chars]" if len(resp) > 200 else resp
                    logger.info(f"{LogColors.CYAN}Response:{display_resp}{LogColors.END}", tag="llm_messages")
                    logger.info(
                        json.dumps(
                            {
                                "tag": tag,
                                "total_tokens": response.usage.total_tokens,
                                "prompt_tokens": response.usage.prompt_tokens,
                                "completion_tokens": response.usage.completion_tokens,
                                "model": model,
                            }
                        ),
                        tag="llm_messages",
                    )

            # Record latency if provider pool is available
            if getattr(self, "_provider_pool", None) is not None and pool_provider is not None and pool_api_key is not None and start_time is not None:
                try:
                    latency_ms = (time.time() - start_time) * 1000
                    self._provider_pool.record_latency(pool_provider, pool_api_key, latency_ms)
                except Exception as e:
                    logger.warning(f"ProviderPool record_latency failed: {e}")
            if start_time is not None:
                latency_ms = (time.time() - start_time) * 1000
                logger.info(
                    f"[llm-request] end model={model} "
                    f"provider={pool_provider or getattr(self, '_current_retry_provider_name', None)} "
                    f"thread={threading.get_ident()} stream={effective_stream} "
                    f"call_site={llm_call_site or tag} latency_ms={latency_ms:.0f} finish_reason={finish_reason}"
                )

            if json_mode or reasoning_flag:
                # Extract JSON part
                json_start = resp.find("{")
                json_end = resp.rfind("}") + 1
                resp = resp[json_start:json_end]
                # Try parse JSON; on failure try to fix
                try:
                    json.loads(resp)
                except json.JSONDecodeError:
                    # Fix common JSON format issues
                    fixed_resp = resp

                    # Fix LaTeX backslash + generic backslash escapes via shared function
                    fixed_resp = _escape_common_json_sequences(fixed_resp)

                    # Fix control characters inside JSON string values
                    # We need to escape actual control chars (U+0000-U+001F) that appear inside JSON strings
                    # but NOT touch the JSON structural whitespace outside strings
                    def _escape_control_chars_in_json(text):
                        result = []
                        in_string = False
                        escape_next = False
                        for char in text:
                            if escape_next:
                                result.append(char)
                                escape_next = False
                                continue
                            if char == "\\":
                                result.append(char)
                                escape_next = True
                                continue
                            if char == '"' and not escape_next:
                                in_string = not in_string
                                result.append(char)
                                continue
                            if in_string and ord(char) < 32:  # Control character inside string
                                escape_map = {"\n": "\\n", "\r": "\\r", "\t": "\\t", "\b": "\\b", "\f": "\\f"}
                                if char in escape_map:
                                    result.append(escape_map[char])
                                else:
                                    result.append(f"\\u{ord(char):04x}")
                                continue
                            result.append(char)
                        return "".join(result)

                    fixed_resp = _escape_control_chars_in_json(fixed_resp)

                    try:
                        json.loads(fixed_resp)
                        resp = fixed_resp
                        logger.info("Fixed JSON format issues")
                    except json.JSONDecodeError as e2:
                        logger.warning(f"JSON fix failed: {e2}, using raw response")
        if self.dump_chat_cache:
            self.cache.chat_set(input_content_json, resp)
        if tools is not None and tool_calls_result is not None:
            return resp, finish_reason, tool_calls_result
        return resp, finish_reason
