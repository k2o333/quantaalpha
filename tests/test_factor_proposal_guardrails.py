from __future__ import annotations

import unittest

from quantaalpha.core.proposal import Hypothesis, Trace
from quantaalpha.factors import proposal as factor_proposal


class _FakeScenario:
    background = "daily factor mining"

    def get_scenario_all_desc(self, filtered_tag=None):
        return "daily factor mining"


class _RecordingAPIBackend:
    last_system_prompt = None

    def __init__(self, *args, **kwargs):
        pass

    def build_messages_and_create_chat_completion(self, user_prompt, system_prompt, json_mode=False, task_type=None):
        type(self).last_system_prompt = system_prompt
        return """
        {
            "hypothesis": "Use rolling volatility ratios built only from supported daily operators.",
            "concise_observation": "obs",
            "concise_knowledge": "know",
            "concise_justification": "just",
            "concise_specification": "spec"
        }
        """


class _FakeRegulator:
    def __init__(self):
        self.is_parsable_calls = []

    def is_parsable(self, expression):
        self.is_parsable_calls.append(expression)
        return isinstance(expression, str)

    def evaluate(self, expression):
        return True, {
            "num_all_nodes": 4,
            "num_free_args": 0,
            "num_unique_vars": 1,
            "duplicated_subtree_size": 0,
            "duplicated_subtree": "",
            "matched_alpha": "",
            "symbol_length": 20,
            "num_base_features": 1,
        }

    def is_expression_acceptable(self, eval_dict):
        return True

    def add_factor(self, factor_name, factor_expression):
        return None


class _FakeQualityGate:
    def evaluate(self, **kwargs):
        return True, "ok", {
            "corrected_expression": {"expression": "RANK(TS_STD($return, 21))"},
            "corrected_description": kwargs["factor_description"],
        }


class TestFactorProposalGuardrails(unittest.TestCase):
    def test_hypothesis_prompt_includes_function_library_constraints(self):
        trace = Trace(scen=_FakeScenario())
        gen = factor_proposal.AlphaAgentHypothesisGen(_FakeScenario(), potential_direction="挖掘日频时间序列因子")

        original_backend = factor_proposal.APIBackend
        factor_proposal.APIBackend = _RecordingAPIBackend
        try:
            gen.gen(trace)
        finally:
            factor_proposal.APIBackend = original_backend

        system_prompt = _RecordingAPIBackend.last_system_prompt
        self.assertIsNotNone(system_prompt)
        self.assertIn("Only use concepts implementable with the available function library", system_prompt)
        self.assertIn("RANK(A)", system_prompt)

    def test_corrected_expression_dict_is_normalized_before_parser_calls(self):
        converter = factor_proposal.AlphaAgentHypothesis2FactorExpression(consistency_enabled=True)
        fake_regulator = _FakeRegulator()
        converter.factor_regulator = fake_regulator
        converter._quality_gate = _FakeQualityGate()

        trace = Trace(scen=_FakeScenario())
        hypothesis = Hypothesis(
            hypothesis="Use supported rolling volatility ratios only.",
            reason="",
            concise_reason="",
            concise_observation="",
            concise_justification="",
            concise_knowledge="",
        )

        class ProposalAPIBackend:
            def __init__(self, *args, **kwargs):
                pass

            def build_messages_and_create_chat_completion(self, user_prompt, system_prompt, json_mode=False, task_type=None):
                return """
                {
                    "Volatility_Factor": {
                        "description": "desc",
                        "formulation": "f",
                        "expression": "TS_STD($return, 21)",
                        "variables": {"$return": "daily return"}
                    }
                }
                """

        original_backend = factor_proposal.APIBackend
        factor_proposal.APIBackend = ProposalAPIBackend
        try:
            converter.convert(hypothesis, trace)
        finally:
            factor_proposal.APIBackend = original_backend

        self.assertGreaterEqual(len(fake_regulator.is_parsable_calls), 2)
        self.assertTrue(all(isinstance(expr, str) for expr in fake_regulator.is_parsable_calls))


if __name__ == "__main__":
    unittest.main()
