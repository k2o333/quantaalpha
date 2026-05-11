"""Tests proving unified structured-entry behavior for the once mining path.

These tests verify that:
1. call_structured is the official unified entry point in client.py
2. proposal.py uses call_structured (not ad hoc robust_json_parse) in its main route
3. factor_construct is routed through call_structured
4. Fixed-object structured callers use tools + tool_choice
5. AlphaAgentHypothesis2FactorExpression is instantiable (not abstract) at runtime
6. CONSTRUCT_FACTORS_TOOL payload shape matches what _build_experiment_from_dict consumes
"""

import json
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

_fake_factor_experiment = types.ModuleType("quantaalpha.factors.experiment")


class _StubQlibFactorExperiment:
    def __init__(self, tasks=None, sub_tasks=None):
        self.sub_tasks = sub_tasks if sub_tasks is not None else (tasks or [])
        self.result = None
        self.based_experiments = []


_fake_factor_experiment.QlibFactorExperiment = _StubQlibFactorExperiment
sys.modules.setdefault("quantaalpha.factors.experiment", _fake_factor_experiment)


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
        """call_structured must pass tools through to the backend call."""
        from quantaalpha.llm.client import call_structured, APIBackend

        api = object.__new__(APIBackend)
        api.use_chat_cache = False
        api._provider_pool = None
        api.retry_wait_seconds = 0

        tools = [{"type": "function", "function": {"name": "test_tool"}}]
        messages = [{"role": "user", "content": "test"}]

        with patch.object(api, "_create_chat_completion_or_embedding_once") as mock_call:
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
        """When allow_text_fallback=False and all precedence levels fail, must raise."""
        from quantaalpha.llm.client import parse_chat_completion_json_response

        # When tool_calls fail and content is also not valid JSON, should raise
        raw = {
            "content": "NOT_VALID_JSON_EITHER",
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

    def test_alpha_agent_hypothesis2factor_multi_hypothesis_uses_call_structured(self):
        """The multi-hypothesis construct path must also use call_structured."""
        from quantaalpha.factors.proposal import AlphaAgentHypothesis2FactorExpression
        import inspect

        source = inspect.getsource(AlphaAgentHypothesis2FactorExpression.convert_multi_hypothesis)
        self.assertIn(
            "call_structured",
            source,
            "AlphaAgentHypothesis2FactorExpression.convert_multi_hypothesis must use call_structured",
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
        """AlphaAgentLoop._call_ensemble_model must use call_structured."""
        from quantaalpha.pipeline.loop import AlphaAgentLoop
        import inspect

        source = inspect.getsource(AlphaAgentLoop._call_ensemble_model)
        self.assertIn(
            "call_structured",
            source,
            "AlphaAgentLoop._call_ensemble_model must use call_structured",
        )


class TestAlphaAgentHypothesis2FactorExpressionInstantiable(unittest.TestCase):
    """Proof that AlphaAgentHypothesis2FactorExpression is NOT abstract at runtime.

    This is the critical runtime instantiation test: the class must be
    instantiable without TypeError about missing abstract methods.
    """

    def test_class_is_instantiable_not_abstract(self):
        """AlphaAgentHypothesis2FactorExpression must be instantiable.

        Before the fix, this raises:
        TypeError: Can't instantiate abstract class AlphaAgentHypothesis2FactorExpression
        without an implementation for abstract method 'convert_response'
        """
        from quantaalpha.factors.proposal import AlphaAgentHypothesis2FactorExpression

        # Should not raise TypeError about abstract methods
        instance = AlphaAgentHypothesis2FactorExpression()
        self.assertIsNotNone(instance)

    def test_convert_response_method_exists(self):
        """AlphaAgentHypothesis2FactorExpression must have convert_response method.

        The parent class LLMHypothesis2Experiment declares convert_response as
        @abstractmethod. If this method is not overridden, the class is abstract
        and cannot be instantiated.
        """
        from quantaalpha.factors.proposal import AlphaAgentHypothesis2FactorExpression
        import inspect

        # convert_response must be defined on the subclass itself, not inherited as abstract
        self.assertTrue(
            hasattr(AlphaAgentHypothesis2FactorExpression, "convert_response"),
            "AlphaAgentHypothesis2FactorExpression must implement convert_response",
        )

        # The method should be callable (not abstract)
        method = getattr(AlphaAgentHypothesis2FactorExpression, "convert_response")
        # It should be a regular function, not an abstract method
        self.assertFalse(
            getattr(method, "__isabstractmethod__", False),
            "convert_response must not be abstract",
        )


class TestConstructPayloadShape(unittest.TestCase):
    """Proof that CONSTRUCT_FACTORS_TOOL payload shape matches consumer path.

    The tool schema defines factors as dynamic keys:
      {"factors": {"factor_name_A": {"description": ..., "expression": ..., ...}, ...}}

    The consumer (_build_experiment_from_dict) iterates response_dict directly:
      for factor_name in response_dict:
          factor_data = response_dict.get(factor_name, {})

    These must agree on one concrete shape end-to-end.
    """

    def test_construct_factors_tool_schema_has_factors_object(self):
        """CONSTRUCT_FACTORS_TOOL schema must have 'factors' as a dynamic-key object."""
        from quantaalpha.factors.proposal import CONSTRUCT_FACTORS_TOOL

        params = CONSTRUCT_FACTORS_TOOL["function"]["parameters"]
        self.assertIn("factors", params["properties"])
        # The factors property should be an object type
        factors_prop = params["properties"]["factors"]
        self.assertEqual(factors_prop.get("type"), "object")
        # "factors" should be in required
        self.assertIn("factors", params.get("required", []))

    def test_construct_factors_tool_schema_requires_factor_payload_fields(self):
        """Dynamic factor payloads must require the fields consumed by the constructor."""
        from quantaalpha.factors.proposal import CONSTRUCT_FACTORS_TOOL

        factors_prop = CONSTRUCT_FACTORS_TOOL["function"]["parameters"]["properties"]["factors"]
        payload_schema = factors_prop.get("additionalProperties")

        self.assertIsInstance(payload_schema, dict)
        self.assertEqual(payload_schema.get("type"), "object")
        for field in ("description", "formulation", "expression", "variables"):
            self.assertIn(field, payload_schema.get("properties", {}))
            self.assertIn(field, payload_schema.get("required", []))

    def test_build_experiment_from_dict_consumes_same_shape(self):
        """_build_experiment_from_dict must consume the wrapped tool-call shape."""
        from quantaalpha.factors.proposal import AlphaAgentHypothesis2FactorExpression
        from quantaalpha.factors.coder.factor import FactorTask

        instance = AlphaAgentHypothesis2FactorExpression()

        response_dict = {
            "factors": {
                "test_factor_alpha": {
                    "description": "A test factor",
                    "formulation": "Mean reversion over N days",
                    "expression": "ts_mean($close, 5)",
                    "variables": {},
                }
            }
        }

        exp = instance._build_experiment_from_dict(response_dict, MagicMock())

        self.assertEqual(len(exp.tasks), 1)
        task = exp.tasks[0]
        self.assertIsInstance(task, FactorTask)
        self.assertEqual(task.factor_name, "test_factor_alpha")
        self.assertEqual(task.factor_description, "A test factor")
        self.assertEqual(task.factor_expression, "ts_mean($close, 5)")

    def test_construct_payload_end_to_end_shape(self):
        """End-to-end: tool schema -> LLM response -> consumer must agree on shape.

        This proves the runtime contract is one shape end-to-end.
        """
        from quantaalpha.factors.proposal import (
            CONSTRUCT_FACTORS_TOOL,
            AlphaAgentHypothesis2FactorExpression,
        )

        # Tool schema expects: {"factors": {dynamic_key: {description, formulation, expression, variables}}}
        factors_schema = CONSTRUCT_FACTORS_TOOL["function"]["parameters"]["properties"]["factors"]
        self.assertEqual(factors_schema["type"], "object")

        simulated_llm_response = {
            "factors": {
                "my_factor_001": {
                    "description": "Volatility-adjusted momentum",
                    "formulation": "std(high-low, 20) / (std(abs(delta(open,1)), 20) + 1e-8)",
                    "expression": "ts_std($high - $low, 20) / (ts_std(abs(ts_delta($open, 1)), 20) + 1e-8)",
                    "variables": {"high": "daily.high", "low": "daily.low", "open": "daily.open"},
                }
            }
        }

        instance = AlphaAgentHypothesis2FactorExpression()
        exp = instance._build_experiment_from_dict(simulated_llm_response, MagicMock())

        self.assertEqual(len(exp.tasks), 1)
        self.assertEqual(exp.tasks[0].factor_name, "my_factor_001")
        self.assertEqual(
            exp.tasks[0].factor_expression,
            "ts_std($high - $low, 20) / (ts_std(abs(ts_delta($open, 1)), 20) + 1e-8)",
        )

    def test_convert_response_handles_wrapped_tool_payload(self):
        """convert_response must parse wrapped tool-call JSON into an experiment."""
        from quantaalpha.factors.proposal import AlphaAgentHypothesis2FactorExpression

        instance = AlphaAgentHypothesis2FactorExpression()
        response = json.dumps(
            {
                "factors": {
                    "wrapped_factor": {
                        "description": "Wrapped payload",
                        "formulation": "Example",
                        "expression": "ts_mean($close, 3)",
                        "variables": {},
                    }
                }
            }
        )

        exp = instance.convert_response(response, MagicMock())

        self.assertEqual(len(exp.tasks), 1)
        self.assertEqual(exp.tasks[0].factor_name, "wrapped_factor")
        self.assertEqual(exp.tasks[0].factor_expression, "ts_mean($close, 3)")


class TestCompatibilityWrapperDelegation(unittest.TestCase):
    """Step 2: 为兼容入口转调写失败测试

    These tests verify that:
    - build_messages_and_create_chat_completion_json() internally calls call_structured()
    - The old entry point still returns dict by default (backward compatibility)
    - When model is degraded, the old entry uses text JSON extraction, not tools
    """

    def _make_backend(self, model_name="gpt-4-turbo"):
        """Create a minimal APIBackend mock for testing."""
        from quantaalpha.llm.client import APIBackend

        backend = object.__new__(APIBackend)
        backend.use_azure = False
        backend.use_llama2 = False
        backend.use_gcr_endpoint = False
        backend.chat_stream = False
        backend.use_chat_cache = False
        backend.chat_model = model_name
        backend.reasoning_model = ""
        backend.chat_client = MagicMock()
        backend.cache = MagicMock()
        backend.cache.chat_get.return_value = None
        backend.task_model_map = {}
        backend.routing_default = ""
        backend.chat_model_map = {}
        backend.chat_api_key = "test"
        backend.base_url = None
        backend.embedding_api_key = ""
        backend.embedding_base_url = None
        backend.encoder = None
        backend.chat_seed = None
        backend.retry_wait_seconds = 1
        backend.dump_chat_cache = False
        return backend

    def test_compatibility_wrapper_calls_call_structured(self):
        """build_messages_and_create_chat_completion_json must delegate to call_structured."""
        import inspect
        from quantaalpha.llm.client import APIBackend

        source = inspect.getsource(APIBackend.build_messages_and_create_chat_completion_json)
        self.assertIn(
            "call_structured",
            source,
            "build_messages_and_create_chat_completion_json must delegate to call_structured, "
            "not call _try_create_chat_completion_or_embedding directly",
        )

    def test_compatibility_wrapper_returns_dict_by_default(self):
        """The old entry point must still return dict for backward compatibility."""
        from quantaalpha.llm.client import call_structured

        backend = self._make_backend()
        backend._create_chat_completion_or_embedding_once = MagicMock(
            return_value={
                "content": '{"result": "test"}',
                "finish_reason": "stop",
                "tool_calls": None,
            }
        )

        with patch("quantaalpha.llm.client.LLM_SETTINGS") as mock_settings:
            mock_settings.log_llm_chat_content = False
            mock_settings.use_tool_calling = True
            mock_settings.model_switch_threshold = 3
            mock_settings.max_retry = 30

            result = backend.build_messages_and_create_chat_completion_json(
                user_prompt="test",
                tools=[{"type": "function", "function": {"name": "test_tool"}}],
                tool_choice="required",
            )

        self.assertIsInstance(result, dict)
        self.assertEqual(result, {"result": "test"})

    def test_compatibility_wrapper_uses_text_json_when_model_degraded(self):
        """When model is degraded, the old entry must use text JSON path, not tools."""
        import pytest
        from quantaalpha.llm.client import call_structured, _MODEL_DEGRADATION_STATE

        # Clear any leftover degradation state from previous tests
        _MODEL_DEGRADATION_STATE.clear()

        backend = self._make_backend()
        backend.retry_wait_seconds = 0  # No sleep in tests
        captured_kwargs_list = []

        def _capture(**kwargs):
            captured_kwargs_list.append(kwargs)
            return {"content": '{"hypothesis": "degraded_test"}', "finish_reason": "stop", "tool_calls": None}

        with patch("quantaalpha.llm.client.LLM_SETTINGS") as mock_settings:
            mock_settings.log_llm_chat_content = False
            mock_settings.use_tool_calling = True
            mock_settings.model_switch_threshold = 3
            mock_settings.max_retry = 5

            # Degrade the model first with 3 failures
            for i in range(3):
                backend._create_chat_completion_or_embedding_once = MagicMock(
                    side_effect=Exception("tools parameter is not supported")
                )
                with pytest.raises(RuntimeError, match="Failed to create call_structured after 5 retries"):
                    call_structured(
                        backend,
                        [{"role": "user", "content": f"degrade {i}"}],
                        tools=[{"type": "function", "function": {"name": "test_tool"}}],
                        tool_choice="required",
                        allow_text_fallback=True,
                    )

            # Now use the compatibility wrapper
            captured_kwargs_list.clear()
            backend._create_chat_completion_or_embedding_once = MagicMock(side_effect=_capture)

            result = backend.build_messages_and_create_chat_completion_json(
                user_prompt="test after degradation",
                tools=[{"type": "function", "function": {"name": "test_tool"}}],
                tool_choice="required",
            )

        # After degradation, the wrapper must call with tools=None and json_mode=True
        self.assertEqual(len(captured_kwargs_list), 1)
        call_kwargs = captured_kwargs_list[0]
        self.assertIsNone(call_kwargs["tools"], "Degraded model must not use tools via compatibility wrapper")
        self.assertTrue(call_kwargs["json_mode"], "Degraded model must use json_mode via compatibility wrapper")
        self.assertIsInstance(result, dict, "Compatibility wrapper must still return dict")
        self.assertEqual(result, {"hypothesis": "degraded_test"})
