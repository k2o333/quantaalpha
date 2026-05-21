"""Remediation tests for factor construct retry behavior.

Tests cover:
- Empty response handling with feedback injection and history-limit fallback
- Acceptability retry early stopping for non-improving symbol_length
- Multi-hypothesis construction safety (empty factors_dict detection)
- DSL function signature validation for MEAN(A, B, C)
- Bounded feedback accumulation (MAX_FEEDBACK_ITEMS = 3)
"""
import pytest
from unittest.mock import MagicMock, patch, call


class TestConstructResponseUnwrapShapes:
    """Construct response unwrapping should accept common structured-output shapes."""

    def _make_h2e(self):
        from quantaalpha.factors.proposal import AlphaAgentHypothesis2FactorExpression

        return object.__new__(AlphaAgentHypothesis2FactorExpression)

    def test_single_factor_object_is_unwrapped_as_one_factor(self):
        h2e = self._make_h2e()
        response = {
            "factor_name": "Volume_Momentum_5D",
            "description": "test",
            "formulation": "test",
            "expression": "RANK(TS_MEAN($volume, 5))",
            "variables": {"$volume": "volume"},
        }

        assert h2e._unwrap_construct_response(response) == {"Volume_Momentum_5D": response}

    def test_single_factor_object_without_expression_is_reported_precisely(self):
        h2e = self._make_h2e()
        response = {
            "factor_name": "MissingExpression",
            "description": "test",
            "formulation": "test",
            "variables": {"$volume": "volume"},
        }

        assert h2e._find_missing_expression_candidate(response) == (
            "MissingExpression",
            "factor payload has no expression",
        )

    def test_factor_expression_alias_is_normalized_to_expression(self):
        h2e = self._make_h2e()
        response = {
            "factor_list": [
                {
                    "factor_name": "AliasExpression",
                    "description": "test",
                    "formulation": "test",
                    "factor_expression": "RANK(TS_MEAN($volume, 10))",
                    "variables": {"$volume": "volume"},
                }
            ]
        }

        factors = h2e._unwrap_construct_response(response)

        assert factors["AliasExpression"]["expression"] == "RANK(TS_MEAN($volume, 10))"

    def test_build_experiment_deduplicates_sub_tasks_by_expression(self):
        from quantaalpha.factors.coder.factor import FactorTask
        from quantaalpha.factors.experiment import QlibFactorExperiment

        h2e = self._make_h2e()
        trace = MagicMock()
        trace.hist = [
            (
                None,
                QlibFactorExperiment(
                    sub_tasks=[
                        FactorTask(
                            factor_name="Existing",
                            factor_description="",
                            factor_formulation="",
                            factor_expression="RANK(TS_MEAN($volume, 5))",
                            variables={},
                        )
                    ]
                ),
                object(),
            )
        ]
        response = {
            "factors": {
                "NewCopy": {
                    "description": "copy",
                    "formulation": "copy",
                    "expression": "RANK(TS_MEAN($volume, 5))",
                    "variables": {"$volume": "volume"},
                },
                "NewUnique": {
                    "description": "unique",
                    "formulation": "unique",
                    "expression": "RANK(TS_STD($volume, 10))",
                    "variables": {"$volume": "volume"},
                },
            }
        }

        experiment = h2e._build_experiment_from_dict(response, trace)

        assert [task.factor_name for task in experiment.sub_tasks] == ["NewUnique"]
        assert [task.factor_name for task in experiment.tasks] == ["NewUnique"]
        assert len(experiment.sub_workspace_list) == 1

    def test_build_experiment_deduplicates_inverse_multiply_expression_alias(self):
        h2e = self._make_h2e()
        trace = MagicMock()
        trace.hist = []
        response = {
            "factors": {
                "MultiplyInverse": {
                    "description": "same math",
                    "formulation": "same math",
                    "expression": "ZSCORE(TS_DELTA($close, 5)) * INV(TS_STD($volume, 20) + 1e-8)",
                    "variables": {"$close": "close", "$volume": "volume"},
                },
                "Division": {
                    "description": "same math",
                    "formulation": "same math",
                    "expression": "ZSCORE(TS_DELTA($close, 5)) / (TS_STD($volume, 20) + 1e-8)",
                    "variables": {"$close": "close", "$volume": "volume"},
                },
            }
        }

        experiment = h2e._build_experiment_from_dict(response, trace)

        assert [task.factor_name for task in experiment.sub_tasks] == ["MultiplyInverse"]
        assert len(experiment.sub_workspace_list) == 1


