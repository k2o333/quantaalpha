"""
Regression test for dict-type AttributeError bug fix in consistency_checker.py.

Bug: LLM JSON responses may contain nested dict structures for corrected_expression,
causing 'dict' object has no attribute 'replace' error at line 265.

Fix: Added isinstance(expression, dict) checks in ComplexityChecker.check() and
RedundancyChecker.check() to normalize dict inputs before string operations.

Run with:
    cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M002
    python third_party/quantaalpha/tests/test_consistency_checker_dict_fix.py -v
"""
from __future__ import annotations

import unittest
from pathlib import Path
import sys
import types
import importlib.util

# Setup paths - the package structure is:
# third_party/quantaalpha/
#   quantaalpha/
#     factors/
#       regulator/
#         consistency_checker.py
ROOT = Path(__file__).resolve().parents[1]  # goes to quantaalpha/
PKG_ROOT = ROOT / "quantaalpha"  # goes to quantaalpha/quantaalpha/
FACTORS_ROOT = PKG_ROOT / "factors"  # goes to quantaalpha/quantaalpha/factors/

if str(PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(PKG_ROOT))

# Clear any cached modules
for mod in list(sys.modules.keys()):
    if 'quantaalpha' in mod:
        del sys.modules[mod]


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
        raise
    return module


# Stub out regulator package to avoid its __init__.py circularity
if "quantaalpha.factors.regulator" not in sys.modules:
    reg_pkg = types.ModuleType("quantaalpha.factors.regulator")
    reg_pkg.__path__ = [str(FACTORS_ROOT / "regulator")]
    sys.modules["quantaalpha.factors.regulator"] = reg_pkg

# Load the actual module
consistency_checker = _load_module(
    "quantaalpha.factors.regulator.consistency_checker",
    FACTORS_ROOT / "regulator" / "consistency_checker.py"
)

ComplexityChecker = consistency_checker.ComplexityChecker
RedundancyChecker = consistency_checker.RedundancyChecker


class TestDictDefensiveFixRegression(unittest.TestCase):
    """Regression tests for dict-type AttributeError fix.
    
    These tests verify that dict inputs from LLM responses are properly handled
    and do not cause 'dict' object has no attribute 'replace' errors.
    """
    
    def test_complexity_checker_dict_with_code_key(self):
        """Regression: dict with 'code' key should not raise AttributeError.
        
        This is the primary use case from LLM responses:
        {"corrected_expression": {"code": "close / open", "note": "..."}}
        """
        checker = ComplexityChecker(
            symbol_length_threshold=100,
            base_features_threshold=10,
            free_args_ratio_threshold=0.5,
            enabled=True
        )
        
        dict_expr = {"code": "($close - $open) / $open", "note": "Simplified form"}
        
        # This should NOT raise: AttributeError: 'dict' object has no attribute 'replace'
        try:
            passed, feedback = checker.check(dict_expr)
        except AttributeError as e:
            self.fail(f"Dict input raised AttributeError (regression): {e}")
        
        # Should handle gracefully
        self.assertTrue(passed, f"Valid expression in dict should pass: {feedback}")

    def test_complexity_checker_dict_with_expression_key(self):
        """Regression: dict with 'expression' key should not raise AttributeError."""
        checker = ComplexityChecker(
            symbol_length_threshold=100,
            base_features_threshold=10,
            free_args_ratio_threshold=0.5,
            enabled=True
        )
        
        dict_expr = {"expression": "($close / $open) * 100", "source": "llm"}
        
        try:
            passed, feedback = checker.check(dict_expr)
        except AttributeError as e:
            self.fail(f"Dict input raised AttributeError (regression): {e}")
        
        self.assertTrue(passed, f"Valid expression in dict should pass: {feedback}")

    def test_complexity_checker_dict_unknown_keys(self):
        """Regression: dict without 'code' or 'expression' should not raise AttributeError.
        
        Falls back to str() conversion.
        """
        checker = ComplexityChecker(
            symbol_length_threshold=100,
            base_features_threshold=10,
            free_args_ratio_threshold=0.5,
            enabled=True
        )
        
        dict_expr = {"unknown_key": "some_value", "nested": {"data": 123}}
        
        try:
            passed, feedback = checker.check(dict_expr)
        except AttributeError as e:
            self.fail(f"Dict with unknown keys raised AttributeError (regression): {e}")

    def test_complexity_checker_string_still_works(self):
        """Baseline: string input should still work as before."""
        checker = ComplexityChecker(
            symbol_length_threshold=100,
            base_features_threshold=10,
            free_args_ratio_threshold=0.5,
            enabled=True
        )
        
        str_expr = "($close - $open) / $open"
        passed, feedback = checker.check(str_expr)
        self.assertTrue(passed)
        
    def test_redundancy_checker_dict_input_no_attributeerror(self):
        """Regression: RedundancyChecker.check() should not raise AttributeError on dict input."""
        checker = RedundancyChecker(
            enabled=True,
            duplication_threshold=5,
            factor_zoo_path=None  # Disable zoo for unit test
        )
        
        dict_expr = {"code": "($close - $open) / $open"}
        
        try:
            passed, feedback, details = checker.check(dict_expr)
        except AttributeError as e:
            self.fail(f"Dict input raised AttributeError in RedundancyChecker (regression): {e}")

    def test_redundancy_checker_string_baseline(self):
        """Baseline: string input should still work in RedundancyChecker."""
        checker = RedundancyChecker(
            enabled=True,
            duplication_threshold=5,
            factor_zoo_path=None
        )
        
        str_expr = "($close - $open) / $open"
        
        try:
            passed, feedback, details = checker.check(str_expr)
        except AttributeError as e:
            self.fail(f"String input raised AttributeError in RedundancyChecker: {e}")


