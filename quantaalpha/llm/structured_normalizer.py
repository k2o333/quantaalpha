"""
Structured LLM response normalizer.

This module provides a single normalization layer between raw LiteLLM/OpenAI-compatible
responses and structured parsing. All structured calls consume one normalized response
shape with a fixed precedence order: tool_calls -> content -> reasoning_content -> generic JSON.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from quantaalpha.log import logger


@dataclass
class NormalizedResponse:
    """One normalized internal shape for structured parsing.

    Attributes:
        provider_model: The model name from the provider.
        finish_reason: The finish reason from the provider.
        content: The message content text.
        reasoning_content: The reasoning content text (if available).
        tool_calls: The tool calls list (if available).
        raw: The original raw response dict.
    """

    provider_model: str = ""
    finish_reason: str = ""
    content: str | None = None
    reasoning_content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def normalize_response(raw: dict[str, Any]) -> NormalizedResponse:
    """Normalize a raw provider response into one consistent internal shape.

    This handles OpenAI/LiteLLM-compatible response formats and extracts the
    relevant fields into a NormalizedResponse.

    Args:
        raw: The raw response dict from the provider.

    Returns:
        A NormalizedResponse with extracted fields.
    """
    provider_model = raw.get("model", raw.get("provider_model", ""))
    finish_reason = raw.get("finish_reason", "")
    content = raw.get("content")
    reasoning_content = raw.get("reasoning_content")
    tool_calls = raw.get("tool_calls")

    # Normalize None to empty string for consistency
    if content is not None and not isinstance(content, str):
        content = str(content) if content else None
    if reasoning_content is not None and not isinstance(reasoning_content, str):
        reasoning_content = str(reasoning_content) if reasoning_content else None

    return NormalizedResponse(
        provider_model=provider_model,
        finish_reason=finish_reason,
        content=content,
        reasoning_content=reasoning_content,
        tool_calls=tool_calls,
        raw=raw,
    )


def _robust_json_parse(text: str) -> dict[str, Any]:
    """Parse JSON text with robust fallbacks.

    Args:
        text: The raw text that should contain JSON.

    Returns:
        Parsed JSON dict.

    Raises:
        json.JSONDecodeError: If all parsing strategies fail.
    """
    # Strategy 1: direct parse
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # Strategy 2: extract JSON code block
    import re

    json_block_pattern = r"```(?:json)?\s*\n?([\s\S]*?)\n?```"
    matches = re.findall(json_block_pattern, text)
    for match in matches:
        try:
            result = json.loads(match.strip())
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            continue

    # Strategy 3: balanced brace extraction
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
                candidate = text[start_idx : i + 1]
                try:
                    result = json.loads(candidate)
                    if isinstance(result, dict):
                        return result
                except json.JSONDecodeError:
                    continue

    logger.warning(f"_robust_json_parse: all strategies failed; text={text[:120]!r}")
    raise json.JSONDecodeError("Could not parse JSON from text", text, 0)


def _default_json_parser(text: str) -> dict[str, Any]:
    """Use the legacy parser when available so the normalizer does not weaken repairs."""
    try:
        from quantaalpha.llm.client import robust_json_parse as legacy_robust_json_parse
    except ImportError:
        return _robust_json_parse(text)
    return legacy_robust_json_parse(text)


def normalize_and_parse(
    raw: dict[str, Any],
    *,
    allow_text_fallback: bool = True,
    json_parser: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Normalize a raw response and parse structured data with fixed precedence.

    Parser precedence:
    1. tool_calls[].function.arguments (highest priority)
    2. content field JSON
    3. reasoning_content field JSON
    4. generic JSON extraction (lowest priority)

    Args:
        raw: The raw response dict from the provider.
        allow_text_fallback: Whether to allow fallback to text-based JSON parsing.
        json_parser: Optional parser override. When omitted, uses the local fallback parser.

    Returns:
        Parsed structured data as a dict.

    Raises:
        json.JSONDecodeError: When all parsing strategies fail and no structured data found.
    """
    normalized = normalize_response(raw)
    parser = json_parser or _default_json_parser

    # Priority 1: tool_calls[].function.arguments
    if normalized.tool_calls:
        for tool_call in normalized.tool_calls:
            if not isinstance(tool_call, dict):
                continue
            function_payload = tool_call.get("function")
            if not isinstance(function_payload, dict):
                continue
            arguments = function_payload.get("arguments")
            if not isinstance(arguments, str) or not arguments.strip():
                continue
            try:
                parsed = parser(arguments)
                logger.info("[normalize_and_parse] TOOL_CALL_PATH: parsed tool-call arguments.")
                return parsed
            except json.JSONDecodeError as exc:
                tool_name = function_payload.get("name", "<unknown>")
                logger.warning(
                    f"[normalize_and_parse] TOOL_CALL_PARSE_FAILED: tool={tool_name}; "
                    f"continuing to next precedence level. error={exc}"
                )
                # Continue to next precedence level

    # Priority 2: content field JSON
    if isinstance(normalized.content, str) and normalized.content.strip():
        try:
            parsed = parser(normalized.content)
            logger.info("[normalize_and_parse] CONTENT_PATH: parsed content field JSON.")
            return parsed
        except json.JSONDecodeError:
            logger.info("[normalize_and_parse] CONTENT_PARSE_FAILED: content not valid JSON, trying next level.")

    # Priority 3: reasoning_content field JSON
    if isinstance(normalized.reasoning_content, str) and normalized.reasoning_content.strip():
        try:
            parsed = parser(normalized.reasoning_content)
            logger.info("[normalize_and_parse] REASONING_PATH: parsed reasoning_content field JSON.")
            return parsed
        except json.JSONDecodeError:
            logger.info("[normalize_and_parse] REASONING_PARSE_FAILED: reasoning_content not valid JSON.")

    # Priority 4: generic text fallback
    if allow_text_fallback:
        # Try the raw response as text if content wasn't parseable
        raw_text = normalized.content or ""
        if not raw_text.strip():
            raw_text = normalized.reasoning_content or ""

        if raw_text.strip():
            try:
                parsed = parser(raw_text)
                logger.info("[normalize_and_parse] TEXT_FALLBACK_PATH: parsed from raw text.")
                return parsed
            except json.JSONDecodeError:
                pass

    raise json.JSONDecodeError(
        "No structured data found in any precedence level (tool_calls -> content -> reasoning_content -> text)",
        str(raw)[:200],
        0,
    )
