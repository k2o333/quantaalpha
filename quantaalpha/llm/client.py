from __future__ import annotations

import hashlib
import inspect
import json
import os
import random
import re
import sqlite3
import ssl
import time
import urllib.request
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any, Optional

import numpy as np
import tiktoken

from quantaalpha.core.utils import LLM_CACHE_SEED_GEN, SingletonBaseClass
from quantaalpha.log import LogColors, logger
from quantaalpha.log import logger
from quantaalpha.llm.config import LLM_SETTINGS

DEFAULT_QLIB_DOT_PATH = Path("./")
KNOWN_TASK_TYPES = {
    "hypothesis_generation",
    "factor_construction",
    "evaluation_screening",
    "feedback_summarization",
}
TOKENIZER_UNSUPPORTED_MODEL_PREFIXES = ("qwen",)
DEFAULT_FALLBACK_TOKENIZER = "cl100k_base"
_TOKENIZER_FALLBACK_WARNED_MODELS: set[str] = set()


class EmptyLLMResponseError(RuntimeError):
    """Raised when the provider returns an empty chat completion payload."""


def md5_hash(input_string: str) -> str:
    hash_md5 = hashlib.md5(usedforsecurity=False)
    input_bytes = input_string.encode("utf-8")
    hash_md5.update(input_bytes)
    return hash_md5.hexdigest()


def parse_routing_tasks(raw: str) -> dict[str, str]:
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid LLM routing_tasks JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("LLM routing_tasks must be a JSON object")
    return {str(key): str(value) for key, value in parsed.items()}


def should_skip_tokenizer_lookup(model: str | None) -> bool:
    if not model:
        return False
    normalized = model.strip().lower()
    return any(normalized.startswith(prefix) for prefix in TOKENIZER_UNSUPPORTED_MODEL_PREFIXES)


def log_tokenizer_fallback_once(model: str | None, reason: str) -> None:
    normalized = (model or "").strip().lower() or "<empty>"
    if normalized in _TOKENIZER_FALLBACK_WARNED_MODELS:
        return
    _TOKENIZER_FALLBACK_WARNED_MODELS.add(normalized)
    logger.warning(f"Tokenizer lookup failed for model {model}; falling back to {DEFAULT_FALLBACK_TOKENIZER}. reason={reason}")


def _extract_balanced_json_object(text: str) -> str | None:
    brace_count = 0
    start_idx = -1
    in_string = False
    escape_next = False

    for i, char in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        if char == "\\":
            escape_next = True
            continue
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue

        if char == "{":
            if brace_count == 0:
                start_idx = i
            brace_count += 1
        elif char == "}":
            brace_count -= 1
            if brace_count == 0 and start_idx != -1:
                return text[start_idx : i + 1]

    if start_idx != -1:
        return text[start_idx:]
    return None


def _escape_common_json_sequences(text: str) -> str:
    fixed_text = text
    latex_commands = [
        "text",
        "frac",
        "left",
        "right",
        "times",
        "cdot",
        "sqrt",
        "sum",
        "prod",
        "int",
        "alpha",
        "beta",
        "gamma",
        "delta",
    ]
    for cmd in latex_commands:
        fixed_text = re.sub(r"(?<!\\)\\(" + cmd + r")", r"\\\\\1", fixed_text)
    fixed_text = re.sub(
        r"(?<!\\)\\([_\{\}\[\]])",
        lambda match: "\\" + match.group(1),
        fixed_text,
    )
    # Fix all unrecognized backslash escapes (generic fallback)
    fixed_text = re.sub(r'\\(?!["\\\/bfnrtu])', r"\\\\", fixed_text)
    return fixed_text


def _remove_trailing_commas(text: str) -> str:
    return re.sub(r",(\s*[}\]])", r"\1", text)


