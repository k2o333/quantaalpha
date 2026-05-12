"""Tests for factor proposal retry diagnostics: last failure reason and bounded feedback."""
import pytest
from unittest.mock import MagicMock, patch, call

try:
    from quantaalpha.factors.proposal import _bound_feedback_accumulation
    _HAS_BOUNDED_FEEDBACK = True
except ImportError:
    _bound_feedback_accumulation = None
    _HAS_BOUNDED_FEEDBACK = False


def test_parse_diagnostic_returns_error_message_for_unbalanced_parentheses():
    """FactorRegulator.parse_diagnostic must return (False, error_message) for unbalanced expressions."""
    from quantaalpha.factors.regulator.factor_regulator import FactorRegulator

    ok, error = FactorRegulator().parse_diagnostic("RANK($close))")

    assert ok is False
    assert error is not None
    assert len(error) > 0
    # Must mention a concrete parser failure signal
    assert (
        "Unclosed parentheses" in error
        or "Expected end of text" in error
        or "ParseException" in error
        or "parse" in error.lower()
        or "Unbalanced parentheses" in error
    )


def test_construct_prompt_requires_parentheses_balance():
    """The hypothesis2experiment system_prompt must contain explicit parentheses balance rules."""
    from quantaalpha.factors.proposal import qa_prompt_dict

    system_prompt = qa_prompt_dict["hypothesis2experiment"]["system_prompt"]

    assert "Every opening parenthesis" in system_prompt
    assert "matching closing parenthesis" in system_prompt
    assert "Do not add trailing unmatched" in system_prompt


