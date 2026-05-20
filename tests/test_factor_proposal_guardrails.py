from __future__ import annotations

import sys
import types
import unittest

if "rdagent.scenarios.qlib.experiment.factor_experiment" not in sys.modules:
    rdagent_pkg = types.ModuleType("rdagent")
    scenarios_pkg = types.ModuleType("rdagent.scenarios")
    qlib_pkg = types.ModuleType("rdagent.scenarios.qlib")
    experiment_pkg = types.ModuleType("rdagent.scenarios.qlib.experiment")
    factor_experiment_pkg = types.ModuleType("rdagent.scenarios.qlib.experiment.factor_experiment")
    workspace_pkg = types.ModuleType("rdagent.scenarios.qlib.experiment.workspace")
    utils_pkg = types.ModuleType("rdagent.utils")
    agent_pkg = types.ModuleType("rdagent.utils.agent")
    tpl_pkg = types.ModuleType("rdagent.utils.agent.tpl")
    log_pkg = types.ModuleType("rdagent.log")

    class _StubFactorExperiment:
        def __init__(self, *args, **kwargs):
            pass

    class _StubFactorTask:
        def __init__(self, *args, **kwargs):
            pass

    class _StubFactorFBWorkspace:
        def __init__(self, *args, **kwargs):
            pass

    class _StubQlibFactorScenario:
        def __init__(self, *args, **kwargs):
            pass

    class _StubQlibFactorExperiment:
        def __init__(self, *args, **kwargs):
            self.sub_tasks = kwargs.get("sub_tasks")
            if self.sub_tasks is None and args:
                self.sub_tasks = args[0]
            if self.sub_tasks is None:
                self.sub_tasks = []
            self.experiment_workspace = None

    class _StubWorkspace:
        def __init__(self, *args, **kwargs):
            self.workspace_path = None

        def inject_code_from_folder(self, *args, **kwargs):
            return None

        def before_execute(self):
            return None

    class _StubLogger:
        def info(self, *args, **kwargs):
            return None

    class _StubTemplate:
        def __call__(self, *args, **kwargs):
            return self

        def r(self, *args, **kwargs):
            return ""

    factor_experiment_pkg.QlibFactorScenario = _StubQlibFactorScenario
    factor_experiment_pkg.FactorExperiment = _StubFactorExperiment
    factor_experiment_pkg.FactorTask = _StubFactorTask
    factor_experiment_pkg.FactorFBWorkspace = _StubFactorFBWorkspace
    factor_experiment_pkg.QlibFactorExperiment = _StubQlibFactorExperiment
    factor_experiment_pkg.__file__ = __file__
    workspace_pkg.QlibFBWorkspace = _StubWorkspace
    tpl_pkg.T = _StubTemplate()
    log_pkg.rdagent_logger = _StubLogger()

    sys.modules["rdagent"] = rdagent_pkg
    sys.modules["rdagent.scenarios"] = scenarios_pkg
    sys.modules["rdagent.scenarios.qlib"] = qlib_pkg
    sys.modules["rdagent.scenarios.qlib.experiment"] = experiment_pkg
    sys.modules["rdagent.scenarios.qlib.experiment.factor_experiment"] = factor_experiment_pkg
    sys.modules["rdagent.scenarios.qlib.experiment.workspace"] = workspace_pkg
    sys.modules["rdagent.utils"] = utils_pkg
    sys.modules["rdagent.utils.agent"] = agent_pkg
    sys.modules["rdagent.utils.agent.tpl"] = tpl_pkg
    sys.modules["rdagent.log"] = log_pkg

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

    def build_messages(self, user_prompt, system_prompt):
        return {"user_prompt": user_prompt, "system_prompt": system_prompt}

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
        if "WEIGHTED_SUM" in expression:
            return False
        return isinstance(expression, str)

    def parse_diagnostic(self, expression):
        return self.is_parsable(expression), None

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

        globals_dict = factor_proposal.AlphaAgentHypothesisGen.gen.__globals__
        original_backend = globals_dict["APIBackend"]
        original_call_structured = globals_dict["call_structured"]
        globals_dict["APIBackend"] = _RecordingAPIBackend

        def fake_call_structured(api, messages, **kwargs):
            return globals_dict["robust_json_parse"](
                api.build_messages_and_create_chat_completion(
                    messages["user_prompt"],
                    messages["system_prompt"],
                    json_mode=kwargs.get("json_mode", False),
                    task_type=kwargs.get("task_type"),
                )
            )

        globals_dict["call_structured"] = fake_call_structured
        try:
            gen.gen(trace)
        finally:
            globals_dict["APIBackend"] = original_backend
            globals_dict["call_structured"] = original_call_structured

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

            def build_messages(self, user_prompt, system_prompt):
                return {"user_prompt": user_prompt, "system_prompt": system_prompt}

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

        globals_dict = factor_proposal.AlphaAgentHypothesis2FactorExpression._convert_with_history_limit.__globals__
        original_backend = globals_dict["APIBackend"]
        original_call_structured = globals_dict["call_structured"]
        globals_dict["APIBackend"] = ProposalAPIBackend

        def fake_call_structured(api, messages, **kwargs):
            return globals_dict["robust_json_parse"](
                api.build_messages_and_create_chat_completion(
                    messages["user_prompt"],
                    messages["system_prompt"],
                    json_mode=kwargs.get("json_mode", False),
                    task_type=kwargs.get("task_type"),
                )
            )

        globals_dict["call_structured"] = fake_call_structured
        try:
            converter.convert(hypothesis, trace)
        finally:
            globals_dict["APIBackend"] = original_backend
            globals_dict["call_structured"] = original_call_structured

        self.assertGreaterEqual(len(fake_regulator.is_parsable_calls), 2)
        self.assertTrue(all(isinstance(expr, str) for expr in fake_regulator.is_parsable_calls))

    def test_invalid_corrected_expression_falls_back_to_original_expression(self):
        converter = factor_proposal.AlphaAgentHypothesis2FactorExpression(consistency_enabled=True)
        fake_regulator = _FakeRegulator()
        converter.factor_regulator = fake_regulator

        class FallbackQualityGate:
            def evaluate(self, **kwargs):
                return True, "ok", {
                    "corrected_expression": "WEIGHTED_SUM(TS_STD($return, 21), TS_STD($return, 42))",
                    "corrected_description": kwargs["factor_description"],
                }

        converter._quality_gate = FallbackQualityGate()

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

            def build_messages(self, user_prompt, system_prompt):
                return {"user_prompt": user_prompt, "system_prompt": system_prompt}

            def build_messages_and_create_chat_completion(self, user_prompt, system_prompt, json_mode=False, task_type=None):
                return """
                {
                    "Fallback_Factor": {
                        "description": "desc",
                        "formulation": "f",
                        "expression": "TS_STD($return, 21)",
                        "variables": {"$return": "daily return"}
                    }
                }
                """

        globals_dict = factor_proposal.AlphaAgentHypothesis2FactorExpression._convert_with_history_limit.__globals__
        original_backend = globals_dict["APIBackend"]
        original_call_structured = globals_dict["call_structured"]
        globals_dict["APIBackend"] = ProposalAPIBackend

        def fake_call_structured(api, messages, **kwargs):
            return globals_dict["robust_json_parse"](
                api.build_messages_and_create_chat_completion(
                    messages["user_prompt"],
                    messages["system_prompt"],
                    json_mode=kwargs.get("json_mode", False),
                    task_type=kwargs.get("task_type"),
                )
            )

        globals_dict["call_structured"] = fake_call_structured
        try:
            experiment = converter.convert(hypothesis, trace)
        finally:
            globals_dict["APIBackend"] = original_backend
            globals_dict["call_structured"] = original_call_structured

        self.assertEqual(len(experiment.sub_tasks), 1)
        self.assertEqual(experiment.sub_tasks[0].factor_expression, "TS_STD($return, 21)")

    def test_quality_gate_constructor_respects_runtime_config(self):
        converter = factor_proposal.AlphaAgentHypothesis2FactorExpression(
            consistency_enabled=True,
            consistency_strict_mode=True,
            max_correction_attempts=7,
            complexity_enabled=False,
            redundancy_enabled=False,
            allowed_inconsistent_severities=("none", "minor", "major"),
        )

        quality_gate = converter.quality_gate

        self.assertTrue(quality_gate.consistency_checker.strict_mode)
        self.assertEqual(quality_gate.consistency_checker.max_correction_attempts, 7)
        self.assertEqual(
            quality_gate.consistency_checker.allowed_inconsistent_severities,
            ("none", "minor", "major"),
        )
        self.assertFalse(quality_gate.complexity_checker.enabled)
        self.assertFalse(quality_gate.redundancy_checker.enabled)

    def test_convert_retries_when_expression_uses_unknown_fields(self):
        converter = factor_proposal.AlphaAgentHypothesis2FactorExpression(consistency_enabled=False)
        converter.factor_regulator = _FakeRegulator()

        trace = Trace(scen=_FakeScenario())
        hypothesis = Hypothesis(
            hypothesis="Use only supported daily variables.",
            reason="",
            concise_reason="",
            concise_observation="",
            concise_justification="",
            concise_knowledge="",
        )

        class ProposalAPIBackend:
            calls = 0

            def __init__(self, *args, **kwargs):
                pass

            def build_messages(self, user_prompt, system_prompt):
                return {"user_prompt": user_prompt, "system_prompt": system_prompt}

            def build_messages_and_create_chat_completion(
                self, user_prompt, system_prompt, json_mode=False, task_type=None
            ):
                type(self).calls += 1
                if type(self).calls == 1:
                    return """
                    {
                        "Unknown_Field_Factor": {
                            "description": "desc",
                            "formulation": "f",
                            "expression": "TS_MEAN($pb, 5)",
                            "variables": {"$pb": "price to book"}
                        }
                    }
                    """
                return """
                {
                    "Supported_Factor": {
                        "description": "desc",
                        "formulation": "f",
                        "expression": "TS_MEAN($close, 5)",
                        "variables": {"$close": "close"}
                    }
                }
                """

        globals_dict = factor_proposal.AlphaAgentHypothesis2FactorExpression._convert_with_history_limit.__globals__
        original_backend = globals_dict["APIBackend"]
        original_call_structured = globals_dict["call_structured"]
        globals_dict["APIBackend"] = ProposalAPIBackend

        def fake_call_structured(api, messages, **kwargs):
            return globals_dict["robust_json_parse"](
                api.build_messages_and_create_chat_completion(
                    messages["user_prompt"],
                    messages["system_prompt"],
                    json_mode=kwargs.get("json_mode", False),
                    task_type=kwargs.get("task_type"),
                )
            )

        globals_dict["call_structured"] = fake_call_structured
        try:
            experiment = converter.convert(hypothesis, trace)
        finally:
            globals_dict["APIBackend"] = original_backend
            globals_dict["call_structured"] = original_call_structured

        self.assertEqual(ProposalAPIBackend.calls, 2)
        self.assertEqual(len(experiment.sub_tasks), 1)
        self.assertEqual(experiment.sub_tasks[0].factor_name, "Supported_Factor")

    def test_expression_capability_validation_rejects_bare_factor_names(self):
        converter = factor_proposal.AlphaAgentHypothesis2FactorExpression(consistency_enabled=False)
        trace = Trace(scen=_FakeScenario())

        valid, feedback = converter._validate_expression_capabilities(
            "ZSCORE(Parent_Momentum_5D) * ZSCORE(Parent_Liquidity_20D)",
            trace,
        )

        self.assertFalse(valid)
        self.assertIn("Unsupported bare identifiers", feedback)
        self.assertIn("Parent_Momentum_5D", feedback)

        valid, feedback = converter._validate_expression_capabilities(
            "ZSCORE(TS_DELTA($close, 5)) * ZSCORE(TS_MEAN($volume, 20))",
            trace,
        )

        self.assertTrue(valid, feedback)


if __name__ == "__main__":
    unittest.main()