def _close_truncated_json(text: str) -> str:
    open_braces = text.count("{")
    close_braces = text.count("}")
    open_brackets = text.count("[")
    close_brackets = text.count("]")
    text = text.rstrip()
    if text.endswith(","):
        text = text[:-1].rstrip()
    if open_brackets > close_brackets:
        text += "]" * (open_brackets - close_brackets)
    if open_braces > close_braces:
        text += "}" * (open_braces - close_braces)
    return text


def robust_json_parse(text: str, max_retries: int = 3) -> dict:
    """
    Robust JSON parser: handles extra data, LaTeX escapes, markdown-wrapped JSON.
    Raises json.JSONDecodeError if all strategies fail.
    """
    original_text = text

    # Strategy 1: direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: extract JSON code block
    json_block_pattern = r"```(?:json)?\s*\n?([\s\S]*?)\n?```"
    matches = re.findall(json_block_pattern, text)
    if matches:
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue

    # Strategy 3: balanced object extraction, with conservative repairs for common truncation.
    json_candidate = _extract_balanced_json_object(text)
    if json_candidate:
        candidate_variants = [
            json_candidate,
            _escape_common_json_sequences(json_candidate),
            _remove_trailing_commas(json_candidate),
            _close_truncated_json(_remove_trailing_commas(_escape_common_json_sequences(json_candidate))),
        ]
        seen_variants = set()
        for candidate in candidate_variants:
            if candidate in seen_variants:
                continue
            seen_variants.add(candidate)
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

    # Strategy 4: looser JSON extraction
    potential_jsons = re.findall(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text)
    for pj in potential_jsons:
        try:
            result = json.loads(pj)
            if isinstance(result, dict) and len(result) > 0:
                return result
        except json.JSONDecodeError:
            continue

    repaired_text = _close_truncated_json(_remove_trailing_commas(_escape_common_json_sequences(original_text.strip())))
    if repaired_text != original_text.strip():
        try:
            result = json.loads(repaired_text)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    raise json.JSONDecodeError(
        f"Could not parse JSON; original text length: {len(original_text)}",
        original_text,
        0,
    )


try:
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
except ImportError:
    logger.warning("azure.identity is not installed.")

try:
    import openai
except ImportError:
    logger.warning("openai is not installed.")

try:
    from llama import Llama
except ImportError:
    logger.info("llama is not installed.")


class ConvManager:
    """
    This is a conversation manager of LLM
    It is for convenience of exporting conversation for debugging.
    """

    def __init__(
        self,
        path: Path | str = DEFAULT_QLIB_DOT_PATH / "llm_conv",
        recent_n: int = 10,
    ) -> None:
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.recent_n = recent_n

    def _rotate_files(self) -> None:
        pairs = []
        for f in self.path.glob("*.json"):
            m = re.match(r"(\d+).json", f.name)
            if m is not None:
                n = int(m.group(1))
                pairs.append((n, f))
        pairs.sort(key=lambda x: x[0])
        for n, f in pairs[: self.recent_n][::-1]:
            if (self.path / f"{n + 1}.json").exists():
                (self.path / f"{n + 1}.json").unlink()
            f.rename(self.path / f"{n + 1}.json")

    def append(self, conv: tuple[list, str]) -> None:
        self._rotate_files()
        with (self.path / "0.json").open("w") as file:
            json.dump(conv, file)
        # TODO: reseve line breaks to make it more convient to edit file directly.


