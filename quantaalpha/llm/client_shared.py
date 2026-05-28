from __future__ import annotations

import hashlib
import inspect
import json
import os
import re
import sqlite3
import ssl
import threading
import time
import urllib.request
import uuid
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

import numpy as np
import tiktoken

from quantaalpha.core.utils import LLM_CACHE_SEED_GEN, SingletonBaseClass
from quantaalpha.llm.config import LLM_SETTINGS
from quantaalpha.llm.structured_normalizer import normalize_and_parse
from quantaalpha.log import LogColors, logger

if TYPE_CHECKING:
    from quantaalpha.llm.provider_pool import ProviderPool

# ruff: noqa: D101, D102, D103, D107, D205, D415

# ---------------------------------------------------------------------------
# Default ProviderPool registry
# ---------------------------------------------------------------------------
_DEFAULT_PROVIDER_POOL: "ProviderPool | None" = None
_DEFAULT_POOL_LOCK = threading.Lock()


def set_default_provider_pool(pool: "ProviderPool | None") -> None:
    """Set the default ProviderPool for all new APIBackend instances."""
    global _DEFAULT_PROVIDER_POOL
    with _DEFAULT_POOL_LOCK:
        _DEFAULT_PROVIDER_POOL = pool


def get_default_provider_pool() -> "ProviderPool | None":
    """Get the current default ProviderPool."""
    with _DEFAULT_POOL_LOCK:
        return _DEFAULT_PROVIDER_POOL


# ---------------------------------------------------------------------------
# Process-local model-level degradation state for tool-call capability failures
# ---------------------------------------------------------------------------
# Key: model name (str)
# Value: {"tool_call_failure_count": int, "force_text_json_fallback": bool}
_MODEL_DEGRADATION_STATE: dict[str, dict[str, Any]] = {}
_DEGRADATION_LOCK = threading.Lock()

# ---------------------------------------------------------------------------
# Provider attempt context for retry model switching
# ---------------------------------------------------------------------------


@dataclass
class _ProviderAttempt:
    """Context for a single provider attempt during retry."""

    provider_name: str | None
    api_key: str | None
    base_url: str | None
    model: str | None


_TOOL_CALL_CAPABILITY_FAILURE_PATTERNS = (
    "does not support function calling",
    "does not support tools",
    "does not support tool_choice",
    "tools parameter is not supported",
    "tool_choice is not supported",
    "tools is not supported",
    "function calling is not supported",
    "tool calls are not supported",
    "unsupported parameter",
    "invalid_parameter_error: tools",
    "invalid_parameter_error: tool_choice",
)


def _is_tool_call_capability_failure(error: BaseException) -> bool:
    """Return True if *error* signals that the provider cannot handle tool calls.

    This explicitly excludes generic network errors, rate-limit (429), timeouts,
    and business-level validation errors.  Only protocol / capability errors
    related to the tool-calling mechanism itself should count toward the
    process-local degradation threshold.
    """
    error_text = str(error).lower()
    return any(pattern in error_text for pattern in _TOOL_CALL_CAPABILITY_FAILURE_PATTERNS)


def _record_tool_call_capability_failure(model: str) -> None:
    """Increment the tool-call failure counter and degrade after 3 strikes."""
    with _DEGRADATION_LOCK:
        if model not in _MODEL_DEGRADATION_STATE:
            _MODEL_DEGRADATION_STATE[model] = {
                "tool_call_failure_count": 0,
                "force_text_json_fallback": False,
            }
        state = _MODEL_DEGRADATION_STATE[model]
        if state["force_text_json_fallback"]:
            return  # Already degraded; no need to recount
        state["tool_call_failure_count"] += 1
        if state["tool_call_failure_count"] >= 3:
            state["force_text_json_fallback"] = True
            logger.error(f"[call_structured] MODEL_DEGRADED: model={model} has reached {state['tool_call_failure_count']} consecutive tool-call capability failures; ALL future calls for this model in this process will use text-json fallback directly.")
        else:
            logger.warning(f"[call_structured] FAILURE_COUNT: model={model} tool-call capability failure count={state['tool_call_failure_count']}/3.")