class TestConvertReportsLastFailureReason:
    """_convert_with_history_limit must include last failure reason in final RuntimeError."""

    def _make_h2e(self):
        """Create a minimal AlphaAgentHypothesis2FactorExpression for testing."""
        from quantaalpha.factors.proposal import AlphaAgentHypothesis2FactorExpression

        h2e = object.__new__(AlphaAgentHypothesis2FactorExpression)
        h2e.factor_regulator = MagicMock()
        h2e.factor_regulator.parse_diagnostic.return_value = (True, None)
        h2e.data_capabilities = None
        h2e.targets = []
        h2e.consistency_enabled = False
        h2e._quality_gate = None  # Use private attribute to avoid property setter issue
        return h2e

    def test_unparsable_expression_reports_last_failure(self):
        """When expression is unparsable on every retry, final RuntimeError must contain
        'last failure reason: unparsable expression'."""
        from quantaalpha.factors.proposal import AlphaAgentHypothesis2FactorExpression

        h2e = self._make_h2e()
        h2e.factor_regulator.parse_diagnostic.return_value = (False, "mock parse error")

        mock_trace = MagicMock()
        mock_trace.scen.data_capabilities = None
        mock_trace.scen.get_scenario_all_desc.return_value = "mock"
        mock_trace.scen.background = "mock"
        mock_trace.hist = MagicMock()
        mock_trace.hist.__len__ = MagicMock(return_value=0)
        mock_trace.hist.__bool__ = MagicMock(return_value=False)

        mock_hypothesis = MagicMock()
        mock_hypothesis.__str__ = MagicMock(return_value="test hypothesis")

        with patch.object(AlphaAgentHypothesis2FactorExpression, 'prepare_context',
                          return_value=({"target_hypothesis": "test", "experiment_output_format": "",
                                         "hypothesis_and_feedback": "fb", "function_lib_description": "fl",
                                         "target_list": [], "RAG": None, "financial_pit_context_hint": ""}, True)):
            with patch("quantaalpha.factors.proposal_expression.Environment") as MockEnv:
                mock_template = MagicMock()
                mock_template.render.return_value = "mock prompt"
                MockEnv.return_value.from_string.return_value = mock_template

                with patch("quantaalpha.factors.proposal_expression.APIBackend") as MockAPI:
                    mock_api = MagicMock()
                    mock_api.build_messages.return_value = [{"role": "user", "content": "test"}]
                    MockAPI.return_value = mock_api

                    with patch("quantaalpha.factors.proposal_expression.logger") as mock_logger:
                        with patch("quantaalpha.factors.proposal_expression.call_structured") as mock_call:
                            # Always return a valid-looking response with unparsable expression
                            mock_call.return_value = {"factor_A": {"expression": "INVALID_EXPR()", "description": "test", "formulation": "test"}}

                            with pytest.raises(RuntimeError) as exc_info:
                                h2e._convert_with_history_limit(mock_hypothesis, mock_trace, 6)

                            error_msg = str(exc_info.value)
                            assert "last failure reason" in error_msg.lower()
                            assert "unparsable" in error_msg.lower() or "parsable" in error_msg.lower()
                            warning_text = "\n".join(str(args[0]) for args, _ in mock_logger.warning.call_args_list if args)
                            assert "[retry attempt 1/2]" in warning_text
                            assert "unparsable expression for factor_A" in warning_text

    def test_unparsable_expression_feedback_is_added_to_retry_prompt(self):
        """When expression is unparsable, the next retry user_prompt must contain parser-error feedback."""
        from quantaalpha.factors.proposal import AlphaAgentHypothesis2FactorExpression
        from quantaalpha.factors.regulator.factor_regulator import FactorRegulator

        h2e = object.__new__(AlphaAgentHypothesis2FactorExpression)
        # Use a real FactorRegulator so parse_diagnostic is real
        h2e.factor_regulator = FactorRegulator()
        h2e.data_capabilities = None
        h2e.targets = []
        h2e.consistency_enabled = False
        h2e._quality_gate = None

        mock_trace = MagicMock()
        mock_trace.scen.data_capabilities = None
        mock_trace.scen.get_scenario_all_desc.return_value = "mock"
        mock_trace.scen.background = "mock"
        mock_trace.hist = MagicMock()
        mock_trace.hist.__len__ = MagicMock(return_value=0)
        mock_trace.hist.__bool__ = MagicMock(return_value=False)

        mock_hypothesis = MagicMock()
        mock_hypothesis.__str__ = MagicMock(return_value="test hypothesis")

        seen_user_prompts = []

        def fake_render(**kwargs):
            prompt = f"feedback={kwargs.get('expression_duplication')}"
            seen_user_prompts.append(prompt)
            return prompt

        with patch.object(AlphaAgentHypothesis2FactorExpression, 'prepare_context',
                          return_value=({"target_hypothesis": "test", "experiment_output_format": "",
                                         "hypothesis_and_feedback": "fb", "function_lib_description": "fl",
                                         "target_list": [], "RAG": None, "financial_pit_context_hint": ""}, True)):
            with patch("quantaalpha.factors.proposal_expression.Environment") as MockEnv:
                mock_template = MagicMock()
                mock_template.render.side_effect = fake_render
                MockEnv.return_value.from_string.return_value = mock_template

                with patch("quantaalpha.factors.proposal_expression.APIBackend") as MockAPI:
                    mock_api = MagicMock()
                    mock_api.build_messages.return_value = [{"role": "user", "content": "test"}]
                    MockAPI.return_value = mock_api

                    with patch("quantaalpha.factors.proposal_expression.call_structured") as mock_call:
                        # Return an unbalanced expression
                        mock_call.return_value = {
                            "factor_A": {
                                "expression": "RANK($close))",
                                "description": "test",
                                "formulation": "test"
                            }
                        }

                        with pytest.raises(RuntimeError) as exc_info:
                            h2e._convert_with_history_limit(mock_hypothesis, mock_trace, 6)

                        error_msg = str(exc_info.value)
                        assert "last failure reason" in error_msg.lower()
                        assert "unparsable expression" in error_msg.lower()

        # At least one retry prompt after the first must contain the required feedback phrases
        retry_prompts = seen_user_prompts[1:]  # skip the first prompt
        assert len(retry_prompts) > 0, "Expected at least one retry prompt"

        combined_retry = "\n".join(retry_prompts)
        assert "Expression Syntax Check Failed" in combined_retry
        assert "Parser error" in combined_retry
        assert "Ensure every opening parenthesis" in combined_retry
        assert "Do not return the same expression again" in combined_retry
        assert "factor_A" in combined_retry

    def test_capability_validation_failure_reports_last_failure(self):
        """When capability validation always fails, final RuntimeError must mention capability validation."""
        from quantaalpha.factors.proposal import AlphaAgentHypothesis2FactorExpression

        h2e = self._make_h2e()
        h2e.factor_regulator.parse_diagnostic.return_value = (True, None)
        # Make capability validation always fail
        h2e._validate_expression_capabilities = MagicMock(return_value=(False, "Unsupported fields: disallowed_field"))

        mock_trace = MagicMock()
        mock_trace.scen.data_capabilities = None
        mock_trace.scen.get_scenario_all_desc.return_value = "mock"
        mock_trace.scen.background = "mock"
        mock_trace.hist = MagicMock()
        mock_trace.hist.__len__ = MagicMock(return_value=0)
        mock_trace.hist.__bool__ = MagicMock(return_value=False)

        mock_hypothesis = MagicMock()
        mock_hypothesis.__str__ = MagicMock(return_value="test hypothesis")

        with patch.object(AlphaAgentHypothesis2FactorExpression, 'prepare_context',
                          return_value=({"target_hypothesis": "test", "experiment_output_format": "",
                                         "hypothesis_and_feedback": "fb", "function_lib_description": "fl",
                                         "target_list": [], "RAG": None, "financial_pit_context_hint": ""}, True)):
            with patch("quantaalpha.factors.proposal_expression.Environment") as MockEnv:
                mock_template = MagicMock()
                mock_template.render.return_value = "mock prompt"
                MockEnv.return_value.from_string.return_value = mock_template

                with patch("quantaalpha.factors.proposal_expression.APIBackend") as MockAPI:
                    mock_api = MagicMock()
                    mock_api.build_messages.return_value = [{"role": "user", "content": "test"}]
                    MockAPI.return_value = mock_api

                    with patch("quantaalpha.factors.proposal_expression.call_structured") as mock_call:
                        mock_call.return_value = {"factor_A": {"expression": "VALID(x)", "description": "test"}}

                        with pytest.raises(RuntimeError) as exc_info:
                            h2e._convert_with_history_limit(mock_hypothesis, mock_trace, 6)

                        error_msg = str(exc_info.value)
                        assert "last failure reason" in error_msg.lower()
                        assert "capabilit" in error_msg.lower()

    def test_expression_acceptability_failure_reports_last_failure(self):
        """When expression acceptability check always fails, final RuntimeError must mention it."""
        from quantaalpha.factors.proposal import AlphaAgentHypothesis2FactorExpression

        h2e = self._make_h2e()
        h2e.factor_regulator.parse_diagnostic.return_value = (True, None)
        h2e._validate_expression_capabilities = MagicMock(return_value=(True, ""))
        h2e.factor_regulator.evaluate.return_value = (True, {"num_all_nodes": 5, "num_free_args": 0,
                                                               "num_unique_vars": 2, "duplicated_subtree_size": 0,
                                                               "symbol_length": 20, "num_base_features": 1})
        h2e.factor_regulator.is_expression_acceptable.return_value = False
        h2e.factor_regulator.duplication_threshold = 0.5
        h2e.factor_regulator.symbol_length_threshold = 100
        h2e.factor_regulator.base_features_threshold = 10

        mock_trace = MagicMock()
        mock_trace.scen.data_capabilities = None
        mock_trace.scen.get_scenario_all_desc.return_value = "mock"
        mock_trace.scen.background = "mock"
        mock_trace.hist = MagicMock()
        mock_trace.hist.__len__ = MagicMock(return_value=0)
        mock_trace.hist.__bool__ = MagicMock(return_value=False)

        mock_hypothesis = MagicMock()
        mock_hypothesis.__str__ = MagicMock(return_value="test hypothesis")

        with patch.object(AlphaAgentHypothesis2FactorExpression, 'prepare_context',
                          return_value=({"target_hypothesis": "test", "experiment_output_format": "",
                                         "hypothesis_and_feedback": "fb", "function_lib_description": "fl",
                                         "target_list": [], "RAG": None, "financial_pit_context_hint": ""}, True)):
            with patch("quantaalpha.factors.proposal_expression.Environment") as MockEnv:
                mock_template = MagicMock()
                mock_template.render.return_value = "mock prompt"
                MockEnv.return_value.from_string.return_value = mock_template

                with patch("quantaalpha.factors.proposal_expression.APIBackend") as MockAPI:
                    mock_api = MagicMock()
                    mock_api.build_messages.return_value = [{"role": "user", "content": "test"}]
                    MockAPI.return_value = mock_api

                    with patch("quantaalpha.factors.proposal_expression.call_structured") as mock_call:
                        mock_call.return_value = {"factor_A": {"expression": "STD(x)", "description": "test", "formulation": "test"}}

                        with pytest.raises(RuntimeError) as exc_info:
                            h2e._convert_with_history_limit(mock_hypothesis, mock_trace, 6)

                        error_msg = str(exc_info.value)
                        assert "last failure reason" in error_msg.lower()
                        assert "acceptab" in error_msg.lower() or "expression not acceptable" in error_msg.lower()

    def test_exhausted_retry_salvages_valid_prefix(self):
        """If a later factor remains invalid after retries, keep validated factors instead of failing the task."""
        from quantaalpha.factors.proposal import AlphaAgentHypothesis2FactorExpression

        h2e = self._make_h2e()
        h2e._validate_expression_capabilities = MagicMock(return_value=(True, ""))
        h2e.factor_regulator.parse_diagnostic.side_effect = [
            (True, None),
            (False, 'Invalid operator(s): "[]"'),
            (True, None),
            (False, 'Invalid operator(s): "[]"'),
        ]
        h2e.factor_regulator.evaluate.return_value = (
            True,
            {
                "num_all_nodes": 5,
                "num_free_args": 1,
                "num_unique_vars": 2,
                "duplicated_subtree_size": 0,
                "symbol_length": 40,
                "num_base_features": 1,
            },
        )
        h2e.factor_regulator.is_expression_acceptable.return_value = True

        mock_trace = MagicMock()
        mock_trace.scen.data_capabilities = None
        mock_trace.scen.get_scenario_all_desc.return_value = "mock"
        mock_trace.scen.background = "mock"
        mock_trace.hist = MagicMock()
        mock_trace.hist.__len__ = MagicMock(return_value=0)
        mock_trace.hist.__bool__ = MagicMock(return_value=False)

        mock_hypothesis = MagicMock()
        mock_hypothesis.__str__ = MagicMock(return_value="test hypothesis")

        response = {
            "factor_A": {"expression": "RANK($close)", "description": "valid", "formulation": "valid"},
            "factor_B": {"expression": "REGRESI([A,B],C,20)", "description": "invalid", "formulation": "invalid"},
        }

        with patch.object(AlphaAgentHypothesis2FactorExpression, "prepare_context",
                          return_value=({"target_hypothesis": "test", "experiment_output_format": "",
                                         "hypothesis_and_feedback": "fb", "function_lib_description": "fl",
                                         "target_list": [], "RAG": None, "financial_pit_context_hint": ""}, True)):
            with patch("quantaalpha.factors.proposal_expression.Environment") as MockEnv:
                mock_template = MagicMock()
                mock_template.render.return_value = "mock prompt"
                MockEnv.return_value.from_string.return_value = mock_template

                with patch("quantaalpha.factors.proposal_expression.APIBackend") as MockAPI:
                    mock_api = MagicMock()
                    mock_api.build_messages.return_value = [{"role": "user", "content": "test"}]
                    MockAPI.return_value = mock_api

                    with patch("quantaalpha.factors.proposal_expression.call_structured", return_value=response):
                        exp = h2e._convert_with_history_limit(mock_hypothesis, mock_trace, 6)

        assert [task.factor_name for task in exp.tasks] == ["factor_A"]
        h2e.factor_regulator.add_factor.assert_called_once_with(["factor_A"], ["RANK($close)"])