class SQliteLazyCache(SingletonBaseClass):
    def __init__(self, cache_location: str) -> None:
        super().__init__()
        self.cache_location = cache_location
        db_file_exist = Path(cache_location).exists()
        # TODO: sqlite3 does not support multiprocessing.
        self.conn = sqlite3.connect(cache_location, timeout=20)
        self.c = self.conn.cursor()
        if not db_file_exist:
            self.c.execute(
                """
                CREATE TABLE chat_cache (
                    md5_key TEXT PRIMARY KEY,
                    chat TEXT
                )
                """,
            )
            self.c.execute(
                """
                CREATE TABLE embedding_cache (
                    md5_key TEXT PRIMARY KEY,
                    embedding TEXT
                )
                """,
            )
            self.c.execute(
                """
                CREATE TABLE message_cache (
                    conversation_id TEXT PRIMARY KEY,
                    message TEXT
                )
                """,
            )
            self.conn.commit()

    def chat_get(self, key: str) -> str | None:
        md5_key = md5_hash(key)
        self.c.execute("SELECT chat FROM chat_cache WHERE md5_key=?", (md5_key,))
        result = self.c.fetchone()
        if result is None:
            return None
        return result[0]

    def embedding_get(self, key: str) -> list | dict | str | None:
        md5_key = md5_hash(key)
        self.c.execute("SELECT embedding FROM embedding_cache WHERE md5_key=?", (md5_key,))
        result = self.c.fetchone()
        if result is None:
            return None
        return json.loads(result[0])

    def chat_set(self, key: str, value: str) -> None:
        md5_key = md5_hash(key)
        self.c.execute(
            "INSERT OR REPLACE INTO chat_cache (md5_key, chat) VALUES (?, ?)",
            (md5_key, value),
        )
        self.conn.commit()

    def embedding_set(self, content_to_embedding_dict: dict) -> None:
        for key, value in content_to_embedding_dict.items():
            md5_key = md5_hash(key)
            self.c.execute(
                "INSERT OR REPLACE INTO embedding_cache (md5_key, embedding) VALUES (?, ?)",
                (md5_key, json.dumps(value)),
            )
        self.conn.commit()

    def message_get(self, conversation_id: str) -> list[str]:
        self.c.execute("SELECT message FROM message_cache WHERE conversation_id=?", (conversation_id,))
        result = self.c.fetchone()
        if result is None:
            return []
        return json.loads(result[0])

    def message_set(self, conversation_id: str, message_value: list[str]) -> None:
        self.c.execute(
            "INSERT OR REPLACE INTO message_cache (conversation_id, message) VALUES (?, ?)",
            (conversation_id, json.dumps(message_value)),
        )
        self.conn.commit()


class SessionChatHistoryCache(SingletonBaseClass):
    def __init__(self) -> None:
        """load all history conversation json file from self.session_cache_location"""
        self.cache = SQliteLazyCache(cache_location=LLM_SETTINGS.prompt_cache_path)

    def message_get(self, conversation_id: str) -> list[str]:
        return self.cache.message_get(conversation_id)

    def message_set(self, conversation_id: str, message_value: list[str]) -> None:
        self.cache.message_set(conversation_id, message_value)


class ChatSession:
    def __init__(self, api_backend: Any, conversation_id: str | None = None, system_prompt: str | None = None) -> None:
        self.conversation_id = str(uuid.uuid4()) if conversation_id is None else conversation_id
        self.system_prompt = system_prompt if system_prompt is not None else LLM_SETTINGS.default_system_prompt
        self.api_backend = api_backend

    def build_chat_completion_message(self, user_prompt: str) -> list[dict[str, Any]]:
        history_message = SessionChatHistoryCache().message_get(self.conversation_id)
        messages = history_message
        if not messages:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append(
            {
                "role": "user",
                "content": user_prompt,
            },
        )
        return messages

    def build_chat_completion_message_and_calculate_token(self, user_prompt: str) -> Any:
        messages = self.build_chat_completion_message(user_prompt)
        return self.api_backend.calculate_token_from_messages(messages)

    def build_chat_completion(self, user_prompt: str, **kwargs: Any) -> str:
        """
        this function is to build the session messages
        user prompt should always be provided
        """
        messages = self.build_chat_completion_message(user_prompt)

        with logger.tag(f"session_{self.conversation_id}"):
            response = self.api_backend._try_create_chat_completion_or_embedding(  # noqa: SLF001
                messages=messages,
                chat_completion=True,
                **kwargs,
            )

        messages.append(
            {
                "role": "assistant",
                "content": response,
            },
        )
        SessionChatHistoryCache().message_set(self.conversation_id, messages)
        return response

    def build_chat_completion_json(self, user_prompt: str, **kwargs: Any) -> dict[str, Any]:
        kwargs["json_mode"] = True
        response = self.build_chat_completion(user_prompt, **kwargs)
        return robust_json_parse(response)

    def get_conversation_id(self) -> str:
        return self.conversation_id

    def display_history(self) -> None:
        # TODO: Realize a beautiful presentation format for history messages
        pass


