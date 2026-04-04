from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PKG_ROOT = ROOT / "quantaalpha"
FACTORS_ROOT = PKG_ROOT / "factors"

if str(PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_module(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


if "quantaalpha.factors.regulator" not in sys.modules:
    reg_pkg = types.ModuleType("quantaalpha.factors.regulator")
    reg_pkg.__path__ = [str(FACTORS_ROOT / "regulator")]
    sys.modules["quantaalpha.factors.regulator"] = reg_pkg


consistency_checker = _load_module(
    "quantaalpha.factors.regulator.consistency_checker",
    FACTORS_ROOT / "regulator" / "consistency_checker.py",
)

FactorConsistencyChecker = consistency_checker.FactorConsistencyChecker


class _HistoryAwareAPIBackend:
    prompts: list[dict[str, str]] = []
    responses: list[dict] = []

    def __init__(self, *args, **kwargs):
        pass

    def build_messages_and_create_chat_completion_json(self, user_prompt, system_prompt):
        type(self).prompts.append({"user": user_prompt, "system": system_prompt})
        if not type(self).responses:
            raise AssertionError("No fake responses queued for test")
        return type(self).responses.pop(0)


class TestConsistencyCheckerHistory(unittest.TestCase):
    def setUp(self):
        _HistoryAwareAPIBackend.prompts = []
        original_backend = consistency_checker.APIBackend
        self.addCleanup(setattr, consistency_checker, "APIBackend", original_backend)
        consistency_checker.APIBackend = _HistoryAwareAPIBackend

    def test_later_attempt_prompt_includes_prior_feedback_and_rejected_expression(self):
        _HistoryAwareAPIBackend.responses = [
            {
                "is_consistent": False,
                "severity": "major",
                "overall_feedback": "First attempt missed the illiquidity interaction",
                "corrected_expression": "TS_MEAN($close, 10)",
            },
            {
                "is_consistent": True,
                "severity": "none",
                "overall_feedback": "ok",
            },
        ]

        checker = FactorConsistencyChecker(enabled=True, max_correction_attempts=2)
        checker.check_and_correct(
            hypothesis="Include illiquidity interaction",
            factor_name="factor_a",
            factor_description="desc",
            factor_formulation="form",
            factor_expression="TS_MEAN($close, 5)",
        )

        self.assertEqual(len(_HistoryAwareAPIBackend.prompts), 2)
        second_prompt = _HistoryAwareAPIBackend.prompts[1]["user"]
        self.assertIn("First attempt missed the illiquidity interaction", second_prompt)
        self.assertIn("TS_MEAN($close, 10)", second_prompt)

    def test_final_attempt_prompt_switches_to_last_resort_downgrade_mode(self):
        _HistoryAwareAPIBackend.responses = [
            {
                "is_consistent": False,
                "severity": "major",
                "overall_feedback": "too complex",
                "corrected_expression": "TS_MEAN($close, 10)",
            },
            {
                "is_consistent": False,
                "severity": "major",
                "overall_feedback": "still too complex",
                "corrected_expression": "TS_MEAN($close, 20)",
            },
            {
                "is_consistent": True,
                "severity": "none",
                "overall_feedback": "ok",
            },
        ]

        checker = FactorConsistencyChecker(enabled=True, max_correction_attempts=3)
        checker.check_and_correct(
            hypothesis="Use a supported simplified factor if needed",
            factor_name="factor_b",
            factor_description="desc",
            factor_formulation="form",
            factor_expression="TS_MEAN($close, 5)",
        )

        self.assertEqual(len(_HistoryAwareAPIBackend.prompts), 3)
        final_prompt = _HistoryAwareAPIBackend.prompts[2]["user"].lower()
        self.assertIn("last resort", final_prompt)
        self.assertIn("simpl", final_prompt)

    def test_final_attempt_prompt_requests_supported_single_window_downgrade_after_invalid_corrections(self):
        _HistoryAwareAPIBackend.responses = [
            {
                "is_consistent": False,
                "severity": "major",
                "overall_feedback": "proposed a branching regime expression",
                "corrected_expression": "TS_MEAN($close, 10)?TS_MEAN($volume, 5):TS_MEAN($volume, 20)",
            },
            {
                "is_consistent": False,
                "severity": "major",
                "overall_feedback": "still too expressive for the DSL",
                "corrected_expression": "TS_MEAN($close, 15)",
            },
            {
                "is_consistent": True,
                "severity": "none",
                "overall_feedback": "ok",
            },
        ]

        checker = FactorConsistencyChecker(enabled=True, max_correction_attempts=3)
        checker.check_and_correct(
            hypothesis="Use a simple supported proxy instead of regime branches",
            factor_name="factor_d",
            factor_description="desc",
            factor_formulation="form",
            factor_expression="TS_MEAN($close, 5)",
        )

        final_prompt = _HistoryAwareAPIBackend.prompts[2]["user"].lower()
        self.assertIn("single-window", final_prompt)
        self.assertIn("single-branch", final_prompt)
        self.assertIn("supported proxy", final_prompt)

    def test_final_attempt_prompt_explicitly_calls_for_lower_complexity_when_prior_attempts_grew(self):
        _HistoryAwareAPIBackend.responses = [
            {
                "is_consistent": False,
                "severity": "major",
                "overall_feedback": "first correction increased expression complexity",
                "corrected_expression": "TS_CORR(TS_MEAN($close, 5), TS_STD($volume, 10), 20)",
            },
            {
                "is_consistent": False,
                "severity": "major",
                "overall_feedback": "second correction is even more complex",
                "corrected_expression": "TS_CORR(TS_MEAN($close, 5), TS_STD($volume, 10), 20) + TS_RANK($return, 15)",
            },
            {
                "is_consistent": True,
                "severity": "none",
                "overall_feedback": "ok",
            },
        ]

        checker = FactorConsistencyChecker(enabled=True, max_correction_attempts=3)
        checker.check_and_correct(
            hypothesis="Prefer the simplest supported proxy for the hypothesis",
            factor_name="factor_e",
            factor_description="desc",
            factor_formulation="form",
            factor_expression="TS_MEAN($close, 5)",
        )

        final_prompt = _HistoryAwareAPIBackend.prompts[2]["user"].lower()
        self.assertIn("reduce complexity", final_prompt)
        self.assertIn("avoid adding branches", final_prompt)
        self.assertIn("simpler than the rejected candidates", final_prompt)


class TestSupportedFunctionGuardrails(unittest.TestCase):
    def test_checker_does_not_accept_unsupported_corrected_expression(self):
        original_backend = consistency_checker.APIBackend
        self.addCleanup(setattr, consistency_checker, "APIBackend", original_backend)

        class UnsupportedFunctionAPIBackend:
            responses = [
                {
                    "is_consistent": False,
                    "severity": "major",
                    "overall_feedback": "unsupported weighted operator",
                    "corrected_expression": "WEIGHTED_SUM(TS_MEAN($close, 10), TS_MEAN($close, 20))",
                }
            ]

            def __init__(self, *args, **kwargs):
                pass

            def build_messages_and_create_chat_completion_json(self, user_prompt, system_prompt):
                return type(self).responses.pop(0)

        consistency_checker.APIBackend = UnsupportedFunctionAPIBackend

        checker = FactorConsistencyChecker(enabled=True, max_correction_attempts=1)
        result, final_expr, final_desc = checker.check_and_correct(
            hypothesis="Use supported functions only",
            factor_name="factor_c",
            factor_description="desc",
            factor_formulation="form",
            factor_expression="TS_MEAN($close, 5)",
        )

        self.assertEqual(final_expr, "TS_MEAN($close, 5)")
        self.assertIn("unsupported", result.overall_feedback.lower())

    def test_metadata_only_inconsistency_is_reported_without_retry_loop(self):
        original_backend = consistency_checker.APIBackend
        self.addCleanup(setattr, consistency_checker, "APIBackend", original_backend)

        class MetadataOnlyAPIBackend:
            prompts: list[dict[str, str]] = []
            responses = [
                {
                    "is_consistent": False,
                    "severity": "major",
                    "overall_feedback": "Description/formulation mismatch but expression is already correct",
                    "corrected_expression": None,
                    "corrected_description": "metadata-only correction",
                }
            ]

            def __init__(self, *args, **kwargs):
                pass

            def build_messages_and_create_chat_completion_json(self, user_prompt, system_prompt):
                type(self).prompts.append({"user": user_prompt, "system": system_prompt})
                return type(self).responses.pop(0)

        consistency_checker.APIBackend = MetadataOnlyAPIBackend

        checker = FactorConsistencyChecker(enabled=True, max_correction_attempts=3)
        result, final_expr, final_desc = checker.check_and_correct(
            hypothesis="Keep the expression and only report metadata drift",
            factor_name="factor_meta",
            factor_description="desc",
            factor_formulation="form",
            factor_expression="TS_MEAN($close, 5)",
        )

        self.assertEqual(len(MetadataOnlyAPIBackend.prompts), 1)
        self.assertEqual(final_expr, "TS_MEAN($close, 5)")
        self.assertEqual(final_desc, "desc")
        self.assertEqual(result.severity, "minor")
        self.assertTrue(checker.should_proceed_to_backtest(result))
        self.assertIn("metadata", result.overall_feedback.lower())


if __name__ == "__main__":
    unittest.main()