def _record_tool_call_success(model: str) -> None:
    """Clear non-degraded tool-call failure count after a successful structured call."""
    with _DEGRADATION_LOCK:
        state = _MODEL_DEGRADATION_STATE.get(model)
        if not state or state["force_text_json_fallback"]:
            return
        if state["tool_call_failure_count"]:
            logger.info(f"[call_structured] FAILURE_COUNT_RESET: model={model} structured call succeeded after {state['tool_call_failure_count']} prior tool-call capability failure(s).")
        state["tool_call_failure_count"] = 0


def _get_model_degradation_state(model: str) -> dict[str, Any]:
    """Return the current degradation state for *model*."""
    return _MODEL_DEGRADATION_STATE.get(model, {"tool_call_failure_count": 0, "force_text_json_fallback": False})


def _detect_tool_call_capability_failure_from_response(raw: Any) -> bool:
    """Inspect the raw response / exception for tool-call capability failure signals.

    Returns True if the response indicates the provider cannot handle tool calling.

    Note: finish_reason="stop" with missing tool_calls is NOT treated as capability
    failure when valid structured text is still present. Only explicit protocol-level
    unsupported-tool errors count as capability failures.
    """
    if isinstance(raw, BaseException):
        return _is_tool_call_capability_failure(raw)

    if isinstance(raw, dict):
        # Check for error fields in the response
        error_msg = str(raw.get("error", raw.get("message", ""))).lower()
        if error_msg and _is_tool_call_capability_failure(Exception(error_msg)):
            return True
        # finish_reason="stop" with missing tool_calls is NOT capability failure
        # when valid structured text may still be present.
    return False


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


class StructuredSchemaError(RuntimeError):
    """Structured LLM response parsed as JSON but did not match the expected object shape."""

    def __init__(self, message: str, *, top_level_type: str) -> None:
        super().__init__(message)
        self.top_level_type = top_level_type


def _ensure_structured_object_payload(payload: Any) -> dict[str, Any]:
    """Require current structured callers to receive a JSON object."""
    if isinstance(payload, dict):
        return payload
    top_level_type = type(payload).__name__
    raise StructuredSchemaError(
        f"Structured LLM response must be a JSON object; got {top_level_type}",
        top_level_type=top_level_type,
    )