class TestBoundedFeedbackAccumulation:
    """expression_duplication_prompt must not grow without bound."""

    def test_feedback_retains_bounded_window(self):
        """The feedback accumulation helper must keep only a bounded recent window.

        This test will fail with ImportError before the helper is implemented,
        which counts as a genuine product-behavior gap.
        """
        from quantaalpha.factors.proposal import _bound_feedback_accumulation
        # Simulate many rounds of feedback accumulation
        feedback_items = [f"feedback item {i} " * 50 for i in range(30)]

        accumulated = None
        for item in feedback_items:
            accumulated = _bound_feedback_accumulation(accumulated, item)

        # The accumulated feedback must be bounded
        assert accumulated is not None
        # Should not grow to include all 30 items concatenated
        total_possible = sum(len(f) for f in feedback_items)
        assert len(accumulated) < total_possible
        # Should retain recent items, not all old ones
        assert "feedback item 29" in accumulated or "feedback item 28" in accumulated

    def test_feedback_total_length_is_bounded(self):
        """Total character length of accumulated feedback must have a hard cap."""
        from quantaalpha.factors.proposal import _bound_feedback_accumulation
        # Create very long feedback items
        long_items = ["X" * 5000 for _ in range(10)]

        accumulated = None
        for item in long_items:
            accumulated = _bound_feedback_accumulation(accumulated, item)

        # Total length must be bounded by a reasonable cap (e.g., 8000 chars)
        MAX_TOTAL_LENGTH = 8000
        assert len(accumulated) <= MAX_TOTAL_LENGTH, f"Feedback length {len(accumulated)} exceeds cap {MAX_TOTAL_LENGTH}"

    def test_first_feedback_item_is_bounded(self):
        """A single oversized first feedback item must also be capped."""
        from quantaalpha.factors.proposal import _bound_feedback_accumulation

        accumulated = _bound_feedback_accumulation(None, "Y" * 10000)

        assert len(accumulated) <= 8000