class TestEmptyResponseRecognition:
    """is_input_length_error must recognize persistent empty-response failures."""

    def test_empty_response_is_recognized_as_length_error(self):
        """'persistent empty or invalid LLM response' must be treated as a context-length fallback candidate."""
        from quantaalpha.factors.proposal import is_input_length_error

        # Must recognize empty response indicators
        assert is_input_length_error("persistent empty or invalid LLM response") is True
        assert is_input_length_error("empty response") is True
        assert is_input_length_error("EmptyLLMResponseError: got empty content") is True

    def test_context_length_errors_still_recognized(self):
        """Original context length indicators must still work."""
        from quantaalpha.factors.proposal import is_input_length_error

        assert is_input_length_error("input length exceeded") is True
        assert is_input_length_error("context length limit reached") is True
        assert is_input_length_error("maximum context exceeded") is True


class TestEmptyResponseFeedbackInjection:
    """Empty response must inject feedback and re-render prompt, not repeat unchanged."""

    def _make_h2e(self):
        """Create a minimal AlphaAgentHypothesis2FactorExpression for testing."""
        from quantaalpha.factors.proposal import AlphaAgentHypothesis2FactorExpression

        h2e = object.__new__(AlphaAgentHypothesis2FactorExpression)
        h2e.factor_regulator = MagicMock()
        h2e.factor_regulator.parse_diagnostic.return_value = (True, None)
        h2e.data_capabilities = None
        h2e.targets = []
        h2e.consistency_enabled = False
        h2e._quality_gate = None
        h2e.max_multi_construct_retries = 2
        h2e.max_multi_construct_retries = 2
        return h2e

    def test_empty_response_injects_feedback_and_changes_prompt(self):
        """When response_dict is empty, the retry loop must inject a short feedback item."""
        from quantaalpha.factors.proposal import AlphaAgentHypothesis2FactorExpression

        h2e = self._make_h2e()

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
                        # Return empty response every time
                        mock_call.return_value = {}

                        with pytest.raises(RuntimeError) as exc_info:
                            h2e._convert_with_history_limit(mock_hypothesis, mock_trace, 6)

                        error_msg = str(exc_info.value)
                        # Must contain empty response reason
                        assert "empty response" in error_msg.lower() or "empty" in error_msg.lower()

        # At least some retry prompts after the first must contain empty response feedback
        retry_prompts = seen_user_prompts[1:]
        assert len(retry_prompts) > 0, "Expected at least one retry prompt after empty response"
        combined_retry = "\n".join(retry_prompts)
        # Must contain some feedback about empty response
        assert "empty" in combined_retry.lower() or "previous call" in combined_retry.lower() or "response" in combined_retry.lower()