def _coerce_int_setting(value: Any, default: int | None, *, minimum: int | None = None) -> int | None:
    """Return integer settings only when the loaded value is concrete."""
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    if minimum is not None:
        return max(minimum, value)
    return value


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
    logger.info(f"Tokenizer fallback selected for model {model}: {DEFAULT_FALLBACK_TOKENIZER}. reason={reason}")


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
    """Fallback JSON parser for text-based response content.

    ⚠️  FALLBACK-ONLY PARSER — NOT THE DEFAULT STRUCTURED MECHANISM
    =================================================================
    This function is **only** invoked when:
    1. Tool-call arguments (from a structured tool_call response) fail to parse,
       and text content fallback is enabled.
    2. The model is degraded and the text-json extraction path is used directly.
    3. ``json_mode=True`` is used without tools (response_format=json_object path).

    It is **NOT** the primary mechanism for obtaining structured responses.
    The primary path is tool-call argument extraction via ``parse_chat_completion_json_response()``.

    This parser applies multiple heuristics to extract JSON from raw text,
    including markdown code block extraction, balanced brace matching, and
    common repair strategies for truncated or escaped content.

    Raises json.JSONDecodeError if all extraction strategies fail.
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

    logger.warning(f"robust_json_parse: all strategies failed; text length={len(original_text)}, preview={original_text[:120]!r}")
    raise json.JSONDecodeError(
        f"Could not parse JSON; original text length: {len(original_text)}",
        original_text,
        0,
    )


def call_structured(
    api: "APIBackend",
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict[str, Any] | None = None,
    json_mode: bool = False,
    reasoning_flag: bool = False,
    task_type: str | None = None,
    chat_cache_prefix: str = "",
    temperature: float | None = None,
    max_tokens: int | None = None,
    frequency_penalty: float | None = None,
    presence_penalty: float | None = None,
    seed: int | None = None,
    add_json_in_prompt: bool = False,
    allow_text_fallback: bool = True,
) -> dict[str, Any]:
    """Unified structured-completion entry for the once mining path.

    Three-stage strategy with process-local model degradation:
    1. If model is already degraded in this process, skip tool call and go
       directly to text-json extraction path.
    2. Otherwise, attempt tool call first.
    3. If tool-call capability failure occurs, count it; after 3 consecutive
       failures for the same model, degrade and switch to text-json path.

    Phase-1 contract:
    - When ``tools`` is provided, the call uses ``tools + tool_choice`` to
      request a tool-call response.  Tool-call arguments are parsed first.
    - When ``json_mode`` is True without tools, the call uses ``json_object``
      response format with text-based JSON parsing fallback.
    - ``allow_text_fallback`` controls whether non-tool-call text JSON parsing
      is permitted when tool calls are requested but not returned.
    - Dynamic-key ``factor_construct`` callers may still rely on text fallback
      internally; this function unifies the entry point.

    Policy gateway:
    - If ``LLM_SETTINGS.use_tool_calling`` is ``False`` and ``tools`` is
      provided, the call is downgraded: ``tools`` / ``tool_choice`` are
      cleared and ``json_mode`` is forced ``True``.  A short log records
      the fallback.
    - If ``use_tool_calling`` is ``True`` (default), tools pass through
      unchanged and ``json_mode`` is forced ``False`` when tools are present.

    Returns a dict parsed from tool-call arguments or text JSON content.
    Raises ``json.JSONDecodeError`` when all parsing strategies fail.
    """
    model_name = getattr(api, "chat_model", None) or getattr(api, "reasoning_model", None) or "<unknown>"

    # --- Policy gateway: enforce use_tool_calling config ---
    effective_tools = tools
    effective_tool_choice = tool_choice
    effective_json_mode = json_mode

    if tools is not None and not LLM_SETTINGS.use_tool_calling:
        logger.info(f"[call_structured] POLICY: use_tool_calling is disabled; downgrading to json_mode path (tools cleared). model={model_name}")
        effective_tools = None
        effective_tool_choice = None
        effective_json_mode = True
    elif tools is not None:
        # When tools are actually used, disable json_mode to avoid double enforcement
        effective_json_mode = False

        # --- Stage 1: Check if model is already degraded ---
        degradation_state = _get_model_degradation_state(model_name)
        if degradation_state["force_text_json_fallback"]:
            logger.warning(f"[call_structured] DEGRADED_PATH: model={model_name} is degraded (failure_count={degradation_state['tool_call_failure_count']}); skipping tool call, using text-json extraction directly.")
            effective_tools = None
            effective_tool_choice = None
            effective_json_mode = True
        else:
            # Model is NOT degraded — proceeding with tool-call path
            logger.info(f"[call_structured] TOOL_CALL_PATH: model={model_name}; attempting tool-call first (tools={len(tools)}, tool_choice={tool_choice}).")
    # --------------------------------------------------------

    original_chat_stream = getattr(api, "chat_stream", None)
    # Unified structured streaming policy for the structured entry point.
    # This applies to both tool-call and degraded text-json structured paths.
    if original_chat_stream is not None:
        api.chat_stream = LLM_SETTINGS.structured_streaming_mode

    # Preserve None fallback semantic: if LLM_SETTINGS.max_retry is None,
    # fall back to the default (30) like _try_create_chat_completion_or_embedding does.
    max_retry_setting = getattr(api, "_max_retry_override", None)
    if max_retry_setting is None:
        max_retry_setting = getattr(LLM_SETTINGS, "max_retry", None)
    max_retry = _coerce_int_setting(max_retry_setting, 30, minimum=1)

    def _call_structured_once() -> dict[str, Any]:
        """Execute a single raw call + parse, without retry."""
        try:
            raw_call = api.__dict__.get("_try_create_chat_completion_or_embedding")
            if raw_call is None:
                raw_call = api._create_chat_completion_or_embedding_once
            raw = raw_call(
                messages=messages,
                chat_completion=True,
                chat_cache_prefix=chat_cache_prefix,
                json_mode=effective_json_mode,
                reasoning_flag=reasoning_flag,
                task_type=task_type,
                tools=effective_tools,
                tool_choice=effective_tool_choice,
                temperature=temperature,
                max_tokens=max_tokens,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
                seed=seed,
                add_json_in_prompt=add_json_in_prompt,
            )
        except Exception as exc:
            # --- Stage 3 (exception path): record capability failure if applicable ---
            if tools is not None and LLM_SETTINGS.use_tool_calling:
                if _is_tool_call_capability_failure(exc):
                    degradation_state = _get_model_degradation_state(model_name)
                    current_count = degradation_state["tool_call_failure_count"] + 1
                    logger.warning(f"[call_structured] CAPABILITY_FAILURE: model={model_name} tool-call capability error (count={current_count}/3); error={exc}")
                    _record_tool_call_capability_failure(model_name)
            raise

        # --- Stage 3 (response path): detect capability failure from response ---
        if tools is not None and LLM_SETTINGS.use_tool_calling and effective_tools is not None:
            if _detect_tool_call_capability_failure_from_response(raw):
                degradation_state = _get_model_degradation_state(model_name)
                current_count = degradation_state["tool_call_failure_count"] + 1
                logger.warning(f"[call_structured] CAPABILITY_FAILURE: model={model_name} tool-call capability failure detected in response (count={current_count}/3).")
                _record_tool_call_capability_failure(model_name)

        parsed = parse_chat_completion_json_response(raw, allow_text_fallback=allow_text_fallback)
        if tools is not None and LLM_SETTINGS.use_tool_calling and effective_tools is not None:
            _record_tool_call_success(model_name)
        return _ensure_structured_object_payload(parsed)

    try:
        return api._run_with_retry_and_model_switch(
            _call_structured_once,
            max_retry=max_retry,
            retry_label="call_structured",
            chat_completion=True,
            switch_model_on_failure=True,
        )
    finally:
        if original_chat_stream is not None:
            api.chat_stream = original_chat_stream


def parse_chat_completion_json_response(
    response: str | dict[str, Any],
    *,
    allow_text_fallback: bool = True,
) -> dict[str, Any]:
    """Parse chat-completion JSON via the unified normalizer.

    Parser precedence (delegated to normalize_and_parse):
    1. TOOL_CALL_PATH: tool_calls[].function.arguments (primary structured path).
    2. CONTENT_PATH: content field JSON.
    3. REASONING_PATH: reasoning_content field JSON.
    4. TEXT_FALLBACK_PATH: generic JSON extraction.

    Args:
        response: The raw response dict or string from the provider.
        allow_text_fallback: Whether to allow fallback to text-based JSON parsing.

    Returns:
        Parsed structured data as a dict.

    Raises:
        json.JSONDecodeError: When all parsing strategies fail.
    """
    if isinstance(response, dict):
        return normalize_and_parse(
            response,
            allow_text_fallback=allow_text_fallback,
            json_parser=robust_json_parse,
        )

    if not allow_text_fallback:
        raise json.JSONDecodeError("Text fallback disabled but response is not a dict", "", 0)

    # Response is a string — wrap as dict and normalize
    logger.info(f"[parse_response] TEXT_JSON_PATH: response is raw string; extracting JSON from text. length={len(response)}")
    return normalize_and_parse(
        {"content": response, "finish_reason": "stop"},
        allow_text_fallback=True,
        json_parser=robust_json_parse,
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
