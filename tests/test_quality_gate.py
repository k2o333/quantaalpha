from __future__ import annotations

import unittest
from pathlib import Path
import sys

# Add PKG_ROOT to sys.path
ROOT = Path(__file__).resolve().parents[1]
PKG_ROOT = ROOT / "quantaalpha"
if str(PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import importlib.util
import types

def _load_module(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec and spec.loader
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        print(f"Error loading {name}: {e}")
    return module

# Stub out regulator package to avoid its __init__.py circularity
if "quantaalpha.factors.regulator" not in sys.modules:
    reg_pkg = types.ModuleType("quantaalpha.factors.regulator")
    reg_pkg.__path__ = [str(PKG_ROOT / "factors" / "regulator")]
    sys.modules["quantaalpha.factors.regulator"] = reg_pkg

consistency_checker = _load_module(
    "quantaalpha.factors.regulator.consistency_checker", 
    PKG_ROOT / "factors" / "regulator" / "consistency_checker.py"
)

FactorQualityGate = consistency_checker.FactorQualityGate
ComplexityChecker = consistency_checker.ComplexityChecker
RedundancyChecker = consistency_checker.RedundancyChecker
FactorConsistencyChecker = consistency_checker.FactorConsistencyChecker


class TestQualityGate(unittest.TestCase):
    def setUp(self):
        self.qg = FactorQualityGate(
            consistency_enabled=False, # Disable LLM-based check for unit tests
            complexity_enabled=True,
            redundancy_enabled=False # Disable redundancy for now as it needs a factor zoo
        )

    def test_complexity_gate_bad_samples(self):
        checker = ComplexityChecker(
            symbol_length_threshold=100,
            base_features_threshold=10,
            free_args_ratio_threshold=0.2
        )
        
        # Sample 1: Too long
        expr_too_long = "($close + $open + $high + $low) / 4.0 * TS_MEAN($volume, 20) / TS_STD($close, 20) + ($high - $low) / ($open + 1e-5)"
        # This one is around 110 chars
        passed, feedback = checker.check(expr_too_long)
        self.assertFalse(passed)
        self.assertIn("Symbol Length", feedback)
        
        # Sample 2: Too many base features
        expr_too_many_features = "($close + $open + $high + $low + $volume + $amount + $extra1 + $extra2 + $extra3 + $extra4 + $extra5) / 11.0"
        passed, feedback = checker.check(expr_too_many_features)
        self.assertFalse(passed)
        self.assertIn("Base Features", feedback)
        
        # Sample 3: Over-parameterized (too many constants)
        expr_over_param = "($close * 1.1 + $open * 0.9) / 2.0"
        passed, feedback = checker.check(expr_over_param)
        self.assertFalse(passed)
        self.assertIn("Free Args Ratio", feedback)

        # Sample 4: Trivial/Invalid patterns
        for bad_p in ["1/1", "$close/$close", "0*$volume"]:
            passed, feedback = checker.check(bad_p)
            self.assertFalse(passed)
            self.assertIn("prohibited trivial or invalid pattern", feedback)

    def test_quality_gate_integration(self):
        # Test with a good sample
        good_expr = "($close - $open) / $open"
        passed, feedback, results = self.qg.evaluate(
            hypothesis="Price change relative to open",
            factor_name="rel_change",
            factor_description="Relative price change",
            factor_formulation="($close - $open) / $open",
            factor_expression=good_expr
        )
        self.assertTrue(passed)
        
        # Test with a bad sample (complexity)
        bad_expr = "($close + $open + $high + $low + $volume + $amount + $extra1 + $extra2) / 8.0"
        passed, feedback, results = self.qg.evaluate(
            hypothesis="Too many features",
            factor_name="complex_factor",
            factor_description="Complex description",
            factor_formulation="Sum of many features",
            factor_expression=bad_expr
        )
        self.assertFalse(passed)
        self.assertIn("[Complexity]", feedback)

    def test_data_quality_gate_blocks_bad_samples(self):
        bad_expr = "($close - $open) / $open"
        passed, feedback, results = self.qg.evaluate(
            hypothesis="Bad sample quality",
            factor_name="bad_sample_factor",
            factor_description="Contains invalid sample profile",
            factor_formulation="($close - $open) / $open",
            factor_expression=bad_expr,
            data_profile={
                "nan_ratio": 0.45,
                "has_inf": True,
                "is_constant": True,
                "valid_ratio": 0.4,
            },
        )
        self.assertFalse(passed)
        self.assertIn("[DataQuality]", feedback)
        self.assertFalse(results["data_quality"]["passed"])
        self.assertIn("nan_ratio", results["data_quality"]["details"])
        self.assertIn("valid_ratio", results["data_quality"]["details"])

    def test_failed_quality_gate_skips_high_cost_step(self):
        runner_calls = []

        def fake_backtest():
            runner_calls.append("ran")

        passed, feedback, results = self.qg.evaluate(
            hypothesis="Bad sample quality",
            factor_name="blocked_before_backtest",
            factor_description="Should never reach backtest",
            factor_formulation="($close - $open) / $open",
            factor_expression="($close - $open) / $open",
            data_profile={
                "nan_ratio": 0.4,
                "has_inf": False,
                "is_constant": False,
                "valid_ratio": 0.5,
            },
        )
        if passed:
            fake_backtest()

        self.assertFalse(passed)
        self.assertEqual(runner_calls, [])
        self.assertIn("[DataQuality]", feedback)

    def test_consistency_check_exception_fails_closed(self):
        checker = FactorConsistencyChecker(enabled=True)

        class RaisingAPIBackend:
            def build_messages_and_create_chat_completion_json(self, **kwargs):
                raise RuntimeError("synthetic llm failure")

        original_backend = consistency_checker.APIBackend
        consistency_checker.APIBackend = RaisingAPIBackend
        try:
            result = checker.check_consistency(
                hypothesis="hyp",
                factor_name="factor",
                factor_description="desc",
                factor_formulation="form",
                factor_expression="($close - $open) / $open",
            )
        finally:
            consistency_checker.APIBackend = original_backend

        self.assertFalse(result.is_consistent)
        self.assertEqual(result.severity, "critical")
        self.assertIn("synthetic llm failure", result.overall_feedback)
        self.assertNotIn("Skipping check", result.overall_feedback)

    def test_should_proceed_to_backtest_allows_major_when_configured(self):
        checker = FactorConsistencyChecker(
            enabled=True,
            allowed_inconsistent_severities=("none", "minor", "major"),
        )
        result = consistency_checker.ConsistencyCheckResult(
            is_consistent=False,
            hypothesis_to_description="",
            description_to_formulation="",
            formulation_to_expression="",
            overall_feedback="major but allowed",
            severity="major",
        )

        self.assertTrue(checker.should_proceed_to_backtest(result))

    def test_strict_mode_still_blocks_major_even_when_allowed(self):
        checker = FactorConsistencyChecker(
            enabled=True,
            strict_mode=True,
            allowed_inconsistent_severities=("none", "minor", "major"),
        )
        result = consistency_checker.ConsistencyCheckResult(
            is_consistent=False,
            hypothesis_to_description="",
            description_to_formulation="",
            formulation_to_expression="",
            overall_feedback="major and strict",
            severity="major",
        )

        self.assertFalse(checker.should_proceed_to_backtest(result))

if __name__ == "__main__":
    unittest.main()