class TestAcceptabilityEarlyStopping:
    """Repeated acceptability failures from non-improving symbol_length must stop early."""

    def _make_h2e_with_regulator(self):
        """Create H2E with a real FactorRegulator for symbol_length tracking."""
        from quantaalpha.factors.proposal import AlphaAgentHypothesis2FactorExpression
        from quantaalpha.factors.regulator.factor_regulator import FactorRegulator

        h2e = object.__new__(AlphaAgentHypothesis2FactorExpression)
        h2e.factor_regulator = FactorRegulator()
        h2e.data_capabilities = None
        h2e.targets = []
        h2e.consistency_enabled = False
        h2e._quality_gate = None
        return h2e

    def test_acceptability_early_stop_on_non_improving_symbol_length(self):
        """When symbol_length does not improve for 3 consecutive attempts, must stop before 10 retries."""
        from quantaalpha.factors.proposal import AlphaAgentHypothesis2FactorExpression

        h2e = self._make_h2e_with_regulator()

        mock_trace = MagicMock()
        mock_trace.scen.data_capabilities = None
        mock_trace.scen.get_scenario_all_desc.return_value = "mock"
        mock_trace.scen.background = "mock"
        mock_trace.hist = MagicMock()
        mock_trace.hist.__len__ = MagicMock(return_value=0)
        mock_trace.hist.__bool__ = MagicMock(return_value=False)

        mock_hypothesis = MagicMock()
        mock_hypothesis.__str__ = MagicMock(return_value="test hypothesis")

        call_count = 0

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
                        mock_call.return_value = {
                            "factor_A": {
                                "expression": "MEAN($volume)",
                                "description": "test",
                                "formulation": "test"
                            }
                        }

                        with pytest.raises(RuntimeError) as exc_info:
                            h2e._convert_with_history_limit(mock_hypothesis, mock_trace, 6)

                        error_msg = str(exc_info.value)
                        # Must mention early stopping or symbol length
                        assert "symbol_length" in error_msg or "early stop" in error_msg.lower() or "not improving" in error_msg.lower() or "non-improving" in error_msg.lower() or "length" in error_msg.lower()
                        # Must contain the factor name
                        assert "factor_A" in error_msg or "factor_a" in error_msg.lower()

    def test_early_stop_allows_improving_sequence(self):
        """[500, 400, 300] should NOT trigger early stopping — expression is getting shorter."""
        from quantaalpha.factors.proposal import AlphaAgentHypothesis2FactorExpression
        from quantaalpha.factors.regulator.factor_regulator import FactorRegulator

        h2e = object.__new__(AlphaAgentHypothesis2FactorExpression)
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

        # Simulate improving symbol lengths across all 10 attempts
        improving_lengths = [500, 400, 300, 250, 200, 180, 160, 140, 120, 100]
        length_idx = [0]

        def mock_evaluate(expr):
            sl = improving_lengths[min(length_idx[0], len(improving_lengths) - 1)]
            length_idx[0] += 1
            return True, {
                "num_all_nodes": 5, "num_free_args": 0,
                "num_unique_vars": 2, "duplicated_subtree_size": 0,
                "symbol_length": sl, "num_base_features": 1
            }

        # Mock is_expression_acceptable to always return False (so we test early stopping logic)
        h2e.factor_regulator.is_expression_acceptable = MagicMock(return_value=False)
        h2e.factor_regulator.evaluate = MagicMock(side_effect=mock_evaluate)

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
                        mock_call.return_value = {
                            "factor_A": {
                                "expression": "MEAN($volume)",
                                "description": "test",
                                "formulation": "test"
                            }
                        }

                        # Should NOT raise early-stop RuntimeError for improving sequence
                        # It will exhaust all 10 retries and raise the full retry exhaustion error
                        with pytest.raises(RuntimeError) as exc_info:
                            h2e._convert_with_history_limit(mock_hypothesis, mock_trace, 6)

                        error_msg = str(exc_info.value)
                        # Must NOT mention early stopping for improving sequence
                        assert "early-stop" not in error_msg


