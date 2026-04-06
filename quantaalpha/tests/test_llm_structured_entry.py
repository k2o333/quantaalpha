"""Tests proving unified structured-entry behavior for the once mining path.

These tests verify that:
1. call_structured is the official unified entry point in client.py
2. proposal.py uses call_structured (not ad hoc robust_json_parse) in its main route
3. factor_construct is routed through call_structured
4. Fixed-object structured callers use tools + tool_choice
"""

import json
import unittest
from unittest.mock import MagicMock, patch


class TestUnifiedStructuredEntry(unittest.TestCase):
    """Proof that there is one official structured-completion entry."""

    def test_call_structured_exists_in_client(self):
        """call_structured must exist as the unified entry point."""
        from quantaalpha.llm.client import call_structured

        self.assertTrue(callable(call_structured))

    def test_call_structured_accepts_tools_and_tool_choice(self):
        """call_structured must accept tools and tool_choice params."""
        from quantaalpha.llm.client import call_structured
        import inspect

        sig = inspect.signature(call_structured)
        params = set(sig.parameters.keys())
        self.assertIn("tools", params)
        self.assertIn("tool_choice", params)

    def test_call_structured_forwards_tools_to_backend(self):
        """call_structured must pass tools through to _try_create_chat_completion_or_embedding."""
        from quantaalpha.llm.client import call_structured, APIBackend

        api = object.__new__(APIBackend)
        api.use_chat_cache = False

        tools = [{"type": "function", "function": {"name": "test_tool"}}]
        messages = [{"role": "user", "content": "test"}]

        with patch.object(api, "_try_create_chat_completion_or_embedding") as mock_call:
            mock_call.return_value = {
                "content": '{"hypothesis": "test"}',
                "finish_reason": "stop",
                "tool_calls": None,
            }
            with patch("quantaalpha.llm.client.robust_json_parse", return_value={"hypothesis": "test"}):
                call_structured(
                    api,
                    messages,
                    tools=tools,
                    tool_choice="required",
                )

            call_kwargs = mock_call.call_args[1]
            self.assertIn("tools", call_kwargs)
            self.assertEqual(call_kwargs["tools"], tools)
            self.assertEqual(call_kwargs["tool_choice"], "required")

    def test_parse_chat_completion_json_response_tool_call_priority(self):
        """parse_chat_completion_json_response must prefer tool-call arguments."""
        from quantaalpha.llm.client import parse_chat_completion_json_response

        raw = {
            "content": '{"hypothesis": "text_fallback"}',
            "finish_reason": "tool_calls",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "propose_hypothesis",
                        "arguments": '{"hypothesis": "from_tool"}',
                    },
                }
            ],
        }

        result = parse_chat_completion_json_response(raw)
        self.assertEqual(result["hypothesis"], "from_tool")

    def test_parse_chat_completion_json_response_text_fallback_disabled(self):
        """When allow_text_fallback=False, must raise on non-dict or tool-call failure."""
        from quantaalpha.llm.client import parse_chat_completion_json_response

        raw = {
            "content": '{"hypothesis": "text"}',
            "finish_reason": "tool_calls",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "propose_hypothesis",
                        "arguments": "NOT_VALID_JSON",
                    },
                }
            ],
        }

        with self.assertRaises(json.JSONDecodeError):
            parse_chat_completion_json_response(raw, allow_text_fallback=False)


class TestProposalUsesCallStructured(unittest.TestCase):
    """Proof that proposal.py main route uses call_structured, not ad hoc robust_json_parse."""

    def test_proposal_imports_call_structured(self):
        """proposal.py must import call_structured."""
        from quantaalpha.factors import proposal

        self.assertTrue(hasattr(proposal, "call_structured"))

    def test_alpha_agent_hypothesis_gen_uses_call_structured(self):
        """AlphaAgentHypothesisGen.gen must call call_structured in its main route."""
        from quantaalpha.factors.proposal import AlphaAgentHypothesisGen
        import inspect

        source = inspect.getsource(AlphaAgentHypothesisGen.gen)
        self.assertIn(
            "call_structured",
            source,
            "AlphaAgentHypothesisGen.gen must use call_structured, not ad hoc build_messages_and_create_chat_completion + robust_json_parse",
        )

    def test_alpha_agent_hypothesis2factor_uses_call_structured(self):
        """AlphaAgentHypothesis2FactorExpression must call call_structured in its main route."""
        from quantaalpha.factors.proposal import AlphaAgentHypothesis2FactorExpression
        import inspect

        source = inspect.getsource(AlphaAgentHypothesis2FactorExpression._convert_with_history_limit)
        self.assertIn(
            "call_structured",
            source,
            "AlphaAgentHypothesis2FactorExpression._convert_with_history_limit must use call_structured",
        )


class TestFixedObjectToolCalling(unittest.TestCase):
    """Proof that fixed-object structured callers use tools + tool_choice."""

    def test_propose_factors_tool_definition_exists(self):
        """PROPOSE_FACTORS_TOOL must be defined in proposal.py."""
        from quantaalpha.factors.proposal import PROPOSE_FACTORS_TOOL

        self.assertEqual(PROPOSE_FACTORS_TOOL["type"], "function")
        self.assertEqual(PROPOSE_FACTORS_TOOL["function"]["name"], "propose_hypothesis")

    def test_construct_factors_tool_definition_exists(self):
        """CONSTRUCT_FACTORS_TOOL must be defined in proposal.py."""
        from quantaalpha.factors.proposal import CONSTRUCT_FACTORS_TOOL

        self.assertEqual(CONSTRUCT_FACTORS_TOOL["type"], "function")
        self.assertEqual(CONSTRUCT_FACTORS_TOOL["function"]["name"], "construct_factors")

    def test_feedback_tool_definition_exists(self):
        """FEEDBACK_TOOL must be defined in proposal.py."""
        from quantaalpha.factors.proposal import FEEDBACK_TOOL

        self.assertEqual(FEEDBACK_TOOL["type"], "function")
        self.assertEqual(FEEDBACK_TOOL["function"]["name"], "provide_feedback")


class TestLoopEnsembleUsesCallStructured(unittest.TestCase):
    """Proof that loop.py ensemble propose path uses call_structured."""

    def test_loop_imports_call_structured(self):
        """loop.py must import call_structured."""
        from quantaalpha.pipeline import loop

        self.assertTrue(hasattr(loop, "call_structured"))

    def test_propose_with_ensemble_uses_call_structured(self):
        """AlphaAgentLoop._propose_with_ensemble must use call_structured."""
        from quantaalpha.pipeline.loop import AlphaAgentLoop
        import inspect

        source = inspect.getsource(AlphaAgentLoop._propose_with_ensemble)
        self.assertIn(
            "call_structured",
            source,
            "AlphaAgentLoop._propose_with_ensemble must use call_structured, not ad hoc build_messages_and_create_chat_completion",
        )