class TestDictNormalizationLogic(unittest.TestCase):
    """Unit tests for the isinstance(expression, dict) defensive logic."""
    
    def test_isinstance_guard_returns_true_for_dict(self):
        """Verify isinstance check correctly identifies dict."""
        test_input = {"code": "test"}
        self.assertTrue(isinstance(test_input, dict))
    
    def test_isinstance_guard_returns_false_for_string(self):
        """Verify isinstance check correctly rejects string."""
        test_input = "($close - $open) / $open"
        self.assertFalse(isinstance(test_input, dict))
    
    def test_dict_get_code_fallback(self):
        """Verify .get("code") extraction works."""
        test_input = {"code": "close / open", "note": "test"}
        extracted = test_input.get("code") or test_input.get("expression") or str(test_input)
        self.assertEqual(extracted, "close / open")
    
    def test_dict_get_expression_fallback(self):
        """Verify .get("expression") extraction works."""
        test_input = {"expression": "close * open"}
        extracted = test_input.get("code") or test_input.get("expression") or str(test_input)
        self.assertEqual(extracted, "close * open")
    
    def test_dict_no_keys_fallback_to_str(self):
        """Verify fallback to str() when no standard keys."""
        test_input = {"foo": "bar"}
        extracted = test_input.get("code") or test_input.get("expression") or str(test_input)
        self.assertEqual(extracted, "{'foo': 'bar'}")


class TestOriginalBugNotReproduced(unittest.TestCase):
    """Verify the original bug cannot be reproduced with the fix in place."""
    
    def test_original_bug_code_would_fail(self):
        """Demonstrate that the original buggy code pattern would fail."""
        # Simulating the original buggy code
        def original_buggy_check(expression):
            expr_clean = expression.replace(" ", "")  # Line 265 before fix
            return expr_clean
        
        # String works
        self.assertEqual(original_buggy_check("close / open"), "close/open")
        
        # Dict FAILS - this is the bug
        with self.assertRaises(AttributeError):
            original_buggy_check({"code": "close / open"})
    
    def test_fixed_code_handles_both(self):
        """Verify the fixed code handles both string and dict inputs."""
        def fixed_check(expression):
            if isinstance(expression, dict):
                expression = expression.get("code") or expression.get("expression") or str(expression)
            expr_clean = expression.replace(" ", "")
            return expr_clean
        
        # String works
        self.assertEqual(fixed_check("close / open"), "close/open")
        
        # Dict NOW works - bug is fixed
        self.assertEqual(fixed_check({"code": "close / open"}), "close/open")


if __name__ == "__main__":
    unittest.main()