class TestMultiHypothesisEmptyFactorsDict:
    """convert_multi_hypothesis must not silently return zero-task experiment from empty factors_dict."""

    def _make_h2e(self):
        from quantaalpha.factors.proposal import AlphaAgentHypothesis2FactorExpression

        h2e = object.__new__(AlphaAgentHypothesis2FactorExpression)
        h2e.factor_regulator = MagicMock()
        h2e.factor_regulator.parse_diagnostic.return_value = (True, None)
        h2e.factor_regulator.evaluate.return_value = (True, {"symbol_length": 32})
        h2e.factor_regulator.is_expression_acceptable.return_value = True
        h2e.data_capabilities = None
        h2e.targets = []
        h2e.consistency_enabled = False
        h2e._quality_gate = None
        h2e.max_multi_construct_retries = 2
        h2e.fallback_on_multi_construct_failure = True
        return h2e

    def _make_bundle(self):
        from quantaalpha.factors.proposal import EnsembleHypothesisBundle

        return EnsembleHypothesisBundle(
            hypothesis="ensemble test",
            concise_observation="obs",
            concise_knowledge="know",
            concise_justification="just",
            concise_specification="spec",
            hypotheses=[
                {"model": "m1", "hypothesis": {"hypothesis": "h1"}},
                {"model": "m2", "hypothesis": {"hypothesis": "h2"}},
            ],
            ensemble_strategy="collect_all",
            num_models=2,
        )

    def _make_trace(self):
        mock_trace = MagicMock()
        mock_trace.scen.data_capabilities = None
        mock_trace.scen.get_scenario_all_desc.return_value = "mock"
        mock_trace.scen.background = "mock"
        mock_trace.hist = []
        return mock_trace

    def test_empty_multi_hypothesis_response_retries_or_falls_back_with_reason(self):
        """When call_structured returns empty dict, must retry or fallback with logged reason."""
        from quantaalpha.factors.proposal import AlphaAgentHypothesis2FactorExpression, EnsembleHypothesisBundle

        h2e = object.__new__(AlphaAgentHypothesis2FactorExpression)
        h2e.factor_regulator = MagicMock()
        h2e.data_capabilities = None
        h2e.targets = []
        h2e.consistency_enabled = False
        h2e._quality_gate = None
        h2e.max_multi_construct_retries = 2
        h2e.fallback_on_multi_construct_failure = True

        bundle = EnsembleHypothesisBundle(
            hypothesis="ensemble test",
            concise_observation="obs",
            concise_knowledge="know",
            concise_justification="just",
            concise_specification="spec",
            hypotheses=[
                {"model": "m1", "hypothesis": {"hypothesis": "h1"}},
                {"model": "m2", "hypothesis": {"hypothesis": "h2"}},
            ],
            ensemble_strategy="collect_all",
            num_models=2,
        )

        mock_trace = MagicMock()
        mock_trace.scen.data_capabilities = None
        mock_trace.scen.get_scenario_all_desc.return_value = "mock"
        mock_trace.scen.background = "mock"
        mock_trace.hist = MagicMock()
        mock_trace.hist.__len__ = MagicMock(return_value=0)
        mock_trace.hist.__bool__ = MagicMock(return_value=False)

        call_count = 0
        fallback_reason_logged = []

        def mock_call_structured(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # Return empty dict first 2 times, then still empty
            return {}

        with patch("quantaalpha.factors.proposal_expression.call_structured", side_effect=mock_call_structured):
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

                        with patch.object(AlphaAgentHypothesis2FactorExpression, 'convert') as mock_convert:
                            fallback_exp = MagicMock()
                            mock_convert.return_value = fallback_exp
                            with patch("quantaalpha.factors.proposal_expression.logger") as mock_logger:
                                result = h2e.convert_multi_hypothesis(bundle, mock_trace)

                                # Must have logged the fallback reason
                                warning_calls = [str(args[0]) for args, _ in mock_logger.warning.call_args_list if args]
                                combined_warnings = "\n".join(warning_calls)
                                assert "empty" in combined_warnings.lower() or "multi-hypothesis" in combined_warnings.lower()
                                assert "falling back to primary hypothesis" in combined_warnings.lower()
                            assert result is fallback_exp
                            mock_convert.assert_called_once()

    def test_multi_hypothesis_length_error_retries_with_reduced_history(self):
        """Context-length errors must retry the multi-hypothesis path with reduced history before fallback."""
        from quantaalpha.factors.proposal import AlphaAgentHypothesis2FactorExpression, EnsembleHypothesisBundle
        from quantaalpha.factors.regulator.factor_regulator import FactorRegulator

        h2e = object.__new__(AlphaAgentHypothesis2FactorExpression)
        h2e.factor_regulator = FactorRegulator()
        h2e.data_capabilities = None
        h2e.targets = []
        h2e.consistency_enabled = False
        h2e._quality_gate = None
        h2e._validate_expression_capabilities = MagicMock(return_value=(True, ""))
        h2e.max_multi_construct_retries = 2
        h2e.fallback_on_multi_construct_failure = True

        bundle = EnsembleHypothesisBundle(
            hypothesis="ensemble test",
            concise_observation="obs",
            concise_knowledge="know",
            concise_justification="just",
            concise_specification="spec",
            hypotheses=[
                {"model": "m1", "hypothesis": {"hypothesis": "h1"}},
                {"model": "m2", "hypothesis": {"hypothesis": "h2"}},
            ],
            ensemble_strategy="collect_all",
            num_models=2,
        )

        mock_trace = MagicMock()
        mock_trace.scen.data_capabilities = None
        mock_trace.scen.get_scenario_all_desc.return_value = "mock"
        mock_trace.scen.background = "mock"
        mock_trace.hist = MagicMock()
        mock_trace.hist.__len__ = MagicMock(return_value=0)
        mock_trace.hist.__bool__ = MagicMock(return_value=False)

        seen_history_limits = []

        def fake_prepare_context(_bundle, _trace, history_limit):
            seen_history_limits.append(history_limit)
            return ({"target_hypothesis": "test", "experiment_output_format": "",
                     "hypothesis_and_feedback": "fb", "function_lib_description": "fl",
                     "target_list": [], "RAG": None, "financial_pit_context_hint": ""}, True)

        with patch.object(AlphaAgentHypothesis2FactorExpression, 'prepare_context', side_effect=fake_prepare_context):
            with patch("quantaalpha.factors.proposal_expression.Environment") as MockEnv:
                mock_template = MagicMock()
                mock_template.render.return_value = "mock prompt"
                MockEnv.return_value.from_string.return_value = mock_template

                with patch("quantaalpha.factors.proposal_expression.APIBackend") as MockAPI:
                    mock_api = MagicMock()
                    mock_api.build_messages.return_value = [{"role": "user", "content": "test"}]
                    MockAPI.return_value = mock_api

                    with patch("quantaalpha.factors.proposal_expression.call_structured") as mock_call:
                        mock_call.side_effect = [
                            RuntimeError("context length exceeded"),
                            {"factors": {"factor_A": {
                                "expression": "RANK(TS_MEAN($volume,20))",
                                "description": "test",
                                "formulation": "test",
                                "variables": {},
                            }}},
                        ]

                        with patch.object(AlphaAgentHypothesis2FactorExpression, 'convert') as mock_convert:
                            result = h2e.convert_multi_hypothesis(bundle, mock_trace)

                        mock_convert.assert_not_called()
                        assert result.tasks
                        assert seen_history_limits[:2] == [6, 5]

    def test_multi_hypothesis_empty_response_feedback_retries_then_succeeds(self):
        """A retry after empty factors must include targeted construct feedback."""
        from quantaalpha.factors.proposal import AlphaAgentHypothesis2FactorExpression

        h2e = self._make_h2e()
        bundle = self._make_bundle()
        mock_trace = self._make_trace()
        seen_feedback = []

        def fake_render(**kwargs):
            seen_feedback.append(kwargs.get("expression_duplication"))
            return "mock prompt"

        with patch.object(
            AlphaAgentHypothesis2FactorExpression,
            "prepare_context",
            return_value=(
                {
                    "target_hypothesis": "test",
                    "experiment_output_format": "",
                    "hypothesis_and_feedback": "fb",
                    "function_lib_description": "fl",
                    "target_list": [],
                    "RAG": None,
                    "financial_pit_context_hint": "",
                },
                True,
            ),
        ):
            with patch("quantaalpha.factors.proposal_expression.Environment") as MockEnv:
                mock_template = MagicMock()
                mock_template.render.side_effect = fake_render
                MockEnv.return_value.from_string.return_value = mock_template

                with patch("quantaalpha.factors.proposal_expression.APIBackend") as MockAPI:
                    mock_api = MagicMock()
                    mock_api.build_messages.return_value = [{"role": "user", "content": "test"}]
                    MockAPI.return_value = mock_api

                    with patch("quantaalpha.factors.proposal_expression.call_structured") as mock_call:
                        mock_call.side_effect = [
                            {"factors": {}},
                            {
                                "factors": {
                                    "factor_valid": {
                                        "expression": "MEAN($volume)",
                                        "description": "valid",
                                        "formulation": "valid",
                                        "variables": {},
                                    }
                                }
                            },
                        ]

                        result = h2e.convert_multi_hypothesis(bundle, mock_trace)

        MockAPI.assert_called_with()
        assert len(result.tasks) == 1
        assert result.tasks[0].factor_name == "factor_valid"
        combined_feedback = "\n".join(str(item) for item in seen_feedback if item)
        assert "empty factors" in combined_feedback.lower() or "no factor" in combined_feedback.lower()

    def test_multi_hypothesis_mixed_validity_keeps_valid_factor(self):
        """One invalid factor must not discard another valid factor in the same response."""
        h2e = self._make_h2e()
        h2e.fallback_on_multi_construct_failure = False
        h2e.fallback_on_multi_construct_failure = False
        bundle = self._make_bundle()
        mock_trace = self._make_trace()

        def fake_parse(expr):
            if "BAD_EXPR" in expr:
                return False, "parser rejected BAD_EXPR"
            return True, None

        h2e.factor_regulator.parse_diagnostic.side_effect = fake_parse

        with patch.object(
            h2e,
            "prepare_context",
            return_value=(
                {
                    "target_hypothesis": "test",
                    "experiment_output_format": "",
                    "hypothesis_and_feedback": "fb",
                    "function_lib_description": "fl",
                    "target_list": [],
                    "RAG": None,
                    "financial_pit_context_hint": "",
                },
                True,
            ),
        ):
            with patch("quantaalpha.factors.proposal_expression.Environment") as MockEnv:
                mock_template = MagicMock()
                mock_template.render.return_value = "mock prompt"
                MockEnv.return_value.from_string.return_value = mock_template

                with patch("quantaalpha.factors.proposal_expression.APIBackend") as MockAPI:
                    mock_api = MagicMock()
                    mock_api.build_messages.return_value = [{"role": "user", "content": "test"}]
                    MockAPI.return_value = mock_api

                    with patch("quantaalpha.factors.proposal_expression.call_structured") as mock_call:
                        mock_call.return_value = {
                            "factors": {
                                "factor_valid": {
                                    "expression": "MEAN($volume)",
                                    "description": "valid",
                                    "formulation": "valid",
                                    "variables": {},
                                },
                                "factor_bad": {
                                    "expression": "BAD_EXPR(",
                                    "description": "bad",
                                    "formulation": "bad",
                                    "variables": {},
                                },
                            }
                        }

                        result = h2e.convert_multi_hypothesis(bundle, mock_trace)

        assert [task.factor_name for task in result.tasks] == ["factor_valid"]

    def test_percentile_swapped_arguments_are_rejected_before_execution(self):
        """PERCENTILE(x, window, q) must be rejected with structured feedback."""
        h2e = self._make_h2e()
        valid, category, detail, expr = h2e._validate_multi_construct_factor(
            "bad_percentile",
            {
                "expression": "RANK(TS_SUM($return, 5)) * RANK(-PERCENTILE($volume, 20, 0.2))",
                "description": "bad",
                "formulation": "bad",
                "variables": {},
            },
            self._make_trace(),
        )

        assert valid is False
        assert category == "percentile_argument_order"
        assert "PERCENTILE" in detail
        assert "0.2" in detail
        assert "20" in detail
        h2e.factor_regulator.parse_diagnostic.assert_not_called()
        assert expr.startswith("RANK(")

    def test_valid_percentile_argument_order_is_preserved(self):
        """PERCENTILE(x, q, window) remains valid for existing translator contract."""
        h2e = self._make_h2e()
        valid, category, detail, _expr = h2e._validate_multi_construct_factor(
            "good_percentile",
            {
                "expression": "PERCENTILE(TS_SUM($return, 10), 0.5, 20)",
                "description": "good",
                "formulation": "good",
                "variables": {},
            },
            self._make_trace(),
        )

        assert valid is True
        assert category == ""
        assert detail == ""
        h2e.factor_regulator.parse_diagnostic.assert_called_once()

    def test_missing_denominator_multiplier_is_rejected(self):
        """Formulation-expression mismatch must be rejected without global runtime patching."""
        h2e = self._make_h2e()
        valid, category, detail, expr = h2e._validate_multi_construct_factor(
            "Momentum_Consistency_10D",
            {
                "expression": "RANK(COUNT($return > 0, 10) / (TS_STD($return, 20) + 1e-8))",
                "description": "bad",
                "formulation": "COUNT($return > 0, 10) / (10 * TS_STD($return, 20))",
                "variables": {},
            },
            self._make_trace(),
        )

        assert valid is False
        assert category == "missing_denominator_multiplier"
        assert "10 * TS_STD" in detail
        h2e.factor_regulator.parse_diagnostic.assert_not_called()
        assert "COUNT" in expr

    def test_multi_hypothesis_final_error_contains_last_failure_category(self):
        """Final construct failure must classify the last caller-level validation reason."""
        from quantaalpha.factors.proposal import AlphaAgentHypothesis2FactorExpression

        h2e = self._make_h2e()
        h2e.fallback_on_multi_construct_failure = False
        bundle = self._make_bundle()
        mock_trace = self._make_trace()

        with patch.object(
            AlphaAgentHypothesis2FactorExpression,
            "prepare_context",
            return_value=(
                {
                    "target_hypothesis": "test",
                    "experiment_output_format": "",
                    "hypothesis_and_feedback": "fb",
                    "function_lib_description": "fl",
                    "target_list": [],
                    "RAG": None,
                    "financial_pit_context_hint": "",
                },
                True,
            ),
        ):
            with patch("quantaalpha.factors.proposal_expression.Environment") as MockEnv:
                mock_template = MagicMock()
                mock_template.render.return_value = "mock prompt"
                MockEnv.return_value.from_string.return_value = mock_template

                with patch("quantaalpha.factors.proposal_expression.APIBackend") as MockAPI:
                    mock_api = MagicMock()
                    mock_api.build_messages.return_value = [{"role": "user", "content": "test"}]
                    mock_api.chat_model = "construct-model"
                    mock_api.provider_name = "construct-provider"
                    MockAPI.return_value = mock_api

                    with patch("quantaalpha.factors.proposal_expression.call_structured") as mock_call:
                        mock_call.return_value = {
                            "factors": {
                                "factor_missing_expr": {
                                    "description": "missing",
                                    "formulation": "missing",
                                    "variables": {},
                                }
                            }
                        }

                        with pytest.raises(RuntimeError) as exc_info:
                            h2e.convert_multi_hypothesis(bundle, mock_trace)

        error_msg = str(exc_info.value)
        assert "missing_expression" in error_msg
        assert "factor_missing_expr" in error_msg
        assert "construct-model" in error_msg or "construct-provider" in error_msg


class TestMeanSignatureValidation:
    """MEAN(A, B, C) must be rejected before execution; MEAN(A) must pass."""

    def test_mean_signature_single_arg_passes(self):
        """MEAN($volume) is legal."""
        from quantaalpha.factors.regulator.factor_regulator import FactorRegulator

        regulator = FactorRegulator()
        parsable, error = regulator.parse_diagnostic("MEAN($volume)")
        assert parsable is True
        assert error is None

    def test_mean_signature_multi_arg_rejected(self):
        """MEAN(A, B, C) must be rejected with a clear diagnostic."""
        from quantaalpha.factors.regulator.factor_regulator import FactorRegulator

        regulator = FactorRegulator()
        # MEAN(A, B, C) must be rejected by capability validation
        expr = "MEAN(RANK($close), RANK($volume), RANK($open))"
        parsable, parse_error = regulator.parse_diagnostic(expr)
        # Must be rejected
        assert parsable is False
        assert parse_error is not None
        assert "MEAN()" in parse_error
        assert "single-argument" in parse_error

    def test_mean_signature_ts_mean_multi_arg_still_passes(self):
        """TS_MEAN(A, n) is legal with 2 args."""
        from quantaalpha.factors.regulator.factor_regulator import FactorRegulator

        regulator = FactorRegulator()
        parsable, error = regulator.parse_diagnostic("TS_MEAN($close, 20)")
        assert parsable is True
        assert error is None

    def test_mean_signature_deep_nested_multi_arg_rejected(self):
        """MEAN with deeply nested multi-arg must be rejected via AST validation."""
        from quantaalpha.factors.regulator.factor_regulator import FactorRegulator

        regulator = FactorRegulator()
        expr = "MEAN(RANK(ZSCORE(TS_CORR($return,$volume,5))), RANK(ZSCORE(TS_CORR($return,$volume,10))), RANK(ZSCORE(TS_CORR($return,$volume,20))))"
        parsable, parse_error = regulator.parse_diagnostic(expr)
        assert parsable is False
        assert parse_error is not None
        assert "MEAN()" in parse_error
        assert "single-argument" in parse_error


class TestFeedbackAccumulationReduction:
    """MAX_FEEDBACK_ITEMS must be reduced to 3."""

    def test_feedback_accumulation_max_items_is_3(self):
        """The bounded feedback accumulation must keep only the most recent 3 items."""
        from quantaalpha.factors.proposal import _bound_feedback_accumulation, MAX_FEEDBACK_ITEMS

        # MAX_FEEDBACK_ITEMS must be 3
        assert MAX_FEEDBACK_ITEMS == 3, f"MAX_FEEDBACK_ITEMS should be 3, got {MAX_FEEDBACK_ITEMS}"

    def test_feedback_accumulation_retains_only_recent_3_items(self):
        """Accumulating more than 3 items must keep only the most recent 3."""
        from quantaalpha.factors.proposal import _bound_feedback_accumulation, MAX_FEEDBACK_ITEMS

        accumulated = None
        for i in range(10):
            accumulated = _bound_feedback_accumulation(accumulated, f"item_{i}")

        # Must contain recent items
        assert "item_9" in accumulated
        assert "item_8" in accumulated
        assert "item_7" in accumulated
        # Must NOT contain old items
        assert "item_0" not in accumulated
        assert "item_1" not in accumulated
        assert "item_2" not in accumulated
        assert "item_3" not in accumulated
        assert "item_4" not in accumulated
        assert "item_5" not in accumulated
        assert "item_6" not in accumulated


class TestConstructResponseUnwrap:
    """Construct response normalization must accept common structured output variants."""

    def _make_h2e(self):
        from quantaalpha.factors.proposal import AlphaAgentHypothesis2FactorExpression

        return object.__new__(AlphaAgentHypothesis2FactorExpression)

    def test_unwrap_accepts_factors_list_payload(self):
        """{"factors": [...]} payloads must be converted to a factor-name map."""
        h2e = self._make_h2e()

        result = h2e._unwrap_construct_response(
            {
                "factors": [
                    {
                        "factor_name": "factor_list",
                        "expression": "MEAN($volume)",
                        "description": "list payload",
                        "formulation": "list payload",
                    }
                ]
            }
        )

        assert list(result) == ["factor_list"]
        assert result["factor_list"]["expression"] == "MEAN($volume)"

    def test_unwrap_accepts_top_level_list_payload(self):
        """Top-level list payloads must not raise and must be normalized."""
        h2e = self._make_h2e()

        result = h2e._unwrap_construct_response(
            [
                {
                    "name": "factor_top_level",
                    "expression": "RANK($close)",
                    "description": "top-level payload",
                    "formulation": "top-level payload",
                }
            ]
        )

        assert list(result) == ["factor_top_level"]
        assert result["factor_top_level"]["expression"] == "RANK($close)"

    def test_unwrap_rejects_items_without_expression(self):
        """List items without a non-empty expression are metadata, not factors."""
        h2e = self._make_h2e()

        result = h2e._unwrap_construct_response(
            {
                "factors": [
                    {"factor_name": "missing_expression", "description": "not a factor"},
                    {"factor_name": "empty_expression", "expression": "   "},
                ]
            }
        )

        assert result == {}

    def test_unwrap_filters_metadata_from_factor_map(self):
        """Dynamic maps may contain metadata wrappers; only expression payloads are factors."""
        h2e = self._make_h2e()

        result = h2e._unwrap_construct_response(
            {
                "factors": {
                    "metadata": {"note": "not a factor"},
                    "factor_valid": {
                        "expression": "TS_MEAN($close, 20)",
                        "description": "valid",
                        "formulation": "valid",
                    },
                }
            }
        )

        assert list(result) == ["factor_valid"]
