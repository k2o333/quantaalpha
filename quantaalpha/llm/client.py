"""Compatibility facade for LLM client helpers and backend classes."""

from __future__ import annotations

import sys
import types

from .client_backend import APIBackend
from .client_embedding import calculate_embedding_distance_between_str_list
from .client_sessions import ChatSession, ConvManager, SQliteLazyCache, SessionChatHistoryCache
from .client_shared import (
    DEFAULT_FALLBACK_TOKENIZER,
    DEFAULT_QLIB_DOT_PATH,
    KNOWN_TASK_TYPES,
    LLM_SETTINGS,
    TOKENIZER_UNSUPPORTED_MODEL_PREFIXES,
    EmptyLLMResponseError,
    LogColors,
    StructuredSchemaError,
    _DEGRADATION_LOCK,
    _DEFAULT_POOL_LOCK,
    _DEFAULT_PROVIDER_POOL,
    _MODEL_DEGRADATION_STATE,
    _ProviderAttempt,
    _TOKENIZER_FALLBACK_WARNED_MODELS,
    _close_truncated_json,
    _coerce_int_setting,
    _detect_tool_call_capability_failure_from_response,
    _ensure_structured_object_payload,
    _escape_common_json_sequences,
    _extract_balanced_json_object,
    _get_model_degradation_state,
    _is_tool_call_capability_failure,
    _record_tool_call_capability_failure,
    _record_tool_call_success,
    _remove_trailing_commas,
    call_structured,
    get_default_provider_pool,
    logger,
    log_tokenizer_fallback_once,
    md5_hash,
    normalize_and_parse,
    openai,
    parse_chat_completion_json_response,
    parse_routing_tasks,
    robust_json_parse,
    set_default_provider_pool,
    should_skip_tokenizer_lookup,
)

__all__ = [name for name in globals() if not name.startswith("__")]


class _ClientFacadeModule(types.ModuleType):
    """Propagate compatibility monkeypatches from the facade to split modules."""

    _PROPAGATED_MODULES = (
        "quantaalpha.llm.client_backend_completion",
        "quantaalpha.llm.client_backend_init",
        "quantaalpha.llm.client_backend_retry",
        "quantaalpha.llm.client_backend_tokens",
        "quantaalpha.llm.client_embedding",
        "quantaalpha.llm.client_sessions",
        "quantaalpha.llm.client_shared",
    )
    _PROPAGATED_NAMES = {"LLM_SETTINGS", "logger", "openai"}

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name in self._PROPAGATED_NAMES:
            for module_name in self._PROPAGATED_MODULES:
                module = sys.modules.get(module_name)
                if module is not None and hasattr(module, name):
                    setattr(module, name, value)


sys.modules[__name__].__class__ = _ClientFacadeModule