class APIBackend:
    """
    This is a unified interface for different backends.

    (xiao) thinks integrate all kinds of API in a single class is not a good design.
    So we should split them into different classes in `oai/backends/` in the future.
    """

    # FIXME: (xiao) We should avoid using self.xxxx.
    # Instead, we can use LLM_SETTINGS directly. If it's difficult to support different backend settings, we can split them into multiple BaseSettings.
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
                self.chat_client = openai.OpenAI(api_key=self.chat_api_key, base_url=self.base_url)
                self.embedding_client = openai.OpenAI(api_key=self.embedding_api_key, base_url=self.embedding_base_url)

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

    def _get_encoder(self):
        """
        tiktoken.encoding_for_model(self.chat_model) does not cover all cases it should consider.

        This function attempts to handle several edge cases.
        """

        # 1) cases
        def _azure_patch(model: str) -> str:
            """
            When using Azure API, self.chat_model is the deployment name that can be any string.
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
        """
        conversation_id is a 256-bit string created by uuid.uuid4() and is also
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
        """
        Get the model for a task, optionally filtering by capabilities.

        Args:
            task_type: Task type for legacy routing
            tag: Tag for legacy routing
            required_capabilities: List of required capability tags (e.g. ["tool_calling"])
            max_tier: Maximum tier level to consider

        Returns:
            Model name string.
        """
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
            if matching:
                # Return model from the cheapest matching provider
                for provider in matching:
                    if provider.model:
                        return provider.model
                # If no model set on provider, fall through to default
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
        """
        build the messages to avoid implementing several redundant lines of code

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
        kwargs["json_mode"] = True
        response = self.build_messages_and_create_chat_completion(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            former_messages=former_messages,
            chat_cache_prefix=chat_cache_prefix,
            shrink_multiple_break=shrink_multiple_break,
            **kwargs,
        )
        return robust_json_parse(response)

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

    def _create_chat_completion_auto_continue(self, messages: list, **kwargs: dict) -> str:
        """
        Call the chat completion function and automatically continue the conversation if the finish_reason is length.
        TODO: This function only continues once, maybe need to continue more than once in the future.
        """
        result = self._create_chat_completion_inner_function(messages=messages, **kwargs)
        response = result[0]
        finish_reason = result[1]

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

    def _try_create_chat_completion_or_embedding(
        self,
        max_retry: int = 10,
        *,
        chat_completion: bool = False,
        embedding: bool = False,
        **kwargs: Any,
    ) -> Any:
        assert not (chat_completion and embedding), "chat_completion and embedding cannot be True at the same time"
        max_retry = LLM_SETTINGS.max_retry if LLM_SETTINGS.max_retry is not None else max_retry
        for i in range(max_retry):
            try:
                # import pdb; pdb.set_trace()
                if embedding:
                    return self._create_embedding_inner_function(**kwargs)
                if chat_completion:
                    return self._create_chat_completion_auto_continue(**kwargs)
            except openai.BadRequestError as e:  # noqa: PERF203
                error_str = str(e)
                logger.warning(e)
                # Unrecoverable: invalid model name — fail fast, no retry
                if "Invalid model" in error_str:
                    failing_model = self.embedding_model if embedding else self.chat_model
                    logger.error(f"Unrecoverable BadRequest: invalid model '{failing_model}'. Check model configuration.")
                    raise
                logger.warning(f"Retrying {i + 1}th time...")
                if "'messages' must contain the word 'json' in some form" in error_str:
                    kwargs["add_json_in_prompt"] = True
                elif embedding and "maximum context length" in error_str:
                    kwargs["input_content_list"] = [content[: len(content) // 2] for content in kwargs.get("input_content_list", [])]
                # Wait before retry to avoid rate limit
                if i < max_retry - 1:
                    time.sleep(self.retry_wait_seconds)
            except Exception as e:  # noqa: BLE001
                logger.warning(e)
                logger.warning(f"Retrying {i + 1}th time...")
                if i < max_retry - 1:
                    time.sleep(self.retry_wait_seconds)
        error_message = f"Failed to create chat completion after {max_retry} retries."
        raise RuntimeError(error_message)

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
    ) -> tuple[str, str | None] | tuple[str, str | None, list[dict] | None]:
        """
        seed : Optional[int]
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
                stream=self.chat_stream,
                seed=self.chat_seed,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
            )

            if json_mode:
                if add_json_in_prompt:
                    for message in messages[::-1]:
                        message["content"] = message["content"] + "\nPlease respond in json format."
                        if message["role"] == "system":
                            break
                kwargs["response_format"] = {"type": "json_object"}
            if tools is not None:
                kwargs["tools"] = tools
                if tool_choice is not None:
                    kwargs["tool_choice"] = tool_choice
            response = self.chat_client.chat.completions.create(**kwargs)

            if self.chat_stream:
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
            if json_mode or reasoning_flag:
                # Extract JSON part
                json_start = resp.find("{")
                json_end = resp.rfind("}") + 1
                resp = resp[json_start:json_end]
                # Try parse JSON; on failure try to fix
                try:
                    json.loads(resp)
                except json.JSONDecodeError as e:
                    import re

                    error_msg = str(e).lower()
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

    def calculate_token_from_messages(self, messages: list[dict]) -> int:
        if self.use_llama2 or self.use_gcr_endpoint:
            logger.warning("num_tokens_from_messages() is not implemented for model llama2.")
            return 0  # TODO implement this function for llama2

        if "gpt4" in self.chat_model or "gpt-4" in self.chat_model:
            tokens_per_message = 3
            tokens_per_name = 1
        else:
            tokens_per_message = 4  # every message follows <start>{role/name}\n{content}<end>\n
            tokens_per_name = -1  # if there's a name, the role is omitted
        num_tokens = 0
        for message in messages:
            num_tokens += tokens_per_message
            for key, value in message.items():
                if self.encoder is not None:
                    num_tokens += len(self.encoder.encode(value))
                else:
                    num_tokens += max(1, len(value) // 4)
                if key == "name":
                    num_tokens += tokens_per_name
        num_tokens += 3  # every reply is primed with <start>assistant<message>
        return num_tokens

    def build_messages_and_calculate_token(
        self,
        user_prompt: str,
        system_prompt: str | None,
        former_messages: list[dict] | None = None,
        *,
        shrink_multiple_break: bool = False,
    ) -> int:
        if former_messages is None:
            former_messages = []
        messages = self.build_messages(user_prompt, system_prompt, former_messages, shrink_multiple_break=shrink_multiple_break)
        return self.calculate_token_from_messages(messages)


def calculate_embedding_distance_between_str_list(
    source_str_list: list[str],
    target_str_list: list[str],
) -> list[list[float]]:
    if not source_str_list or not target_str_list:
        return [[]]

    embeddings = APIBackend().create_embedding(source_str_list + target_str_list)

    source_embeddings = embeddings[: len(source_str_list)]
    target_embeddings = embeddings[len(source_str_list) :]

    source_embeddings_np = np.array(source_embeddings)
    target_embeddings_np = np.array(target_embeddings)

    source_embeddings_np = source_embeddings_np / np.linalg.norm(source_embeddings_np, axis=1, keepdims=True)
    target_embeddings_np = target_embeddings_np / np.linalg.norm(target_embeddings_np, axis=1, keepdims=True)
    similarity_matrix = np.dot(source_embeddings_np, target_embeddings_np.T)

    return similarity_matrix.tolist()
