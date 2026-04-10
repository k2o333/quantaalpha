"""Tests for the structured LLM response normalizer.

These tests verify the normalized parser precedence:
1. tool_calls[].function.arguments (highest priority)
2. content field JSON
3. reasoning_content field JSON
4. generic JSON extraction (lowest priority)

And verify that finish_reason="stop" with missing tool_calls is NOT treated
as capability failure when valid structured text is present.
"""

import json

import pytest


class TestNormalizedParserPrecedence:
    """Tests proving the normalized parser follows strict precedence order."""

    def test_tool_calls_prefer_content_over_reasoning(self):
        """When tool_calls exist with valid arguments, prefer them over reasoning_content."""
        from quantaalpha.llm.structured_normalizer import normalize_and_parse

        raw_response = {
            "finish_reason": "tool_calls",
            "content": '{"source": "content", "value": 1}',
            "reasoning_content": '{"source": "reasoning", "value": 2}',
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "emit_json",
                        "arguments": '{"source": "tool_calls", "value": 3}',
                    },
                }
            ],
        }

        result = normalize_and_parse(raw_response, allow_text_fallback=True)
        assert result["source"] == "tool_calls"
        assert result["value"] == 3

    def test_content_fallback_when_no_tool_calls(self):
        """When tool_calls are absent, parse content field as JSON."""
        from quantaalpha.llm.structured_normalizer import normalize_and_parse

        raw_response = {
            "finish_reason": "stop",
            "content": '{"source": "content", "value": 42}',
            "reasoning_content": '{"source": "reasoning", "value": 99}',
            "tool_calls": None,
        }

        result = normalize_and_parse(raw_response, allow_text_fallback=True)
        assert result["source"] == "content"
        assert result["value"] == 42

    def test_reasoning_content_fallback_when_content_empty(self):
        """When content is empty/None but reasoning_content has valid JSON, use reasoning_content."""
        from quantaalpha.llm.structured_normalizer import normalize_and_parse

        raw_response = {
            "finish_reason": "stop",
            "content": None,
            "reasoning_content": '{"source": "reasoning", "value": 77}',
            "tool_calls": None,
        }

        result = normalize_and_parse(raw_response, allow_text_fallback=True)
        assert result["source"] == "reasoning"
        assert result["value"] == 77

    def test_reasoning_content_fallback_when_content_not_json(self):
        """When content is not valid JSON but reasoning_content is, use reasoning_content."""
        from quantaalpha.llm.structured_normalizer import normalize_and_parse

        raw_response = {
            "finish_reason": "stop",
            "content": "This is just plain text, not JSON",
            "reasoning_content": '{"source": "reasoning", "value": 88}',
            "tool_calls": None,
        }

        result = normalize_and_parse(raw_response, allow_text_fallback=True)
        assert result["source"] == "reasoning"
        assert result["value"] == 88

    def test_content_fallback_preserves_existing_json_repair_behavior(self):
        """Structured parsing must keep the old JSON repair capability for malformed text payloads."""
        from quantaalpha.llm.structured_normalizer import normalize_and_parse

        raw_response = {
            "finish_reason": "stop",
            "content": '{"source": "content", "value": 42,}',
            "tool_calls": None,
        }

        result = normalize_and_parse(raw_response, allow_text_fallback=True)
        assert result["source"] == "content"
        assert result["value"] == 42


class TestFinishReasonStopNotCapabilityFailure:
    """Tests proving finish_reason="stop" with missing tool_calls is not auto-capability-failure."""

    def test_finish_reason_stop_with_valid_content_not_capability_failure(self):
        """finish_reason="stop" plus missing tool_calls but valid JSON content must not be capability failure."""
        from quantaalpha.llm.structured_normalizer import normalize_and_parse

        raw_response = {
            "finish_reason": "stop",
            "content": '{"hypothesis": "test_hypothesis", "confidence": 0.9}',
            "tool_calls": None,
        }

        # This should parse successfully, not raise or signal capability failure
        result = normalize_and_parse(raw_response, allow_text_fallback=True)
        assert result["hypothesis"] == "test_hypothesis"
        assert result["confidence"] == 0.9

    def test_finish_reason_stop_with_valid_reasoning_content_not_capability_failure(self):
        """finish_reason="stop" plus missing tool_calls but valid reasoning_content JSON must not be capability failure."""
        from quantaalpha.llm.structured_normalizer import normalize_and_parse

        raw_response = {
            "finish_reason": "stop",
            "content": "",
            "reasoning_content": '{"result": "from_reasoning"}',
            "tool_calls": None,
        }

        result = normalize_and_parse(raw_response, allow_text_fallback=True)
        assert result["result"] == "from_reasoning"


class TestOldBehaviorRegression:
    """Stronger regression test: proves old behavior (finish_reason=stop + no tool_calls = failure) is gone.

    This test MUST FAIL before the fix because the old code treated finish_reason="stop"
    with missing tool_calls as a capability failure signal. After the fix, the normalizer
    correctly parses valid structured content regardless of finish_reason.
    """

    def test_old_capability_failure_logic_is_removed(self):
        """The old _detect_tool_call_capability_failure must NOT flag finish_reason=stop as failure.

        Before the fix, this test would fail because the function returned True for
        finish_reason="stop" with None tool_calls. After the fix, it correctly returns False.
        """
        from quantaalpha.llm.client import _detect_tool_call_capability_failure_from_response

        # This is the exact pattern that used to trigger capability failure
        old_capability_failure_pattern = {
            "content": "Some text",
            "finish_reason": "stop",
            "tool_calls": None,
        }

        # After the fix, this must NOT be treated as capability failure
        result = _detect_tool_call_capability_failure_from_response(old_capability_failure_pattern)

        # This assertion MUST PASS after the fix (proving old behavior is removed)
        assert result is False, (
            "Old capability failure logic must not flag finish_reason=stop as failure "
            "when valid structured text may be present"
        )


class TestNormalizedResponseShape:
    """Tests proving the normalizer produces one consistent internal shape."""

    def test_normalized_shape_has_required_fields(self):
        """The normalizer must return a dict with provider_model, finish_reason, content, reasoning_content, tool_calls, raw."""
        from quantaalpha.llm.structured_normalizer import normalize_response

        raw_response = {
            "finish_reason": "stop",
            "content": "test content",
            "model": "glm-4.7-flash",
        }

        normalized = normalize_response(raw_response)
        assert hasattr(normalized, "provider_model")
        assert hasattr(normalized, "finish_reason")
        assert hasattr(normalized, "content")
        assert hasattr(normalized, "reasoning_content")
        assert hasattr(normalized, "tool_calls")
        assert hasattr(normalized, "raw")

    def test_normalized_shape_extract_tool_calls(self):
        """The normalizer must correctly extract tool_calls into the normalized shape."""
        from quantaalpha.llm.structured_normalizer import normalize_response

        raw_response = {
            "finish_reason": "tool_calls",
            "content": None,
            "model": "MiniMax-M2.7",
            "tool_calls": [
                {
                    "id": "call_abc",
                    "type": "function",
                    "function": {
                        "name": "test_tool",
                        "arguments": '{"key": "value"}',
                    },
                }
            ],
        }

        normalized = normalize_response(raw_response)
        assert normalized.finish_reason == "tool_calls"
        assert normalized.provider_model == "MiniMax-M2.7"
        assert len(normalized.tool_calls) == 1
        assert normalized.tool_calls[0]["function"]["name"] == "test_tool"
